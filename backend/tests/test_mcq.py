import json
import random
from datetime import timedelta

import httpx
import pytest
from pydantic import ValidationError

from yhdp.blueprint import load_blueprint
from yhdp.ingest.chunk import chunk_doc
from yhdp.ingest.load_db import load_doc
from yhdp.ingest.model import Block, Loc, ParsedDoc
from yhdp.ingest.tag import pending, tag_chunk, to_llm
from yhdp.llm import Ollama
from yhdp.mcq import bank, deck
from yhdp.mcq.allocate import allocate, largest_remainder, pick_items
from yhdp.mcq.deck import MASTERED, schedule, stamp
from yhdp.mcq.generate import (
    Generated,
    assign_letters,
    check_item,
    generate_item,
    plan_targets,
)
from yhdp.mcq.mastery import mastery
from yhdp.sources import Source
from yhdp.store.db import connect

BP = load_blueprint()
RANGES = {d.id: tuple(d.weight) for d in BP.de_muc}
SRC = Source(doc_id="t", file_match="t", title="Hướng dẫn SXHD", issuer="QĐ 1", year=2023,
             kind="primary", format="docx", citation="section")
TEXT = ("Truyền Ringer lactat 6 ml/kg/giờ trong 3 giờ cho trẻ SXHD có dấu hiệu cảnh báo; "
        "nếu Hct tăng thì tăng lên 10 ml/kg/giờ. Người lớn bắt đầu 5 ml/kg/giờ. ") * 3


# --- allocation ---------------------------------------------------------------------------

def test_largest_remainder_sums_exactly():
    assert sum(largest_remainder({1: 18, 2: 18, 3: 8, 4: 19}, 10).values()) == 10
    assert largest_remainder({1: 1, 2: 1}, 0) == {1: 0, 2: 0}


@pytest.mark.parametrize("size", [10, 30, 60, 280])
def test_allocation_matches_size_and_ranges(size):
    quota, notes = allocate(size, RANGES, {d: 999 for d in RANGES})
    assert sum(quota.values()) == size and notes == []
    if size >= 60:
        for d, (lo, hi) in RANGES.items():
            assert lo - 2 <= 100 * quota[d] / size <= hi + 2


def test_small_de_muc_rotate_in_10_question_sets():
    seen = {d for rot in range(4) for d, n in allocate(10, RANGES, {d: 99 for d in RANGES}, rot)[0].items()
            if n}
    assert {5, 8} <= seen


def test_allocation_reports_gaps_and_caps_by_bank():
    quota, notes = allocate(30, RANGES, {1: 3, 4: 40, 6: 20})
    assert quota[1] == 3 and quota[2] == 0 and sum(quota.values()) == 30
    assert any("Đề mục 2" in n for n in notes) and any("chỉ có 3 câu" in n for n in notes)


def test_pick_items_prefers_unseen_and_balances_mien():
    items = [{"id": i, "mien": "2.3" if i < 6 else "3.2", "seen": 1 if i == 0 else 0} for i in range(10)]
    counts: dict = {}
    picked = pick_items(items, 4, {"2": 40, "3": 35}, counts, random.Random(0))
    assert 0 not in [p["id"] for p in picked]
    assert counts == {"2": 2, "3": 2}


# --- generation ---------------------------------------------------------------------------

GEN = {"y_tuong": "x", "tinh_huong": "Trẻ 8 tuổi SXHD có dấu hiệu cảnh báo tại trạm y tế.",
       "cau_hoi": "Tốc độ truyền ban đầu phù hợp nhất là?",
       "noi_dung_dap_an_dung": "Ringer lactat 6 ml/kg/giờ",
       "giai_thich_dung": "Phác đồ trẻ em bắt đầu 6 ml/kg/giờ [S1].",
       "phuong_an_nhieu": [
           {"noi_dung": "Ringer lactat 5 ml/kg/giờ", "sai_vi": "Đây là liều người lớn [S1].",
            "nham_lan": "Nhầm phác đồ người lớn với trẻ em [S1]."},
           {"noi_dung": "Ringer lactat 10 ml/kg/giờ", "sai_vi": "Chỉ khi Hct tăng [S1].",
            "nham_lan": "Bỏ qua điều kiện Hct tăng [S1]."},
           {"noi_dung": "Ringer lactat 3 ml/kg/giờ", "sai_vi": "Thấp hơn liều khởi đầu 6 ml/kg/giờ [S1].",
            "nham_lan": "Nhầm với thời gian truyền 3 giờ [S1]."}]}


def test_assign_letters_puts_key_on_target_with_purposeful_explanations():
    opts, expl, key = assign_letters(Generated.model_validate(GEN), "C", random.Random(0))
    assert key == "C" and opts["C"] == "Ringer lactat 6 ml/kg/giờ" and expl["C"]["correct"]
    wrong = [k for k in "ABD"]
    assert all(expl[k]["mistake"] and not expl[k]["correct"] for k in wrong)
    assert sorted(opts.values()) == sorted([GEN["noi_dung_dap_an_dung"]] +
                                           [d["noi_dung"] for d in GEN["phuong_an_nhieu"]])


def test_clean_stem_drops_question_sentences():
    from yhdp.mcq.generate import clean_stem

    stem = "Bà N. 65 tuổi khó thở khi đi 100 m. Theo thang mMRC, bà thuộc nhóm nào?"
    assert clean_stem(stem, "Bà thuộc nhóm triệu chứng nào?") == "Bà N. 65 tuổi khó thở khi đi 100 m."
    assert clean_stem("Hỏi gì?", "Hỏi gì?") == ""


def test_schema_rejects_bare_letter_answer():
    with pytest.raises(ValidationError):
        Generated.model_validate({**GEN, "noi_dung_dap_an_dung": "C"})


def test_check_item_catches_cues_numbers_and_uncited_explanations():
    opts = {"A": "6 ml/kg/giờ", "B": "5 ml/kg/giờ", "C": "10 ml/kg/giờ", "D": "Tất cả đều đúng"}
    assert "all_none_of_the_above" in check_item(opts, "A", TEXT)
    opts["D"] = "3 ml/kg/giờ"
    assert check_item(opts, "A", TEXT) == []
    assert check_item({**opts, "A": "7 ml/kg/giờ"}, "A", TEXT) == ["key_numbers_not_in_source:7"]
    long_key = {**opts, "A": "6 ml/kg/giờ trong 3 giờ, sau đó đánh giá lại Hct và lâm sàng kỹ"}
    assert "key_much_longer" in check_item(long_key, "A", TEXT)
    invented = {**opts, "B": "Acyclovir 100 mg/ngày"}
    assert check_item(invented, "A", TEXT) == ["distractor_numbers_not_in_source:100"]
    absent = {"A": {"why": "đúng [S1]"}, "B": {"why": "Nguồn không đề cập kháng sinh [S1]",
                                                "mistake": "nhầm [S1]"}}
    assert check_item(opts, "A", TEXT, absent, 1) == ["distractor_B_wrong_only_by_absence"]
    expl = {"A": {"why": "đúng [S1]"}, "B": {"why": "sai", "mistake": "nhầm"}}
    assert check_item(opts, "A", TEXT, expl, 1) == ["explanation_B_uncited"]
    assert check_item(opts, "A", TEXT, {"A": {"why": "[S4]"}}, 1) == ["explanation_A_uncited"]


@pytest.fixture
def con(tmp_path):
    con = connect(tmp_path / "t.db")
    blocks = [Block(kind="para", text=TEXT, loc=Loc(section_path=["C. Điều trị"], anchor="C"))]
    load_doc(con, SRC, chunk_doc(ParsedDoc(doc_id="t", blocks=blocks), SRC, count=lambda s: len(s.split())))
    run = {"ly_do": "x", "van_de": [{"id": 22, "primary": True, "conf": 0.9}],
           "mien": [{"id": "3.3", "conf": 0.9}], "bloom_ceiling": {"level": "Áp dụng", "conf": 0.9},
           "content_type": "điều_trị", "population": ["trẻ_em"]}
    llm = Ollama(base_url="http://x", log_dir=tmp_path, transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"message": {"content": json.dumps(to_llm(run))}})))
    for c in pending(con):
        tag_chunk(con, llm, c, SRC, "sys")
    return con


def fake_llm(tmp_path, blind="key", single_best=True):
    def handler(req):
        body = json.loads(req.content)
        title = body["format"]["title"]
        if title == "Generated":
            out = GEN
        elif title == "BlindAnswer":
            key = body["messages"][-1]["content"]
            letter = next(k for k in "ABCD" if f"{k}. Ringer lactat 6 ml/kg/giờ" in key)
            out = {"ly_do": "x", "dap_an": letter if blind == "key" else blind}
        else:
            out = {"nhan_xet": "ok", "mot_dap_an_dung_nhat": single_best,
                   "dap_an_dung_theo_nguon": True, "co_goi_y_lo_dap_an": False, "bloom": "Áp dụng"}
        return httpx.Response(200, json={"message": {"content": json.dumps(out)}})
    return Ollama(base_url="http://x", log_dir=tmp_path, transport=httpx.MockTransport(handler))


def test_generate_item_validated_and_letters_balanced(con, tmp_path):
    (target,) = plan_targets(con, 1)
    assert (target.van_de, target.de_muc, target.mien) == (22, 4, "3.3")
    keys = []
    for _ in range(4):
        iid, status, problems = generate_item(con, fake_llm(tmp_path), target)
        assert (status, problems) == ("validated", [])
        keys.append(con.execute("SELECT answer FROM mcq_items WHERE id = ?", (iid,)).fetchone()[0])
    assert sorted(keys) == ["A", "B", "C", "D"]  # key placed on the least-used letter


def test_generate_item_discarded_when_blind_answer_disagrees(con, tmp_path):
    (target,) = plan_targets(con, 1)
    _, status, problems = generate_item(con, fake_llm(tmp_path, blind="D", single_best=False), target)
    assert status == "discarded"
    assert "not_single_best" in problems and any(p.startswith("blind_answer") for p in problems)


# --- bank ---------------------------------------------------------------------------------

@pytest.fixture
def stocked(con, tmp_path):
    (target,) = plan_targets(con, 1)
    for _ in range(6):
        generate_item(con, fake_llm(tmp_path), target)
    return con


def test_practice_answer_and_flag(stocked):
    con = stocked
    item = bank.next_practice(con, "sv")
    assert "answer" not in item and set(item["options"]) == set("ABCD")
    key = con.execute("SELECT answer FROM mcq_items WHERE id = ?", (item["id"],)).fetchone()[0]
    res = bank.answer(con, "sv", item["id"], key)
    assert res["correct"] and res["sources"][0]["citation"].startswith("QĐ 1 (2023)")
    assert res["explanations"][key]["correct"]
    assert bank.next_practice(con, "sv")["id"] != item["id"]  # unseen first
    bank.flag(con, item["id"], "sv", "đáp án sai")
    assert bank.next_review(con)["id"] == item["id"]  # flagged first
    bank.review(con, item["id"], "reject", "bs", "đồng ý")
    assert con.execute("SELECT status FROM mcq_items WHERE id = ?", (item["id"],)).fetchone()[0] \
        == "rejected"


def test_exam_set_submit_and_report(stocked):
    con = stocked
    s = bank.create_set(con, "sv", 10, seed=1)
    assert s["minutes"] == len(s["items"]) == 6
    assert any("chỉ đủ 6/10" in n for n in s["notes"])
    assert all("answer" not in i for i in s["items"])
    first = s["items"][0]["id"]
    key = con.execute("SELECT answer FROM mcq_items WHERE id = ?", (first,)).fetchone()[0]
    done = bank.submit_set(con, s["id"], "sv", {str(first): key}, seconds=120)
    rep = done["report"]
    assert (rep["correct"], rep["total"], rep["blank"]) == (1, 6, 5)
    assert rep["by_de_muc"][0]["label"].startswith("Đề mục 4")
    assert rep["by_mien"][0]["key"] == "3" and rep["by_bloom"][0]["key"] == "Áp dụng"
    assert bank.submit_set(con, s["id"], "sv", {})["report"]["correct"] == 1  # idempotent
    assert bank.list_sets(con, "sv")[0]["score"] == "1/6"
    with pytest.raises(KeyError):
        bank.get_set(con, s["id"], "someone-else")


def test_stats(stocked):
    con = stocked
    st = bank.stats(con)
    assert st["by_status"] == {"validated": 6} and st["by_de_muc"] == {4: 6}


def test_failed_draft_is_revised_with_feedback(con, tmp_path):
    calls = []

    def handler(req):
        body = json.loads(req.content)
        title = body["format"]["title"]
        if title == "Generated":
            calls.append(body["messages"])
            bad = {**GEN, "phuong_an_nhieu": [{**GEN["phuong_an_nhieu"][0], "noi_dung": "Ringer 99 ml/kg/giờ"},
                                              *GEN["phuong_an_nhieu"][1:]]}
            out = bad if len(calls) == 1 else GEN
        elif title == "BlindAnswer":
            key = body["messages"][-1]["content"]
            out = {"ly_do": "x", "dap_an": next(k for k in "ABCD" if f"{k}. Ringer lactat 6 ml" in key)}
        else:
            out = {"nhan_xet": "ok", "mot_dap_an_dung_nhat": True, "dap_an_dung_theo_nguon": True,
                   "co_goi_y_lo_dap_an": False, "bloom": "Áp dụng"}
        return httpx.Response(200, json={"message": {"content": json.dumps(out)}})

    llm = Ollama(base_url="http://x", log_dir=tmp_path, transport=httpx.MockTransport(handler))
    (target,) = plan_targets(con, 1)
    iid, status, problems = generate_item(con, llm, target)
    assert (status, problems) == ("validated", [])
    assert "con số tự đặt" in calls[1][-1]["content"]  # the problem was sent back to the writer
    v = json.loads(con.execute("SELECT validation FROM mcq_items WHERE id = ?", (iid,)).fetchone()[0])
    assert v["attempts"] == [["distractor_numbers_not_in_source:99"], []]


# --- adaptive practice: deck, mastery, topic sets ----------------------------------------

T0 = deck.now_utc()


def key(con, item_id):
    return con.execute("SELECT answer FROM mcq_items WHERE id = ?", (item_id,)).fetchone()[0]


def wrong(con, item_id):
    return next(k for k in "ABCD" if k != key(con, item_id))


def ids(con):
    return [r[0] for r in con.execute("SELECT id FROM mcq_items ORDER BY id")]


def test_schedule_steps():
    assert schedule(0, "good", False, T0) == (1, stamp(T0 + timedelta(days=3)))
    assert schedule(2, "hard", False, T0) == (2, stamp(T0 + timedelta(days=7)))
    assert schedule(3, "again", False, T0) == (0, stamp(T0 + timedelta(days=1)))
    assert schedule(1, "again", True, T0) == (-1, stamp(T0 + timedelta(minutes=10)))
    assert schedule(-1, "good", False, T0) == (0, stamp(T0 + timedelta(days=1)))
    assert schedule(3, "good", False, T0) == (MASTERED, None)


def test_miss_adds_one_card_per_chunk_and_confident_miss_relearns(stocked):
    con = stocked
    a, b = ids(con)[:2]
    r = bank.answer(con, "sv", a, wrong(con, a), confidence="sure")
    assert r["card"]["event"] == "added" and r["card"]["step"] == -1 and "10 phút" in r["card"]["text"]
    r = bank.answer(con, "sv", b, wrong(con, b), confidence="unsure")  # same chunk, not due yet
    assert r["card"]["event"] == "reset" and r["card"]["step"] == 0
    assert con.execute("SELECT count(*) FROM revision_cards").fetchone()[0] == 1
    assert bank.answer(con, "sv", b, key(con, b), confidence="sure")["card"] is None


def test_lucky_guess_adds_a_card_unsure_correct_does_not(stocked):
    con = stocked
    a = ids(con)[0]
    assert bank.answer(con, "sv", a, key(con, a), confidence="unsure")["card"] is None
    assert bank.answer(con, "sv", a, key(con, a), confidence="guess")["card"]["event"] == "added"


def test_due_card_reviewed_with_unseen_sibling_then_open_recall(stocked):
    con = stocked
    items = ids(con)
    first = items[0]
    bank.answer(con, "sv", first, wrong(con, first), confidence="unsure")
    assert deck.next_card(con, "sv") is None  # due tomorrow
    later = T0 + timedelta(days=1, minutes=1)
    nxt = deck.next_card(con, "sv", now=later)
    assert nxt["mode"] == "mcq" and nxt["item"]["id"] != first and "answer" not in nxt["item"]
    card_id = nxt["card"]["id"]
    r = bank.answer(con, "sv", nxt["item"]["id"], key(con, nxt["item"]["id"]), confidence="sure",
                    card_id=card_id)
    assert r["card"]["event"] == "reviewed" and r["card"]["step"] == 1
    for i in items:  # every sibling seen → open recall, no options
        bank.answer(con, "sv", i, key(con, i), confidence="unsure")
    con.execute("UPDATE revision_cards SET due = ?", (stamp(T0),))
    rec = deck.next_card(con, "sv", now=later)
    assert rec["mode"] == "recall" and "Đáp án:" in rec["back"] and "options" not in rec
    done = deck.review(con, "sv", card_id, "good", rec["item_id"], now=later)
    assert done["step"] == 2
    with pytest.raises(KeyError):
        deck.review(con, "other", card_id, "good")


def test_chat_card_keeps_only_cited_sources(stocked):
    con = stocked
    chunk = con.execute("SELECT chunk_id, content_hash FROM chunks").fetchone()
    refs = [{"chunk_id": "gone", "content_hash": "x"}, dict(chunk)]
    with pytest.raises(ValueError):
        deck.add_chat_card(con, "sv", "Hỏi?", "không trích dẫn", refs)
    c = deck.add_chat_card(con, "sv", "Liều Ringer?", "6 ml/kg/giờ [S2][S7]", refs)
    nxt = deck.next_card(con, "sv", now=T0 + timedelta(days=2))
    assert nxt["mode"] == "flash" and nxt["back"] == "6 ml/kg/giờ [S1]"
    assert [s["chunk_id"] for s in nxt["sources"]] == [chunk["chunk_id"]]
    listing = deck.list_cards(con, "sv")
    assert listing["total"] == 1 and listing["cards"][0]["title"] == "Liều Ringer?"
    deck.delete(con, "sv", c["id"])
    assert deck.list_cards(con, "sv")["total"] == 0


def test_mastery_weights_confidence_and_drops_rejected_items(stocked):
    con = stocked
    a, b = ids(con)[:2]
    bank.answer(con, "sv", a, key(con, a), confidence="sure")
    bank.answer(con, "sv", b, wrong(con, b), confidence="sure")
    m = mastery(con, "sv")[22]
    assert m["n"] == 2 and m["p"] == pytest.approx(2 / 4.5, abs=1e-3)  # Beta(1+1, 1+1.5)
    bank.review(con, b, "reject", "bs")
    assert mastery(con, "sv")[22]["p"] == pytest.approx(2 / 3, abs=1e-3)
    rep = bank.mastery_report(con, "sv")
    assert rep["van_de"][0]["id"] == 22 and rep["van_de"][0]["answered"] == 1


def test_practice_skips_recent_items_then_falls_back(stocked):
    con = stocked
    seen = set()
    for _ in range(6):
        item = bank.next_practice(con, "sv")
        assert item["id"] not in seen
        seen.add(item["id"])
        bank.answer(con, "sv", item["id"], key(con, item["id"]), confidence="sure")
    assert bank.next_practice(con, "sv")["id"] in seen  # all seen this week: least recent


def test_topic_set_scope_and_similarity_margin(stocked):
    con = stocked
    chunk = con.execute("SELECT chunk_id FROM chunks").fetchone()[0]
    s = bank.create_topic_set(con, "sv", "bù dịch", {chunk: 0.7, "other": 0.9}, size=4)
    assert (s["title"], s["minutes"], len(s["items"])) == ("bù dịch", None, 4)
    with pytest.raises(LookupError):
        bank.create_topic_set(con, "sv", "sốt rét", {"nope": 0.9})
    with con:  # a second, less similar chunk: its items need the scope match
        con.execute("UPDATE mcq_items SET sources = json_set(sources, '$[0].chunk_id', 'far') "
                    "WHERE id = (SELECT min(id) FROM mcq_items)")
    s = bank.create_topic_set(con, "sv", "x", {chunk: 0.7, "far": 0.5}, size=10)
    assert len(s["items"]) == 5
    s = bank.create_topic_set(con, "sv", "x", {chunk: 0.7, "far": 0.5}, {"far"}, size=10)
    assert len(s["items"]) == 6
    assert bank.list_sets(con, "sv")[-1]["title"] == "bù dịch"


def test_exam_misses_go_to_the_deck(stocked):
    con = stocked
    s = bank.create_set(con, "sv", 10, seed=1)
    rep = bank.submit_set(con, s["id"], "sv", {})["report"]
    assert rep["cards_added"] == 1  # six blanks, one concept
