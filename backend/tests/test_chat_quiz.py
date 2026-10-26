"""Hỏi gia sư · từ câu quiz: a chat opened from a quiz item explains the chosen option first, grounded
in the item's own sources."""
from datetime import datetime, timezone

from app.repo import content
from app.services.responses import record_response
from tests.conftest import make_wrong_unit_answer, sse_events, wrong_key

NOW = datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc)
ANSWER = ('{"evidence":[{"passage_id":"dt-p01","quote":"50 ÷ 2.000 = 0,025 = 2,5%"}],"claims":[{"text":"Bạn chọn 5%, '
          'tức là lấy 50 ÷ 1.000; mẫu số đúng là 2.000 dân nên kết quả là 2,5%.","passage_ids":["dt-p01"]}]}')
ASKED = "Vì sao 5% sai?"


def open_from_item(client) -> int:
    make_wrong_unit_answer(client)                                        # q-dt-01, chose b (5%)
    r = client.post("/v1/chat/sessions", json={"question_id": "q-dt-01"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def send(client, sid, text):
    r = client.post(f"/v1/chat/sessions/{sid}/messages", json={"text": text})
    assert r.status_code == 200, r.text
    return sse_events(r.text)


def sessions(conn) -> int:
    return conn.execute("select count(*) c from chat_session where kind = 'chat'").fetchone()["c"]


def test_the_first_turn_is_about_the_item_and_what_the_learner_chose(learner_api, conn, fake_gw):
    sid = open_from_item(learner_api)
    fake_gw.responses = [ANSWER]
    events = send(learner_api, sid, ASKED)
    call = fake_gw.calls[0]
    assert len(fake_gw.calls) == 1 and (call["task"], call["prompt_version"]) == ("quiz_chat", "quiz-chat-v1")
    user = call["messages"][0]["content"]
    assert "Một xã có 2.000 dân" in user and user.count("ghi chú của chuyên gia") == 4
    assert "Học viên đã chọn: b" in user and f"Câu hỏi của học viên: {ASKED}" in user and "[dt-p01]" in user
    for secret in ("Minh", "HV-DEMO-001", "DEMO-0001"):
        assert secret not in user and secret not in call["system"]
    assert "chose" in call["system"]                                      # the prompt asks for the chosen option's mistake first
    assert [d["kind"] for e, d in events if e == "step" and d["status"] == "done"] == ["get_item", "read", "check"]
    answer, final = events[-2][1], events[-1][1]
    assert final["state"] == "answered" and answer["citations"][0]["passage_id"] == "dt-p01"
    row = conn.execute("select state, prompt_version, trace from chat_message where session_id = %s and role = 'assistant'", (sid,)).fetchone()
    assert (row["state"], row["prompt_version"]) == ("answered", "quiz-chat-v1") and [s["kind"] for s in row["trace"]] == ["get_item", "read", "check"]
    listed = learner_api.get("/v1/chat/sessions").json()["items"]
    assert [(s["id"], s["title"]) for s in listed] == [(sid, ASKED)]


def test_a_quiz_chat_offers_practice_on_the_items_topic(learner_api, conn, fake_gw):
    sid = open_from_item(learner_api)
    fake_gw.responses = [ANSWER]
    final = send(learner_api, sid, ASKED)[-1][1]
    assert [s["kind"] for s in final["suggestions"]] == ["practise", "add_to_tomorrow"]
    assert final["suggestions"][0]["reason_vi"] == "Bạn đã trả lời sai 1 câu về Khái niệm cơ bản của y học dự phòng trong 14 ngày qua."


def test_later_turns_are_ordinary_chat(learner_api, conn, fake_gw):
    sid = open_from_item(learner_api)
    fake_gw.responses = [ANSWER, '{"insufficient": true}']
    send(learner_api, sid, ASKED)
    events = send(learner_api, sid, "Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?")
    assert [c["task"] for c in fake_gw.calls] == ["quiz_chat", "answer"]
    assert "search" in [d["kind"] for e, d in events if e == "step"] and "Học viên đã chọn" not in fake_gw.calls[1]["messages"][0]["content"]


def test_a_patient_question_is_declined_before_anything_else(learner_api, conn, fake_gw):
    sid = open_from_item(learner_api)
    events = send(learner_api, sid, "Con tôi sốt 39 độ nên uống thuốc gì?")
    assert [e for e, _ in events] == ["answer", "final"] and events[-1][1]["state"] == "declined" and fake_gw.calls == []


def test_a_chat_cannot_be_opened_from_an_item_that_is_not_ready(learner_api, conn, learner, clock):
    before = sessions(conn)

    def refused(question_id, status, code):
        r = learner_api.post("/v1/chat/sessions", json={"question_id": question_id})
        assert (r.status_code, r.json()["error"]["code"]) == (status, code) and r.json()["error"]["message_vi"], r.text

    refused("q-nope", 404, "question_not_found")
    refused("q-dt-07", 409, "not_answered")                              # never answered by this learner
    record_response(conn, learner, content.approved_question(conn, "q-dt-07"), wrong_key(conn, "q-dt-07"), "unit", NOW)
    conn.commit()
    attempt = learner_api.post("/v1/exams/de-thi-thu-1/attempts", json={}).json()      # q-dt-07 is in this exam
    refused("q-dt-07", 409, "tutor_unavailable")
    assert sessions(conn) == before
    learner_api.post(f"/v1/attempts/{attempt['attempt_id']}/submit")
    assert learner_api.post("/v1/chat/sessions", json={"question_id": "q-dt-07"}).status_code == 200


def test_mock_mode_still_serves_the_example(mock_client):
    assert mock_client.post("/v1/chat/sessions", json={"question_id": "q-dt-01"}).status_code == 200
