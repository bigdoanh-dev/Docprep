"""Hỏi đáp, sources and the tutor under /v1. Ported from the kickoff demo's test_chat_api.py, the two
explain cases of test_practice_api.py and the commit-timing case of test_app.py."""
import pytest
from fastapi.testclient import TestClient

from app.gateway import GatewayError
from app.schemas.chat import AnswerEvent, ChatMessageList, ChatSessionList, FinalEvent, StatusEvent, StepEvent
from tests.conftest import _test_conn, birth_dose_json, make_wrong_unit_answer, sse_events

Q = "Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?"
MODELS = {"status": StatusEvent, "step": StepEvent, "answer": AnswerEvent, "final": FinalEvent}
# a chat question that names a glossary term and finds passages: three stages, the model, the check
ANSWERED = ["step"] * 6 + ["status", "status", "step", "step", "answer", "final"]


def ask(client, text, **extra):
    sid = client.post("/v1/chat/sessions", json={}).json()["id"]
    r = client.post(f"/v1/chat/sessions/{sid}/messages", json={"text": text, **extra})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    return sid, sse_events(r.text)


def test_sse_event_order_and_logging(learner_api, conn, fake_gw):
    fake_gw.responses = [birth_dose_json(conn)]
    sid, events = ask(learner_api, Q)
    assert [e for e, _ in events] == ANSWERED
    assert [d["status"] for e, d in events if e == "status"] == ["answering", "checking_sources"]
    answer, final = events[-2][1], events[-1][1]
    assert "24 giờ" in answer["text"] and answer["citations"][0]["passage_id"] == "tc-p02"
    assert final["state"] == "answered" and isinstance(final["message_id"], int)

    rows = conn.execute("select * from chat_message where session_id=%s order by id", (sid,)).fetchall()
    assert [r["role"] for r in rows] == ["user", "assistant"] and rows[0]["text"] == Q
    a = rows[1]
    assert a["state"] == "answered" and a["prompt_version"] == "answer-v1" and a["model_version"] == "fake"
    assert a["corpus_version"] == "demo-2026-10-09" and "tc-p02" in a["retrieved_passage_ids"]
    assert a["id"] == final["message_id"] and a["format"] == "text"
    assert conn.execute("select learner_pid, title from chat_session where id=%s", (sid,)).fetchone() == {
        "learner_pid": "HV-DEMO-001", "title": Q}


def test_declined_stream_has_no_status_events(learner_api, conn, fake_gw):
    _sid, events = ask(learner_api, "Con tôi sốt 39 độ nên uống thuốc gì?")
    assert [e for e, _ in events] == ["answer", "final"] and events[1][1]["state"] == "declined"
    assert fake_gw.calls == []
    assert conn.execute("select state from chat_message where role='assistant'").fetchone()["state"] == "declined"


def test_detail_follow_up_is_logged_as_giai_thich_them(learner_api, conn, fake_gw):
    fake_gw.responses = [birth_dose_json(conn)]
    sid, events = ask(learner_api, Q, detail=True)
    assert events[-1][1]["state"] == "answered"
    assert conn.execute("select text from chat_message where role='user'").fetchone()["text"] == "Giải thích thêm"


def test_history_and_session_list(learner_api, conn, fake_gw):
    fake_gw.responses = [birth_dose_json(conn)]
    sid, _ = ask(learner_api, Q)
    body = learner_api.get(f"/v1/chat/sessions/{sid}/messages").json()
    ChatMessageList.model_validate(body)
    msgs = body["items"]
    assert [m["role"] for m in msgs] == ["user", "assistant"] and msgs[1]["citations"][0]["page"] == 8
    assert msgs[0]["citations"] == [] and msgs[1]["state"] == "answered" and body["next_cursor"] is None
    listed = learner_api.get("/v1/chat/sessions").json()
    ChatSessionList.model_validate(listed)
    assert (listed["items"][0]["id"], listed["items"][0]["title"]) == (sid, Q)


def test_unknown_session_is_404_with_vietnamese_message(learner_api):
    r = learner_api.post("/v1/chat/sessions/999/messages", json={"text": "x"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "session_not_found" and r.json()["error"]["message_vi"]
    assert learner_api.get("/v1/chat/sessions/999/messages").json()["error"]["code"] == "session_not_found"


def test_empty_question_is_rejected(learner_api):
    sid = learner_api.post("/v1/chat/sessions", json={}).json()["id"]
    assert learner_api.post(f"/v1/chat/sessions/{sid}/messages", json={"text": "   "}).status_code == 422


def test_passage_endpoint_has_demo_label(learner_api):
    p = learner_api.get("/v1/passages/tc-p02").json()
    assert p["page"] == 8 and p["document"] == "Lịch tiêm chủng mở rộng" and "24 giờ" in p["excerpt"]
    assert p["demo_label"] == "Tài liệu demo – chưa thẩm định"
    law = learner_api.get("/v1/passages/lt-p01").json()
    assert law["page"] is None and law["article"] == "Điều 3, khoản 1, điểm a"
    r = learner_api.get("/v1/passages/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "passage_not_found"


def test_superseded_source_carries_a_validity_note(learner_api):
    law = learner_api.get("/v1/passages/lt-p01").json()
    assert "01/07/2026" in law["validity_note"] and "Luật Phòng bệnh" in law["validity_note"]
    assert learner_api.get("/v1/passages/tc-p02").json()["validity_note"] is None


# ---- the tutor's "Giải thích thêm" (from test_practice_api.py) -----------------------------------

def test_explain_requires_answer(learner_api):
    r = learner_api.post("/v1/items/q-dt-01/explain")
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_answered"
    assert learner_api.post("/v1/items/q-nope/explain").json()["error"]["code"] == "question_not_found"


def test_explain_streams_cited_answer_and_logs_outside_chat_list(learner_api, conn, fake_gw):
    make_wrong_unit_answer(learner_api)
    quote = "50 ÷ 2.000 = 0,025 = 2,5%"
    fake_gw.responses = ['{"evidence":[{"passage_id":"dt-p01","quote":"%s"}],"claims":[{"text":"Mẫu số là 2.000 dân '
                         'nên tỷ lệ là 2,5%%.","passage_ids":["dt-p01"]}]}' % quote]
    r = learner_api.post("/v1/items/q-dt-01/explain")
    events = sse_events(r.text)
    assert [e for e, _ in events] == ["step"] * 4 + ["status", "status", "step", "step", "answer", "final"]
    for name, data in events:
        MODELS[name].model_validate(data)
    assert events[-2][1]["citations"][0]["page"] == 58 and events[-1][1]["state"] == "answered"
    assert "Học viên đã chọn: b" in fake_gw.calls[0]["messages"][0]["content"]
    row = conn.execute("select m.prompt_version, s.kind from chat_message m join chat_session s on s.id=m.session_id "
                       "where m.role='assistant'").fetchone()
    assert row == {"prompt_version": "tutor-v1", "kind": "tutor"}
    assert learner_api.get("/v1/chat/sessions").json()["items"] == []


# ---- commit timing (from test_app.py) -------------------------------------------------------------

def test_writes_are_committed_before_the_response_is_sent(learner_api):
    """The web app chains requests (create session, then post a message); the second must see the first."""
    app = learner_api.app
    seen = {}

    async def spy(scope, receive, send):
        async def checked_send(message):
            if scope["type"] == "http" and message["type"] == "http.response.start":
                with _test_conn() as c:
                    seen["sessions"] = c.execute("select count(*) c from chat_session").fetchone()["c"]
            await send(message)
        await app(scope, receive, checked_send)

    r = TestClient(spy).post("/v1/chat/sessions", json={}, headers={"Authorization": learner_api.headers["Authorization"]})
    assert r.status_code == 200 and seen["sessions"] == 1


# ---- added with the port ----------------------------------------------------------------------

def test_every_event_is_a_contract_event_and_final_is_last(learner_api, fake_gw, conn):
    fake_gw.responses = [birth_dose_json(conn)]
    _sid, events = ask(learner_api, Q)
    for name, data in events:
        MODELS[name].model_validate(data)
    assert [n for n, _ in events] == ANSWERED
    final = events[-1][1]
    assert final["state"] == "answered" and final["format"] == "text"
    assert final["trace_summary"] == {"sources": 1, "claims_checked": 1, "claims_removed": 0}
    assert final["suggestions"] == [] and isinstance(final["message_id"], int)


def test_a_model_failure_still_ends_the_stream_and_is_logged(learner_api, fake_gw, conn):
    def down(task, messages):
        raise GatewayError("timeout")

    fake_gw.responses = down
    _sid, events = ask(learner_api, Q)
    assert [n for n, _ in events] == ["step"] * 6 + ["status", "answer", "final"]
    assert events[-1][1]["state"] == "insufficient_evidence" and events[-1][1]["trace_summary"] is None
    assert events[-2][1]["notice"] == "Không kết nối được mô hình, vui lòng thử lại." and events[-2][1]["text"] == "Chưa trả lời được câu hỏi này lúc này."
    row = conn.execute("select state, notice from chat_message where role = 'assistant'").fetchone()
    assert row == {"state": "insufficient_evidence", "notice": "Không kết nối được mô hình, vui lòng thử lại."}
    stats = learner_api.app.state.pool.get_stats()
    assert stats["pool_available"] == stats["pool_size"]         # the stream's connection went back to the pool


def test_an_unforeseen_failure_also_ends_the_stream_with_final(learner_api, fake_gw, conn):
    def broken(task, messages):
        raise RuntimeError("not a gateway error")

    fake_gw.responses = broken
    sid, events = ask(learner_api, Q)
    assert [n for n, _ in events][-2:] == ["answer", "final"]
    assert events[-1][1]["state"] == "insufficient_evidence" and events[-2][1]["notice"] == "Có lỗi xảy ra. Vui lòng thử lại."
    assert events[-2][1]["citations"] == []
    assert [m["role"] for m in learner_api.get(f"/v1/chat/sessions/{sid}/messages").json()["items"]] == ["user", "assistant"]
    for n in range(12):                                           # more failed streams than the pool holds
        ask(learner_api, f"{Q} ({n})")
    stats = learner_api.app.state.pool.get_stats()
    assert stats["pool_available"] == stats["pool_size"]


def test_another_learners_session_is_not_found(api, learner_api, tokens_for_new_learner, fake_gw):
    sid = learner_api.post("/v1/chat/sessions", json={}).json()["id"]
    other = tokens_for_new_learner()
    for method, path, body in [("GET", f"/v1/chat/sessions/{sid}/messages", None),
                               ("POST", f"/v1/chat/sessions/{sid}/messages", {"text": Q})]:
        r = api.request(method, path, json=body, headers=other)
        assert r.status_code == 404 and r.json()["error"]["code"] == "session_not_found"
    assert api.get("/v1/chat/sessions", headers=other).json()["items"] == []
    assert fake_gw.calls == []


def test_sessions_and_messages_are_paged(learner_api, fake_gw, conn):
    fake_gw.responses = [birth_dose_json(conn)] * 3      # the fake answers by call number
    sids = [ask(learner_api, f"{Q} ({n})")[0] for n in range(3)]
    first = learner_api.get("/v1/chat/sessions", params={"limit": 2}).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    rest = learner_api.get("/v1/chat/sessions", params={"limit": 2, "cursor": first["next_cursor"]}).json()
    assert len(rest["items"]) == 1 and rest["next_cursor"] is None
    assert [s["id"] for s in first["items"] + rest["items"]] == sorted(sids, reverse=True)
    r = learner_api.get("/v1/chat/sessions", params={"cursor": "not-a-cursor"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_cursor"

    page = learner_api.get(f"/v1/chat/sessions/{sids[0]}/messages", params={"limit": 1}).json()
    assert [m["role"] for m in page["items"]] == ["user"] and page["next_cursor"]
    tail = learner_api.get(f"/v1/chat/sessions/{sids[0]}/messages", params={"limit": 1, "cursor": page["next_cursor"]}).json()
    assert [m["role"] for m in tail["items"]] == ["assistant"] and tail["next_cursor"] is None


def test_a_session_opened_from_a_hoc_phan_searches_only_it(learner_api, fake_gw, conn):
    sid = learner_api.post("/v1/chat/sessions", json={"module_id": "g2"}).json()["id"]
    events = sse_events(learner_api.post(f"/v1/chat/sessions/{sid}/messages", json={"text": Q}).text)
    assert events[-1][1]["state"] == "insufficient_evidence" and fake_gw.calls == []      # g2 has no passages yet
    r = learner_api.post("/v1/chat/sessions", json={"module_id": "g99"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "module_not_found"
    fake_gw.responses = [birth_dose_json(conn)]
    sid = learner_api.post("/v1/chat/sessions", json={"module_id": "g1"}).json()["id"]
    events = sse_events(learner_api.post(f"/v1/chat/sessions/{sid}/messages", json={"text": Q}).text)
    assert events[-1][1]["state"] == "answered"
    assert conn.execute("select module_id from chat_session where id = %s", (sid,)).fetchone()["module_id"] == "g1"
    # a chat opened from a quiz item is in test_chat_quiz.py: it needs the learner's answer to that item first


def test_the_prompt_and_the_log_carry_no_name(learner_api, fake_gw, conn):
    fake_gw.responses = [birth_dose_json(conn)]
    ask(learner_api, Q)
    name = conn.execute("select display_name from learner_identity").fetchone()["display_name"]
    call = fake_gw.calls[0]
    assert name not in call["system"] and name not in call["messages"][0]["content"]
    assert "HV-DEMO" not in call["system"] and "HV-DEMO" not in call["messages"][0]["content"]
    assert conn.execute("select learner_pid from chat_session").fetchone()["learner_pid"] == "HV-DEMO-001"
    assert conn.execute("select count(*) c from activity_event where kind = 'chat_turn'").fetchone()["c"] == 1


def test_a_given_title_is_kept_and_a_long_first_question_is_cut(learner_api, fake_gw, conn):
    fake_gw.responses = [birth_dose_json(conn)] * 2
    sid = learner_api.post("/v1/chat/sessions", json={"title": "Tiêm chủng"}).json()["id"]
    learner_api.post(f"/v1/chat/sessions/{sid}/messages", json={"text": Q})
    assert conn.execute("select title from chat_session where id = %s", (sid,)).fetchone()["title"] == "Tiêm chủng"
    long_sid, _ = ask(learner_api, Q + " " + "x" * 200)
    assert len(conn.execute("select title from chat_session where id = %s", (long_sid,)).fetchone()["title"]) == 80


@pytest.mark.parametrize("path", ["/v1/chat/sessions", "/v1/chat/sessions/12/messages", "/v1/passages/tc-p02"])
def test_mock_mode_still_serves_the_examples(mock_client, path):
    assert mock_client.get(path).status_code == 200
