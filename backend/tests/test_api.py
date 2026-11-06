import json
import shutil

import httpx
import pytest
from fastapi.testclient import TestClient

from yhdp.api.app import LOGIN_MAX_FAILS, create_app
from yhdp.api.auth import add_user, hash_password, verify_password
from yhdp.dictionary import load_dictionary
from yhdp.ingest.chunk import chunk_doc
from yhdp.ingest.load_db import embed_missing, load_doc
from yhdp.ingest.model import Block, Loc, ParsedDoc
from yhdp.ingest.tag import pending, tag_chunk, to_llm
from yhdp.llm import Ollama
from yhdp.settings import Settings, settings
from yhdp.sources import Source
from yhdp.store.db import connect

SRC = Source(doc_id="t", file_match="t", title="Hướng dẫn SXHD", issuer="QĐ 1", year=2023,
             kind="primary", format="docx", citation="section", van_de_prior=[22])
RUN = {"ly_do": "x", "van_de": [{"id": 22, "primary": True, "conf": 0.9}],
       "mien": [{"id": "3.2", "conf": 0.9}], "bloom_ceiling": {"level": "Áp dụng", "conf": 0.9},
       "content_type": "điều_trị", "population": []}


@pytest.fixture
def env(tmp_path, monkeypatch):
    (tmp_path / "dictionary").mkdir()
    shutil.copy(settings.data_dir / "dictionary" / "terms.yaml", tmp_path / "dictionary")
    shutil.copytree(settings.data_dir / "blueprint", tmp_path / "blueprint")
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    load_dictionary.cache_clear()
    db = tmp_path / "t.db"
    con = connect(db)
    blocks = [Block(kind="para", text=f"đoạn {i}", loc=Loc(section_path=[f"{i}. S"], anchor=str(i)),
                    needs_review=["table_flattened"]) for i in (1, 2)]
    load_doc(con, SRC, chunk_doc(ParsedDoc(doc_id="t", blocks=blocks), SRC, count=len))
    reply = json.dumps(to_llm(RUN))
    llm = Ollama(base_url="http://x", log_dir=tmp_path, transport=httpx.MockTransport(
        lambda req: httpx.Response(200, json={"message": {"content": reply}})))
    for c in pending(con):
        tag_chunk(con, llm, c, SRC, "sys")
    con.execute("INSERT INTO review_items (kind, ref, payload) VALUES ('dictionary', 'ESBL=x', ?)",
                (json.dumps({"canonical": "Betalactamase phổ rộng", "alias": "ESBL",
                             "method": "abbr_list", "sources": [], "known_as": None}),))
    con.commit()
    add_user(con, "bs.a", "mat-khau-dai", "reviewer")
    add_user(con, "sv.b", "mat-khau-dai", "learner")
    yield TestClient(create_app(db_path=db, web_dir=tmp_path / "web", secret="s" * 32)), con
    load_dictionary.cache_clear()


def login(client, username="bs.a", password="mat-khau-dai"):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    return r, {"Authorization": f"Bearer {r.json().get('token')}"}


def test_password_hashing():
    h = hash_password("abc")
    assert verify_password("abc", h) and not verify_password("abd", h)
    assert hash_password("abc") != h  # salted


def test_auth_required_and_roles(env):
    client, _ = env
    assert client.get("/api/meta").status_code == 401
    assert client.get("/api/v1/meta").status_code == 401
    _, learner = login(client, "sv.b")
    assert client.get("/api/meta", headers=learner).status_code == 200
    assert client.get("/api/v1/meta", headers=learner).status_code == 200
    versioned_login = client.post("/api/v1/auth/login", json={
        "username": "sv.b", "password": "mat-khau-dai"})
    assert versioned_login.status_code == 200
    versioned_headers = {"Authorization": f"Bearer {versioned_login.json()['token']}"}
    assert client.get("/api/v1/me", headers=versioned_headers).status_code == 200
    assert client.get("/api/review/next", headers=learner).status_code == 403
    assert client.get("/api/v1/review/next", headers=learner).status_code == 403


def test_login_rate_limited(env):
    client, _ = env
    for _ in range(LOGIN_MAX_FAILS):
        assert login(client, password="sai")[0].status_code == 401
    assert login(client)[0].status_code == 429


def test_tag_review_accept_and_edit(env):
    client, con = env
    _, h = login(client)
    item = client.get("/api/review/next", headers=h).json()["item"]
    assert item["chunk"]["citation"] == "QĐ 1 (2023) › 1. S" and item["remaining"] == 2
    assert item["auto"]["blueprint"]["van_de"][0]["id"] == 22
    assert client.post(f"/api/review/tag/{item['id']}", json={"action": "accept"},
                       headers=h).json() == {"ok": True}

    item2 = client.get("/api/review/next", headers=h).json()["item"]
    assert item2["chunk"]["chunk_id"] != item["chunk"]["chunk_id"]
    edit = {"van_de_chinh": 21, "van_de_phu": [22], "mien": ["2.3"], "bloom": "Hiểu",
            "content_type": "chẩn_đoán", "population": ["trẻ_em"], "note": "sửa"}
    r = client.post(f"/api/review/tag/{item2['id']}", json={"action": "save", "edit": edit},
                    headers=h)
    assert r.status_code == 200
    human = {r["chunk_id"]: json.loads(r["tags"]) for r in con.execute(
        "SELECT chunk_id, tags FROM chunk_tags WHERE source = 'human'")}
    rec = human[item2["chunk"]["chunk_id"]]
    assert [v["id"] for v in rec["blueprint"]["van_de"]] == [21, 22]
    assert rec["bloom_ceiling"]["level"] == "Hiểu" and rec["mcq_eligible"] is False
    assert rec["reviewer"] == "bs.a" and rec["note"] == "sửa"
    assert client.get("/api/review/next", headers=h).json()["item"] is None
    assert client.get("/api/review/stats", headers=h).json()["human_tags"] == 2


def test_tag_edit_validation(env):
    client, _ = env
    _, h = login(client)
    item = client.get("/api/review/next", headers=h).json()["item"]
    bad = {"van_de_chinh": 21, "mien": ["2.3"], "bloom": "Sáng tạo", "content_type": "khác"}
    r = client.post(f"/api/review/tag/{item['id']}", json={"action": "save", "edit": bad}, headers=h)
    assert r.status_code == 400


def test_dictionary_new_term_writes_yaml(env, tmp_path):
    client, _ = env
    _, h = login(client)
    item = client.get("/api/review/next?kind=dictionary", headers=h).json()["item"]
    assert item["suggestion"]["alias"] == "ESBL" and item["existing"] is None
    r = client.post(f"/api/review/dictionary/{item['id']}", headers=h, json={
        "action": "new_term", "canonical": "beta-lactamase phổ rộng", "aliases": ["ESBL"],
        "type": "XétNghiệm"})
    assert r.status_code == 200
    text = (tmp_path / "dictionary" / "terms.yaml").read_text(encoding="utf-8")
    assert "Reviewer-approved" in text and "canonical: beta-lactamase phổ rộng" in text
    assert text.startswith("# Medical synonym")  # comments kept
    assert load_dictionary().normalize("ESBL") == "beta-lactamase phổ rộng"


def test_dictionary_conflict_rejected_and_alias_added(env):
    client, _ = env
    _, h = login(client)
    item = client.get("/api/review/next?kind=dictionary", headers=h).json()["item"]
    r = client.post(f"/api/review/dictionary/{item['id']}", headers=h, json={
        "action": "add_alias", "canonical": "huyết áp", "aliases": ["THA"]})  # THA is taken
    assert r.status_code == 400 and "used by both" in r.json()["detail"]
    r = client.post(f"/api/review/dictionary/{item['id']}", headers=h, json={
        "action": "add_alias", "canonical": "kháng sinh", "aliases": ["thuốc KS"]})
    assert r.status_code == 200
    assert load_dictionary().normalize("thuốc KS") == "kháng sinh"


def test_figures_need_token_and_stay_in_folder(env, tmp_path, monkeypatch):
    client, _ = env
    _, h = login(client)
    token = h["Authorization"].removeprefix("Bearer ")
    monkeypatch.setattr(settings, "derived_dir", tmp_path / "derived")
    (tmp_path / "derived" / "t" / "figures").mkdir(parents=True)
    (tmp_path / "derived" / "t" / "figures" / "a.png").write_bytes(b"png")
    assert client.get("/api/files/t/figures/a.png").status_code == 422
    assert client.get("/api/files/t/figures/a.png?t=bad").status_code == 401
    assert client.get(f"/api/files/t/figures/a.png?t={token}").content == b"png"
    assert client.get(f"/api/v1/files/t/figures/a.png?t={token}").content == b"png"
    assert client.get(f"/api/files/t/figures/..%2F..%2Ft.db?t={token}").status_code == 404


def test_spa_fallback(env, tmp_path):
    client, _ = env
    assert client.get("/luyen-tap").status_code == 503  # not built
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "index.html").write_text("<html>app</html>")
    assert client.get("/luyen-tap").text == "<html>app</html>"
    assert client.get("/api/nope").status_code == 404


def test_reviewer_app_under_review(tmp_path):
    web, review = tmp_path / "web", tmp_path / "review"
    client = TestClient(create_app(db_path=tmp_path / "t.db", web_dir=web, review_dir=review,
                                   secret="s" * 32))
    assert client.get("/review/").status_code == 503  # not built
    for d, name in ((web, "learner"), (review, "reviewer")):
        (d / "assets").mkdir(parents=True)
        (d / "index.html").write_text(f"<html>{name}</html>")
    (review / "assets" / "a.js").write_text("js")
    assert client.get("/review").text == "<html>reviewer</html>"
    assert client.get("/review/tags").text == "<html>reviewer</html>"
    assert client.get("/review/assets/a.js").text == "js"
    assert client.get("/review/..%2F..%2Ft.db").text == "<html>reviewer</html>"
    assert client.get("/").text == "<html>learner</html>"
    assert client.get("/reviewer-notes").text == "<html>learner</html>"


def chat_llm(tmp_path, turns, plan=None):
    """A fake Ollama: embeddings, then each streamed chat call replays the next of `turns`
    (a list of message dicts); non-streamed calls answer the planner's schema with `plan` and
    the suggestions schema otherwise."""
    calls = []

    def handler(req):
        body = json.loads(req.content)
        if req.url.path == "/api/embed":
            return httpx.Response(200, json={"embeddings": [[1.0, 0.0]] * len(body["input"])})
        calls.append(body)
        if not body["stream"]:
            out = {"cau_hoi": ["Liều dịch cho trẻ béo phì?", "đoạn 1", "Khi nào chuyển tuyến?"]}
            if {"chuong", "doi_tuong"} & set(body["format"]["properties"]):
                out = plan or {"chuong": [], "khia_canh": ""}
            return httpx.Response(200, json={"message": {"content": json.dumps(out)}})
        lines = turns[sum(c["stream"] for c in calls) - 1]
        return httpx.Response(200, text="\n".join(json.dumps({"message": x}) for x in lines))

    return Ollama(base_url="http://x", log_dir=tmp_path,
                  transport=httpx.MockTransport(handler)), calls


def chat_client(env, tmp_path, turns, plan=None):
    _, con = env
    llm, calls = chat_llm(tmp_path, turns, plan)
    embed_missing(con, llm)
    client = TestClient(create_app(db_path=tmp_path / "t.db", web_dir=tmp_path / "web",
                                   secret="s" * 32, llm=llm))
    _, h = login(client, "sv.b")  # learners can chat
    return client, h, calls


def test_chat_streams_sources_answer_and_citations(env, tmp_path):
    client, h, calls = chat_client(env, tmp_path, [[{"content": "Bù dịch [S1]"},
                                                    {"content": " và [S9]."}]])
    r = client.post("/api/chat", json={"question": "đoạn 1", "history": [
        {"role": "assistant", "content": "trước đó [S3]"}]}, headers=h)
    events = [json.loads(line) for line in r.text.splitlines()]
    assert events[0]["type"] == "sources" and events[0]["sources"][0]["citation"].startswith("QĐ 1")
    assert "".join(e["text"] for e in events if e["type"] == "delta") == "Bù dịch [S1] và [S9]."
    assert events[-2] == {"type": "done", "cited": [1], "invalid": [9], "tools": False,
                          "mode": "giai_thich"}
    # the question itself is not suggested back
    assert events[-1] == {"type": "suggestions",
                          "items": ["Liều dịch cho trẻ béo phì?", "Khi nào chuyển tuyến?"]}
    assert calls[0]["tools"][0]["function"]["name"] == "tao_bai_trac_nghiem"
    assert calls[0]["messages"][1]["content"] == "trước đó "  # stale citations stripped
    assert client.post("/api/chat", json={"question": "x"}).status_code == 401


def test_synthesis_questions_are_recognised():
    from yhdp.api.chat import is_synthesis

    assert is_synthesis("lập bảng danh sách bệnh - triệu chứng")
    assert not is_synthesis("So sánh điều trị THA và ĐTĐ")  # a comparison is its own move
    assert is_synthesis("liet ke cac benh lay qua duong ho hap")  # typed without diacritics
    assert not is_synthesis("Liều paracetamol cho trẻ sốt xuất huyết?")
    assert not is_synthesis("bảng phân độ sốt xuất huyết")  # one table, one chapter


def test_chat_synthesis_fans_out_over_planned_chapters(env, tmp_path):
    client, h, calls = chat_client(env, tmp_path, [[{"content": "| A | B |\n|---|---|\n| 1 [S1] | 2 [S2] |"}]],
                                   plan={"chuong": [2, 1, 9], "khia_canh": "triệu chứng"})
    r = client.post("/api/chat", json={"question": "Lập bảng các mục"}, headers=h)
    events = [json.loads(line) for line in r.text.splitlines()]
    assert events[0] == {"type": "plan", "mode": "giai_thich", "sections": ["2. S", "1. S"],
                         "aspect": "triệu chứng"}
    # one chunk per chapter, in the order planned; chapter 9 does not exist
    assert [s["citation"].rsplit("› ", 1)[1] for s in events[1]["sources"]] == ["2. S", "1. S"]
    assert "MỤC LỤC" in calls[0]["messages"][0]["content"]
    assert "Trình bày đủ mọi mục" in calls[1]["messages"][-1]["content"]
    assert next(e for e in events if e["type"] == "done")["cited"] == [1, 2]


def test_chat_synthesis_falls_back_to_search_when_plan_is_narrow(env, tmp_path):
    client, h, calls = chat_client(env, tmp_path, [[{"content": "x [S1]"}]],
                                   plan={"chuong": [1], "khia_canh": "điều trị"})
    events = [json.loads(line) for line in client.post(
        "/api/chat", json={"question": "liệt kê đoạn 1"}, headers=h).text.splitlines()]
    assert events[0]["type"] == "sources" and "Trình bày đủ" not in calls[1]["messages"][-1]["content"]


def test_tutor_moves_are_read_from_the_wording():
    from yhdp.api.tutor import resolve_mode

    assert resolve_mode("auto", "Phân biệt sốt rét và sốt xuất huyết") == "so_sanh"
    assert resolve_mode("auto", "cho minh vi du ca lam sang tang huyet ap") == "vi_du"
    assert resolve_mode("auto", "Kiểm tra mình về hen phế quản") == "kiem_tra"
    assert resolve_mode("auto", "Câu hỏi tôi muốn hỏi là liều thuốc") == "giai_thich"
    assert resolve_mode("auto", "Tóm tắt điều trị thương hàn") == "tom_tat"
    assert resolve_mode("auto", "Liều paracetamol?") == "giai_thich"
    assert resolve_mode("vi_du", "Liều paracetamol?") == "vi_du"  # the client's choice wins


def test_chat_compare_gathers_sources_for_each_item(env, tmp_path):
    client, h, calls = chat_client(
        env, tmp_path, [[{"content": "| | A | B |\n|-|-|-|\n| x | 1 [S1] | 2 [S2] |"}]],
        plan={"doi_tuong": ["đoạn 1", "đoạn 2"], "tieu_chi": ["lâm sàng"]})
    events = [json.loads(line) for line in client.post(
        "/api/chat", json={"question": "So sánh đoạn 1 và đoạn 2"}, headers=h).text.splitlines()]
    assert events[0] == {"type": "plan", "mode": "so_sanh", "sections": ["đoạn 1", "đoạn 2"],
                         "aspect": "lâm sàng"}
    assert len(events[1]["sources"]) == 2
    assert "Bảng so sánh" in calls[1]["messages"][-1]["content"]
    assert "tools" not in calls[1]  # no quiz or card tools during a move
    assert next(e for e in events if e["type"] == "done")["mode"] == "so_sanh"


def test_chat_quiz_me_then_grade_on_the_same_sources(env, tmp_path):
    _, con = env
    first = con.execute("SELECT chunk_id FROM chunks ORDER BY seq").fetchone()[0]
    client, h, calls = chat_client(env, tmp_path, [[{"content": "Câu hỏi: đoạn nào?"}],
                                                   [{"content": "Đúng ý chính [S1]."}]])
    asked = [json.loads(line) for line in client.post("/api/chat", json={
        "question": "Kiểm tra mình", "context": [first],
        "history": [{"role": "user", "content": "đoạn 1"}]}, headers=h).text.splitlines()]
    # the discussed passage first, then a search on the last question for a little more
    assert asked[0]["sources"][0]["chunk_id"] == first
    assert asked[-1] == {"type": "done", "cited": [], "invalid": [], "tools": False,
                         "mode": "kiem_tra"}  # no suggestions: the question awaits its answer
    assert "KHÔNG nêu đáp án" in calls[0]["messages"][-1]["content"]
    graded = [json.loads(line) for line in client.post("/api/chat", json={
        "question": "Là đoạn 1", "mode": "cham", "context": [first],
        "history": [{"role": "assistant", "content": "Câu hỏi: đoạn nào?"}]},
        headers=h).text.splitlines()]
    assert [s["chunk_id"] for s in graded[0]["sources"]] == [first]  # only the question's sources
    assert calls[-2]["messages"][-1]["content"].count("Câu trả lời của người học: Là đoạn 1") == 1


def test_chat_tool_adds_card_and_retries_after_error(env, tmp_path):
    _, con = env
    first = con.execute("SELECT chunk_id FROM chunks ORDER BY seq DESC").fetchone()[0]
    card = {"name": "them_the_on_tap", "arguments": {"mat_truoc": "Bù dịch?", "mat_sau": "x"}}
    turns = [[{"content": "", "tool_calls": [{"function": card}]}],
             [{"content": "", "tool_calls": [{"function": {**card, "arguments": {
                 "mat_truoc": "Bù dịch?", "mat_sau": "Ringer [S2]"}}}]}]]
    client, h, calls = chat_client(env, tmp_path, turns)
    r = client.post("/api/chat", json={"question": "lưu thẻ giúp tôi", "context": [first]},
                    headers=h)
    events = [json.loads(line) for line in r.text.splitlines()]
    tools = [e["result"] for e in events if e["type"] == "tool"]
    assert not tools[0]["ok"] and "[S#]" in tools[0]["message"]  # uncited: sent back
    assert tools[1]["ok"] and tools[1]["front"] == "Bù dịch?"
    assert events[-1]["type"] == "done" and events[-1]["tools"]  # no suggestions after tools
    assert len(calls) == 2  # success ends the turn: no model recap
    assert [m["role"] for m in calls[1]["messages"][-2:]] == ["tool", "user"]  # retry nudge
    row = con.execute("SELECT * FROM revision_cards").fetchone()
    assert (row["origin"], row["back"]) == ("chat", "Ringer [S1]")  # renumbered to its source
    assert json.loads(row["sources"])[0]["chunk_id"] == events[0]["sources"][1]["chunk_id"]
    assert len(events[0]["sources"]) == 2  # the carried-over context chunk wasn't duplicated
    assert client.get("/api/deck", headers=h).json()["total"] == 1


def test_chat_tool_quiz_without_items(env, tmp_path):
    call = {"name": "tao_bai_trac_nghiem", "arguments": {"chu_de": "sốt rét", "so_cau": 10}}
    client, h, calls = chat_client(env, tmp_path, [
        [{"content": "", "tool_calls": [{"function": call}]}],
        [{"content": "", "tool_calls": [{"function": call}]}],
        [{"content": "Chưa có câu hỏi."}]])
    events = [json.loads(line) for line in client.post(
        "/api/chat", json={"question": "tạo quiz sốt rét"}, headers=h).text.splitlines()]
    tools = [e for e in events if e["type"] == "tool"]
    assert len(tools) == 2 and not tools[0]["result"]["ok"] and "sốt rét" in tools[0]["result"]["message"]
    assert "tools" not in calls[-1]  # after two failed rounds the model can only explain


def test_mcq_endpoints(env):
    client, con = env
    chunk = con.execute("SELECT chunk_id, content_hash FROM chunks ORDER BY seq").fetchone()
    expl = {k: {"correct": k == "B", "why": f"lý do {k} [S1]", **({} if k == "B" else
                {"mistake": f"nhầm {k} [S1]"})} for k in "ABCD"}
    with con:
        con.execute("INSERT INTO mcq_items (van_de, de_muc, mien, bloom, stem, lead_in, options, "
                    "answer, explanations, sources, model) VALUES (22, 4, '3.2', 'Áp dụng', 'Trẻ 8 "
                    "tuổi…', 'Xử trí?', ?, 'B', ?, ?, 'm')",
                    (json.dumps({k: f"phương án {k}" for k in "ABCD"}), json.dumps(expl),
                     json.dumps([dict(chunk)])))
    _, learner = login(client, "sv.b")
    item = client.get("/api/mcq/practice", headers=learner).json()["item"]
    assert "answer" not in item
    r = client.post("/api/mcq/answer", json={"item_id": item["id"], "chosen": "A"}, headers=learner)
    assert r.json()["correct"] is False and r.json()["explanations"]["A"]["mistake"] == "nhầm A [S1]"
    assert client.post("/api/mcq/sets", json={"size": 7}, headers=learner).status_code == 400
    s = client.post("/api/mcq/sets", json={"size": 10}, headers=learner).json()
    assert s["minutes"] == 1 and len(s["items"]) == 1
    done = client.post(f"/api/mcq/sets/{s['id']}/submit", json={"answers": {str(item["id"]): "B"}},
                       headers=learner).json()
    assert done["report"]["correct"] == 1
    assert client.post(f"/api/mcq/items/{item['id']}/flag", json={"reason": "sai"},
                       headers=learner).json() == {"ok": True}
    assert client.post(f"/api/review/mcq/{item['id']}", json={"action": "approve"},
                       headers=learner).status_code == 403
    _, rev = login(client)
    assert client.get("/api/review/next?kind=mcq", headers=rev).json()["item"]["flags"][0]["reason"] == "sai"
    assert client.post(f"/api/review/mcq/{item['id']}", json={"action": "approve"},
                       headers=rev).json() == {"ok": True}
    assert client.get("/api/review/stats", headers=rev).json()["counts"]["mcq:open"] == 0


def test_topic_scope_matches_disease_names_in_titles(env, tmp_path):
    from yhdp.retrieve import Retriever

    _, con = env
    llm, _ = chat_llm(tmp_path, [])
    embed_missing(con, llm)
    r = Retriever(con, llm, dictionary=load_dictionary())
    all_chunks = {c for (c,) in con.execute("SELECT chunk_id FROM chunks")}
    chunks, scoped = r.topic("sốt xuất huyết Dengue ở trẻ em")  # title says "SXHD"
    assert scoped == all_chunks and set(chunks) == all_chunks
    assert r.topic("tăng huyết áp")[1] == set()


def test_api_only_mode_does_not_register_frontend_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "serve_frontends", False)
    client = TestClient(create_app(db_path=tmp_path / "t.db", secret="s" * 32))

    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/").status_code == 404
    assert client.get("/review/").status_code == 404
    assert client.get("/api/nope").status_code == 404


def test_deployment_settings_parse_json_origins(monkeypatch):
    monkeypatch.setenv("YHDP_SERVE_FRONTENDS", "false")
    monkeypatch.setenv("YHDP_CORS_ORIGINS", '["https://study.example.com"]')

    configured = Settings(_env_file=None)

    assert configured.serve_frontends is False
    assert configured.cors_origins == ["https://study.example.com"]


def test_cors_allows_configured_frontend_origin(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "cors_origins", ["https://frontend.example"])
    client = TestClient(create_app(db_path=tmp_path / "t.db", secret="s" * 32,
                                   serve_frontends=False))

    response = client.options("/api/meta", headers={
        "Origin": "https://frontend.example",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization",
    })

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://frontend.example"


def test_app_closes_owned_ollama_client(monkeypatch, tmp_path):
    instances = []

    class HttpClient:
        closed = False

        def close(self):
            self.closed = True

    class StubOllama:
        def __init__(self):
            self.http = HttpClient()
            instances.append(self)

        def close(self):
            self.http.close()

    monkeypatch.setattr("yhdp.api.app.Ollama", StubOllama)
    app = create_app(db_path=tmp_path / "t.db", secret="s" * 32, serve_frontends=False)

    with TestClient(app):
        assert not instances[0].http.closed

    assert instances[0].http.closed

    provided = StubOllama()
    with TestClient(create_app(db_path=tmp_path / "provided.db", secret="s" * 32,
                               llm=provided, serve_frontends=False)):
        assert not provided.http.closed
    assert not provided.http.closed
    provided.close()
