"""Hỏi lại: a question that names an ambiguous term is asked back, with the senses as ready questions."""
from app.schemas.chat import ChatMessageList, ClarifyOption, FinalEvent
from tests.conftest import sse_events

AMBIGUOUS = "Tỷ lệ mắc tính thế nào?"
OPTIONS = [{"term": "tỷ lệ hiện mắc", "label_vi": "Tỷ lệ hiện mắc", "query": "Tỷ lệ hiện mắc tính thế nào?"},
           {"term": "tỷ lệ mới mắc", "label_vi": "Tỷ lệ mới mắc", "query": "Tỷ lệ mới mắc tính thế nào?"}]


def new_session(client, headers=None) -> int:
    return client.post("/v1/chat/sessions", json={}, headers=headers).json()["id"]


def send(client, sid, text, headers=None, **extra):
    return client.post(f"/v1/chat/sessions/{sid}/messages", json={"text": text, **extra}, headers=headers)


def messages(conn) -> int:
    return conn.execute("select count(*) c from chat_message").fetchone()["c"]


def test_an_ambiguous_term_is_asked_back_without_search_or_model(learner_api, conn, fake_gw):
    sid = new_session(learner_api)
    events = sse_events(send(learner_api, sid, AMBIGUOUS).text)
    assert [e for e, _ in events] == ["answer", "final"]
    answer, final = events[0][1], events[1][1]
    FinalEvent.model_validate(final)
    assert final["state"] == "needs_clarification" and answer["text"] == 'Bạn muốn hỏi về nghĩa nào của "tỷ lệ mắc"?'
    assert final["clarify_options"] == OPTIONS and final["trace_summary"] is None and answer["citations"] == []
    for option in final["clarify_options"]:
        ClarifyOption.model_validate(option)
    assert fake_gw.calls == []
    row = conn.execute("select state, trace, retrieved_passage_ids, clarify_options from chat_message where role = 'assistant'").fetchone()
    assert row == {"state": "needs_clarification", "trace": None, "retrieved_passage_ids": [], "clarify_options": OPTIONS}
    body = learner_api.get(f"/v1/chat/sessions/{sid}/messages").json()
    ChatMessageList.model_validate(body)
    assert body["items"][1]["clarify_options"] == OPTIONS and body["items"][1]["state"] == "needs_clarification"


def test_a_question_that_names_the_sense_is_not_asked_back(learner_api, fake_gw):
    fake_gw.responses = ['{"insufficient": true}']
    events = sse_events(send(learner_api, new_session(learner_api), "Tỷ lệ hiện mắc tính thế nào?").text)
    assert events[-1][1]["state"] != "needs_clarification" and len(fake_gw.calls) == 1


def test_tapping_an_option_is_answered_and_remembers_what_it_clarifies(learner_api, conn, fake_gw):
    sid = new_session(learner_api)
    asked_back = sse_events(send(learner_api, sid, AMBIGUOUS).text)[-1][1]
    fake_gw.responses = ['{"insufficient": true}']
    events = sse_events(send(learner_api, sid, OPTIONS[1]["query"], clarifies_message_id=asked_back["message_id"]).text)
    assert events[-1][1]["state"] == "insufficient_evidence" and "search" in [d.get("kind") for e, d in events if e == "step"]
    assert len(fake_gw.calls) == 1 and "Tỷ lệ mới mắc tính thế nào?" in fake_gw.calls[0]["messages"][0]["content"]
    rows = conn.execute("select role, clarifies_message_id from chat_message where session_id = %s order by id", (sid,)).fetchall()
    assert [(r["role"], r["clarifies_message_id"]) for r in rows] == [
        ("user", None), ("assistant", None), ("user", asked_back["message_id"]), ("assistant", None)]


def test_a_clarifying_turn_is_never_asked_back_again(learner_api, fake_gw):
    sid = new_session(learner_api)
    asked_back = sse_events(send(learner_api, sid, AMBIGUOUS).text)[-1][1]
    fake_gw.responses = ['{"insufficient": true}']
    events = sse_events(send(learner_api, sid, AMBIGUOUS, clarifies_message_id=asked_back["message_id"]).text)
    assert events[-1][1]["state"] == "insufficient_evidence" and events[-1][1]["clarify_options"] == []


def test_what_is_not_a_clarification_of_this_session_is_refused(api, learner_api, conn, fake_gw, tokens_for_new_learner):
    sid = new_session(learner_api)
    asked_back = sse_events(send(learner_api, sid, AMBIGUOUS).text)[-1][1]["message_id"]
    declined = sse_events(send(learner_api, sid, "Con tôi sốt 39 độ nên uống thuốc gì?").text)[-1][1]["message_id"]
    own_question = conn.execute("select min(id) i from chat_message where session_id = %s and role = 'user'", (sid,)).fetchone()["i"]
    elsewhere = new_session(learner_api)
    other = tokens_for_new_learner()
    theirs = new_session(api, other)
    their_question = sse_events(send(api, theirs, AMBIGUOUS, other).text)[-1][1]["message_id"]
    before = messages(conn)

    def refused(session_id, message_id, status, code):
        r = send(learner_api, session_id, OPTIONS[0]["query"], clarifies_message_id=message_id)
        assert (r.status_code, r.json()["error"]["code"]) == (status, code) and r.json()["error"]["message_vi"], r.text

    refused(sid, 999_999, 404, "message_not_found")                 # no such message
    refused(sid, own_question, 404, "message_not_found")            # the learner's own question, not an answer
    refused(sid, their_question, 404, "message_not_found")          # another learner's
    refused(elsewhere, asked_back, 404, "message_not_found")        # another session's
    refused(sid, declined, 422, "not_a_clarification")              # an answer that asked nothing back
    assert messages(conn) == before and fake_gw.calls == []
