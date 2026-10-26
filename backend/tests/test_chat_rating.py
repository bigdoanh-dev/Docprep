"""Hữu ích: the learner marks an answer as helpful or not (FR-LRN-06)."""
from tests.conftest import birth_dose_json, make_wrong_unit_answer, sse_events

Q = "Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?"


def answered(client, conn, fake_gw, headers=None) -> tuple[int, int]:
    fake_gw.responses = lambda task, messages: birth_dose_json(conn)
    sid = client.post("/v1/chat/sessions", json={}, headers=headers).json()["id"]
    events = sse_events(client.post(f"/v1/chat/sessions/{sid}/messages", json={"text": Q}, headers=headers).text)
    return sid, events[-1][1]["message_id"]


def helpful(conn, message_id: int):
    return conn.execute("select helpful from chat_message where id = %s", (message_id,)).fetchone()["helpful"]


def test_the_last_rating_of_an_answer_is_kept_and_shown(learner_api, conn, fake_gw):
    sid, message_id = answered(learner_api, conn, fake_gw)
    assert helpful(conn, message_id) is None
    r = learner_api.post(f"/v1/messages/{message_id}/rating", json={"helpful": True})
    assert r.status_code == 200 and r.json() == {"ok": True} and helpful(conn, message_id) is True
    assert learner_api.get(f"/v1/chat/sessions/{sid}/messages").json()["items"][1]["helpful"] is True
    assert learner_api.post(f"/v1/messages/{message_id}/rating", json={"helpful": False}).status_code == 200
    assert helpful(conn, message_id) is False
    assert learner_api.get(f"/v1/chat/sessions/{sid}/messages").json()["items"][1]["helpful"] is False


def test_the_tutors_explanation_can_be_rated_too(learner_api, conn, fake_gw):
    make_wrong_unit_answer(learner_api)
    fake_gw.responses = ['{"evidence":[{"passage_id":"dt-p01","quote":"50 ÷ 2.000 = 0,025 = 2,5%"}],"claims":[{"text":"Mẫu số '
                         'đúng là 2.000 dân nên kết quả là 2,5%.","passage_ids":["dt-p01"]}]}']
    message_id = sse_events(learner_api.post("/v1/items/q-dt-01/explain").text)[-1][1]["message_id"]
    assert learner_api.post(f"/v1/messages/{message_id}/rating", json={"helpful": True}).status_code == 200
    assert helpful(conn, message_id) is True


def test_only_ones_own_answers_can_be_rated(api, learner_api, conn, fake_gw, tokens_for_new_learner):
    sid, message_id = answered(learner_api, conn, fake_gw)
    own_question = conn.execute("select id from chat_message where session_id = %s and role = 'user'", (sid,)).fetchone()["id"]
    other = tokens_for_new_learner()
    _sid, theirs = answered(api, conn, fake_gw, other)
    for target in (own_question, theirs, 999_999):
        r = learner_api.post(f"/v1/messages/{target}/rating", json={"helpful": True})
        assert r.status_code == 404 and r.json()["error"]["code"] == "message_not_found" and r.json()["error"]["message_vi"]
    assert helpful(conn, theirs) is None and helpful(conn, own_question) is None and helpful(conn, message_id) is None
    assert learner_api.post(f"/v1/messages/{message_id}/rating", json={}).status_code == 422


def test_mock_mode_still_serves_the_example(mock_client):
    assert mock_client.post("/v1/messages/58/rating", json={"helpful": True}).json() == {"ok": True}
