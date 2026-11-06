import json

import httpx
import pytest
from pydantic import ValidationError

from yhdp.ingest.chunk import chunk_doc
from yhdp.ingest.load_db import load_doc
from yhdp.ingest.model import Block, Loc, ParsedDoc
from yhdp.ingest.tag import (
    from_llm,
    output_schema,
    pending,
    record_to_output,
    route,
    select_pilot,
    system_prompt,
    tag_chunk,
    to_llm,
    to_record,
    user_prompt,
)
from yhdp.llm import Ollama
from yhdp.sources import Source
from yhdp.store.db import connect

SRC = Source(doc_id="t", file_match="t", title="Hướng dẫn SXHD", issuer="QĐ 1", year=2023,
             kind="primary", format="docx", citation="section", van_de_prior=[1, 21])


def run(van_de=21, mien="3.2", bloom="Áp dụng", conf=0.9, second=None):
    vd = [{"id": van_de, "primary": True, "conf": conf}]
    if second:
        vd.append({"id": second, "primary": False, "conf": 0.6})
    return {"ly_do": "x", "van_de": vd, "mien": [{"id": mien, "conf": conf}],
            "bloom_ceiling": {"level": bloom, "conf": conf}, "content_type": "điều_trị",
            "population": ["trẻ_em"]}


def test_route_auto_when_runs_agree_confidently():
    assert route(run(), run(), []) == ("auto", [])


@pytest.mark.parametrize("other,reason", [
    (run(van_de=1), "van_de_disagree"), (run(mien="2.3"), "mien_disagree"),
    (run(bloom="Hiểu"), "bloom_disagree"), (run(bloom="Đánh giá"), "bloom_disagree"),
    (run(conf=0.5), "low_conf")])
def test_route_review_reasons(other, reason):
    status, reasons = route(run(), other, [])
    assert status == "review" and reasons == [reason]


def test_route_tolerates_order_swaps_and_neighbouring_eligible_bloom():
    a, b = run(), run(bloom="Phân tích")
    a["mien"] = [{"id": "2.3", "conf": 0.9}, {"id": "3.3", "conf": 0.85}]
    b["mien"] = [{"id": "3.3", "conf": 0.9}, {"id": "2.3", "conf": 0.85}]
    assert route(a, b, []) == ("auto", [])
    assert route(run(bloom="Nhớ"), run(bloom="Hiểu"), []) == ("auto", [])


def test_route_flags_force_review():
    assert route(run(), run(), ["table_flattened"]) == ("review", ["flag:table_flattened"])


def test_schema_enforces_blueprint_labels_and_distinct_van_de():
    schema = output_schema()
    ok = to_llm(run(second=1))
    assert ok["mien"][0]["id"] == "3.2 Điều trị bằng thuốc"
    assert from_llm(schema.model_validate(ok).model_dump()) == run(second=1)
    assert ok["van_de_chinh"]["id"] == "21. Sốt" and ok["van_de_phu"][0]["id"].startswith("1. ")
    with pytest.raises(ValidationError):
        schema.model_validate({**ok, "van_de_chinh": {"id": "99. X", "conf": 1}})
    with pytest.raises(ValidationError):
        schema.model_validate({**ok, "van_de_chinh": {"id": 21, "conf": 1}})  # bare ids rejected
    with pytest.raises(ValidationError, match="lặp"):
        schema.model_validate({**ok, "van_de_phu": [ok["van_de_chinh"]]})


def test_prompts_carry_blueprint_and_context():
    system = system_prompt()
    assert "21. " in system and "3.2 Điều trị bằng thuốc" in system and "Áp dụng" in system
    chunk = {"chunk_id": "t#a#c01", "kind": "table", "text": "| a |",
             "loc": Loc(section_path=["IV. ĐIỀU TRỊ", "B1. Trẻ em"], anchor="IV/B1")}
    user = user_prompt(chunk, SRC)
    assert "IV. ĐIỀU TRỊ › B1. Trẻ em" in user and "LOẠI: bảng" in user and "21." in user


@pytest.fixture
def con(tmp_path):
    con = connect(tmp_path / "t.db")
    blocks = [Block(kind="para", text=f"đoạn {i}", loc=Loc(section_path=[f"{i}. S"], anchor=str(i)),
                    needs_review=["table_flattened"] if i == 2 else [])
              for i in (1, 2)]
    load_doc(con, SRC, chunk_doc(ParsedDoc(doc_id="t", blocks=blocks), SRC, count=len))
    return con


def test_record_source_comes_from_chunk_and_round_trips(con):
    chunk = con.execute("SELECT * FROM chunks ORDER BY seq").fetchone()
    doc = con.execute("SELECT * FROM documents").fetchone()
    rec = to_record(dict(chunk), doc, run(second=1), "auto")
    assert rec["source"]["issuer"] == "QĐ 1" and rec["source"]["section_path"] == ["1. S"]
    assert rec["blueprint"]["de_muc"] == [4, 1]  # vấn đề 21 → đề mục 4, vấn đề 1 → đề mục 1
    assert rec["blueprint"]["mien"][0]["label"] == "Điều trị bằng thuốc"
    assert rec["mcq_eligible"] is True
    assert record_to_output(rec) == run(second=1)


def fake_llm(tmp_path, reply: dict) -> Ollama:
    def handler(req):
        return httpx.Response(200, json={"message": {"content": json.dumps(to_llm(reply))}})
    return Ollama(base_url="http://x", transport=httpx.MockTransport(handler), log_dir=tmp_path)


def test_tag_chunk_stores_tags_and_queues_flagged(con, tmp_path):
    llm = fake_llm(tmp_path, run())
    statuses = [tag_chunk(con, llm, c, SRC, "sys")[0] for c in pending(con)]
    assert statuses == ["auto", "review"]
    assert con.execute("SELECT count(*) FROM chunk_tags WHERE source = 'auto'").fetchone()[0] == 2
    item = con.execute("SELECT * FROM review_items WHERE kind = 'tag'").fetchone()
    assert item["ref"] == "t#2#c01" and json.loads(item["payload"])["reasons"] == ["flag:table_flattened"]
    assert pending(con) == []  # resumable: nothing left
    assert len(pending(con, force=True)) == 2


def test_human_tag_pins_chunk_and_changed_content_is_requeued(con, tmp_path):
    llm = fake_llm(tmp_path, run())
    c1 = pending(con)[0]
    rec = to_record(dict(c1), con.execute("SELECT * FROM documents").fetchone(), run(), "human")
    con.execute("INSERT INTO chunk_tags (chunk_id, content_hash, tags, source) "
                "VALUES (?, ?, ?, 'human')", (c1["chunk_id"], c1["content_hash"], json.dumps(rec)))
    assert [c["chunk_id"] for c in pending(con, force=True)] == ["t#2#c01"]

    edited = [Block(kind="para", text="đoạn 1 đã sửa", loc=Loc(section_path=["1. S"], anchor="1"))]
    load_doc(con, SRC, chunk_doc(ParsedDoc(doc_id="t", blocks=edited), SRC, count=len))
    (changed,) = pending(con)
    status, reasons = tag_chunk(con, llm, changed, SRC, "sys")
    assert (status, reasons) == ("review", ["content_changed"])
    payload = json.loads(con.execute("SELECT payload FROM review_items WHERE ref = 't#1#c01'")
                         .fetchone()[0])
    assert payload["old_human"]["review_status"] == "human"


def test_pilot_sample_is_reproducible(con):
    assert select_pilot(con, per_doc=2) == select_pilot(con, per_doc=2)
    assert len(select_pilot(con, per_doc=2)) == 2


def test_reports_coverage_and_eval(con, tmp_path):
    from yhdp.reports import cohen_kappa, coverage, tag_eval
    from yhdp.store.tags import save_human_tag

    llm = fake_llm(tmp_path, run())
    for c in pending(con):
        tag_chunk(con, llm, c, SRC, "sys")
    text = coverage(con)
    assert "| 21. Sốt | 2 | **2** |" in text and "53 of 54 vấn đề have no primary chunk" in text
    c1 = con.execute("SELECT * FROM chunks ORDER BY seq").fetchone()
    doc = con.execute("SELECT * FROM documents").fetchone()
    save_human_tag(con, c1["chunk_id"], c1["content_hash"],
                   to_record(dict(c1), doc, run(van_de=22, bloom="Hiểu"), "human"), "bs.a")
    report = tag_eval(con)
    assert "(n = 1)" in report and "| Primary vấn đề accuracy | 0% |" in report
    assert "- 21 → 22: 1" in report and "- Áp dụng → Hiểu: 1" in report
    assert "| 22. Sốt và phát ban | 1 | **1** |" in coverage(con)  # the human tag wins
    assert cohen_kappa(["a", "b"], ["a", "b"], ("a", "b")) == 1.0
