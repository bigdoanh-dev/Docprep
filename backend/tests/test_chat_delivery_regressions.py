"""Hồi quy lỗi gửi trùng chat và mở gia sư khi bài thi chưa kết thúc."""
from uuid import uuid4

from tests.conftest import sse_events


def test_chat_key_replays_exact_stream_and_rejects_changed_payload(learner_api, conn):
    sid = learner_api.post("/v1/chat/sessions", json={}).json()["id"]
    path = f"/v1/chat/sessions/{sid}/messages"
    headers = {"Idempotency-Key": str(uuid4())}
    data = {"text": "Con tôi sốt cao cần uống thuốc gì?"}  # Deterministic decline, no model dependency.
    first = learner_api.post(path, json=data, headers=headers)
    second = learner_api.post(path, json=data, headers=headers)
    assert first.status_code == second.status_code == 200
    assert sse_events(first.text) == sse_events(second.text)
    assert conn.execute("select count(*) n from chat_message where session_id=%s", (sid,)).fetchone()["n"] == 2
    conflict = learner_api.post(path, json={"text": "Một câu hỏi khác"}, headers=headers)
    assert (conflict.status_code, conflict.json()["error"]["code"]) == (409, "idempotency_conflict")


def test_exam_blocks_generic_chat_and_cached_replay_then_submit_reopens(learner_api, conn):
    sid = learner_api.post("/v1/chat/sessions", json={}).json()["id"]
    path = f"/v1/chat/sessions/{sid}/messages"
    data = {"text": "Con tôi sốt cao cần uống thuốc gì?"}
    headers = {"Idempotency-Key": str(uuid4())}
    assert learner_api.post(path, json=data, headers=headers).status_code == 200
    attempt = learner_api.post("/v1/exams/de-thi-thu-1/attempts", json={}).json()
    for key in [headers, {"Idempotency-Key": str(uuid4())}]:
        r = learner_api.post(path, json=data, headers=key)
        assert (r.status_code, r.json()["error"]["code"]) == (409, "tutor_unavailable")
    assert conn.execute("select count(*) n from chat_message where session_id=%s", (sid,)).fetchone()["n"] == 2
    assert learner_api.post(f"/v1/attempts/{attempt['attempt_id']}/submit").status_code == 200
    assert learner_api.post(path, json=data, headers={"Idempotency-Key": str(uuid4())}).status_code == 200


def test_exam_deadline_reopens_chat_without_inventing_a_submission(learner_api, conn, clock):
    sid = learner_api.post("/v1/chat/sessions", json={}).json()["id"]
    attempt = learner_api.post("/v1/exams/de-thi-thu-1/attempts", json={}).json()
    from datetime import timedelta
    conn.execute("update exam_attempt set deadline_at=%s where id=%s",
                 (clock() - timedelta(seconds=1), attempt["attempt_id"]))
    conn.commit()
    response = learner_api.post(f"/v1/chat/sessions/{sid}/messages", json={"text": "Con tôi sốt cao uống thuốc gì?"})
    assert response.status_code == 200
    assert conn.execute("select submitted_at from exam_attempt where id=%s", (attempt["attempt_id"],)).fetchone()["submitted_at"] is None
