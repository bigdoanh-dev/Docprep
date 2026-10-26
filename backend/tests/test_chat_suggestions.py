"""Suggestions after a chat answer: made by rules from the learner's own record, applied only on a tap."""
from datetime import datetime, timezone

from app.repo import content
from app.schemas.chat import ChatMessageList, ChatSuggestion, FinalEvent, SuggestionAccepted
from app.services import chat as chat_service
from app.services.responses import record_response
from tests.conftest import _issue, birth_dose_json, sse_events, wrong_key

NOW = datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc)      # the test clock's start: 16:00 in Hà Nội
Q = "Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?"            # answered from tc-p02, competency CI-04
TOPIC = "Tiêm phòng/Tiêm chủng trẻ em và người lớn"


def wrong_on_the_topic(conn, learner, n: int = 2) -> None:
    """n wrong answers on CI-04, as from a unit quiz."""
    ids = [r["id"] for r in conn.execute(
        "select id from question where competency_code = 'CI-04' and status = 'approved' order by id limit %s", (n,))]
    assert len(ids) == n
    for question_id in ids:
        record_response(conn, learner, content.approved_question(conn, question_id), wrong_key(conn, question_id), "unit", NOW)
    conn.commit()


def ask(client, conn, fake_gw, text=Q):
    fake_gw.responses = lambda task, messages: birth_dose_json(conn)
    sid = client.post("/v1/chat/sessions", json={}).json()["id"]
    r = client.post(f"/v1/chat/sessions/{sid}/messages", json={"text": text})
    assert r.status_code == 200, r.text
    return sid, sse_events(r.text)


def count(conn, table: str) -> int:
    return conn.execute(f"select count(*) c from {table}").fetchone()["c"]


def offered(client, conn, fake_gw, learner) -> dict[str, dict]:
    wrong_on_the_topic(conn, learner)
    _sid, events = ask(client, conn, fake_gw)
    return {s["kind"]: s for s in events[-1][1]["suggestions"]}


def test_an_answer_on_a_weak_spot_offers_practice_and_tomorrow(learner_api, conn, fake_gw, learner):
    wrong_on_the_topic(conn, learner)
    sid, events = ask(learner_api, conn, fake_gw)
    final = events[-1][1]
    FinalEvent.model_validate(final)
    reason = f"Bạn đã trả lời sai 2 câu về {TOPIC} trong 14 ngày qua."
    assert [(s["kind"], s["label_vi"], s["reason_vi"], s["n_items"]) for s in final["suggestions"]] == [
        ("practise", "Luyện 3 câu đã duyệt", reason, 3), ("add_to_tomorrow", "Thêm vào phiên ngày mai", reason, None)]
    for s in final["suggestions"]:
        ChatSuggestion.model_validate(s)
    rows = conn.execute("select id, message_id, competency_code, accepted_at from suggestion order by id").fetchall()
    assert [r["id"] for r in rows] == [s["id"] for s in final["suggestions"]]
    assert all((r["message_id"], r["competency_code"], r["accepted_at"]) == (final["message_id"], "CI-04", None) for r in rows)
    body = learner_api.get(f"/v1/chat/sessions/{sid}/messages").json()
    ChatMessageList.model_validate(body)
    assert body["items"][1]["suggestions"] == final["suggestions"] and body["items"][0]["suggestions"] == []
    # an offer writes nothing to the learner's study: no set, nothing in tomorrow's session
    assert count(conn, "practice_set") == 0 and count(conn, "session_addition") == 0


def test_the_model_never_sees_the_learners_record(learner_api, conn, fake_gw, learner):
    wrong_on_the_topic(conn, learner)
    calls = []
    fake_gw.responses = lambda task, messages: birth_dose_json(conn)
    ask(learner_api, conn, fake_gw)
    calls = fake_gw.calls
    wrong_stem = conn.execute("select q.stem from item_response r join question q on q.id = r.question_id limit 1").fetchone()["stem"]
    assert len(calls) == 1
    seen = calls[0]["system"] + calls[0]["messages"][0]["content"]
    for secret in ("Minh", "HV-DEMO-001", "DEMO-0001", "trả lời sai", wrong_stem):
        assert secret not in seen


def test_without_a_weak_spot_nothing_is_offered(learner_api, conn, fake_gw, learner):
    _sid, events = ask(learner_api, conn, fake_gw)                                 # no wrong answer at all
    assert events[-1][1]["suggestions"] == [] and count(conn, "suggestion") == 0
    record_response(conn, learner, content.approved_question(conn, "q-dt-01"), wrong_key(conn, "q-dt-01"), "unit", NOW)
    conn.commit()                                                                  # a wrong answer on another topic
    _sid, events = ask(learner_api, conn, fake_gw)
    assert events[-1][1]["suggestions"] == [] and count(conn, "suggestion") == 0


def test_only_an_answer_carries_suggestions(learner_api, conn, fake_gw, learner):
    wrong_on_the_topic(conn, learner)
    fake_gw.responses = lambda task, messages: '{"insufficient": true}'
    sid = learner_api.post("/v1/chat/sessions", json={}).json()["id"]
    events = sse_events(learner_api.post(f"/v1/chat/sessions/{sid}/messages", json={"text": Q}).text)
    assert events[-1][1]["state"] == "insufficient_evidence" and events[-1][1]["suggestions"] == []
    assert count(conn, "suggestion") == 0


def test_accepting_practise_builds_one_set_of_approved_questions(learner_api, conn, fake_gw, learner):
    s = offered(learner_api, conn, fake_gw, learner)["practise"]
    r = learner_api.post(f"/v1/chat/suggestions/{s['id']}/accept")
    assert r.status_code == 200, r.text
    SuggestionAccepted.model_validate(r.json())
    set_id = r.json()["practice_set_id"]
    assert r.json() == {"kind": "practise", "practice_set_id": set_id, "for_date": None}
    row = conn.execute("select source, competency_code, question_ids from practice_set where id = %s", (set_id,)).fetchone()
    assert (row["source"], row["competency_code"], len(row["question_ids"])) == ("chat_suggestion", "CI-04", 3)
    approved = conn.execute("select count(*) c from question where id = any(%s) and status = 'approved'", (row["question_ids"],)).fetchone()["c"]
    view = learner_api.get(f"/v1/practice-sets/{set_id}").json()
    assert approved == 3 and (view["total"], view["source"]) == (3, "chat_suggestion")
    assert view["items"][0]["reason_vi"].startswith("Bạn đã thêm từ Hỏi đáp")
    again = learner_api.post(f"/v1/chat/suggestions/{s['id']}/accept")              # a second tap: the same set
    assert again.json() == r.json() and count(conn, "practice_set") == 1
    assert conn.execute("select accepted_at from suggestion where id = %s", (s["id"],)).fetchone()["accepted_at"] is not None


def test_accepting_tomorrow_adds_the_topic_to_the_day_after_the_tap(learner_api, conn, fake_gw, learner, clock):
    s = offered(learner_api, conn, fake_gw, learner)["add_to_tomorrow"]
    clock.advance(days=1)                                                          # tapped a day after the answer
    learner_api.headers.update(_issue("learner", learner["id"], clock()))
    r = learner_api.post(f"/v1/chat/suggestions/{s['id']}/accept")
    assert r.status_code == 200 and r.json() == {"kind": "add_to_tomorrow", "practice_set_id": None, "for_date": "2026-10-12"}
    again = learner_api.post(f"/v1/chat/suggestions/{s['id']}/accept")
    assert again.json() == r.json() and count(conn, "session_addition") == 1 and count(conn, "practice_set") == 0
    assert conn.execute("select suggestion_id, competency_code from session_addition").fetchone() == {
        "suggestion_id": s["id"], "competency_code": "CI-04"}
    clock.advance(days=1)                                                          # the day it was added to
    learner_api.headers.update(_issue("learner", learner["id"], clock()))
    steps = {x["kind"]: x for x in learner_api.get("/v1/session/today").json()["steps"]}
    assert steps["practice"]["reason_vi"] == "Bạn đã thêm từ Hỏi đáp."


def test_an_offer_already_taken_for_tomorrow_is_not_made_again(learner_api, conn, fake_gw, learner):
    s = offered(learner_api, conn, fake_gw, learner)["add_to_tomorrow"]
    learner_api.post(f"/v1/chat/suggestions/{s['id']}/accept")
    _sid, events = ask(learner_api, conn, fake_gw)
    assert [x["kind"] for x in events[-1][1]["suggestions"]] == ["practise"]


def test_what_cannot_be_accepted_is_refused(api, learner_api, conn, fake_gw, learner, tokens_for_new_learner):
    s = offered(learner_api, conn, fake_gw, learner)["practise"]
    r = api.post(f"/v1/chat/suggestions/{s['id']}/accept", headers=tokens_for_new_learner())
    assert r.status_code == 404 and r.json()["error"]["code"] == "suggestion_not_found"
    assert learner_api.post("/v1/chat/suggestions/999999/accept").json()["error"]["code"] == "suggestion_not_found"
    conn.execute("update question set status = 'retired' where competency_code = 'CI-04'")   # nothing left to ask
    conn.commit()
    r = learner_api.post(f"/v1/chat/suggestions/{s['id']}/accept")
    assert r.status_code == 409 and r.json()["error"]["code"] == "nothing_to_practise" and r.json()["error"]["message_vi"]
    assert count(conn, "practice_set") == 0
    assert conn.execute("select accepted_at from suggestion where id = %s", (s["id"],)).fetchone()["accepted_at"] is None


def test_two_turns_at_once_keep_their_own_answers(learner_api, conn, fake_gw, learner, clock):
    wrong_on_the_topic(conn, learner)
    app = learner_api.app
    fake_gw.responses = lambda task, messages: birth_dose_json(conn)
    sid = learner_api.post("/v1/chat/sessions", json={}).json()["id"]
    session = {"id": sid, "module_id": None}
    turns = [chat_service.answer_events(app.state.pool.connection, app.state.model_slots, fake_gw, learner, session, Q,
                                        False, False, clock()) for _ in range(2)]
    finals, running = [None, None], [0, 1]
    while running:                                                   # one event of each in turn: the two overlap
        for i in list(running):
            event = next(turns[i], None)
            if event is None:
                running.remove(i)
            elif event[0] == "final":
                finals[i] = event[1]
    assert finals[0]["message_id"] != finals[1]["message_id"]
    for final in finals:
        ids = [s["id"] for s in final["suggestions"]]
        owners = {r["message_id"] for r in conn.execute("select message_id from suggestion where id = any(%s)", (ids,))}
        assert len(ids) == 2 and owners == {final["message_id"]}
    assert conn.execute("select count(*) c from chat_message where session_id = %s and role = 'assistant'", (sid,)).fetchone()["c"] == 2
    assert app.state.model_slots.in_use() == 0


def test_mock_mode_still_serves_the_example(mock_client):
    assert mock_client.post("/v1/chat/suggestions/7/accept").status_code == 200


def test_a_failure_while_making_suggestions_keeps_the_answer(learner_api, conn, fake_gw, learner, monkeypatch):
    from app.services import suggestions as suggestions_service

    def broken(*args, **kwargs):
        raise KeyError("a topic without a name")

    wrong_on_the_topic(conn, learner)
    monkeypatch.setattr(suggestions_service, "after_answer", broken)
    _sid, events = ask(learner_api, conn, fake_gw)
    assert [e for e, _ in events][-2:] == ["answer", "final"]
    final = events[-1][1]
    assert final["state"] == "answered" and final["suggestions"] == []
    row = conn.execute("select id, state from chat_message where role = 'assistant'").fetchone()
    assert (row["id"], row["state"]) == (final["message_id"], "answered")


def test_tomorrow_takes_one_topic_from_chat(learner_api, conn, fake_gw, learner):
    wrong_on_the_topic(conn, learner)
    _sid, first = ask(learner_api, conn, fake_gw)
    _sid, second = ask(learner_api, conn, fake_gw)                  # both offered before either was tapped
    a, b = ({s["kind"]: s for s in e[-1][1]["suggestions"]}["add_to_tomorrow"] for e in (first, second))
    assert learner_api.post(f"/v1/chat/suggestions/{a['id']}/accept").status_code == 200
    r = learner_api.post(f"/v1/chat/suggestions/{b['id']}/accept")
    assert r.status_code == 409 and r.json()["error"]["code"] == "tomorrow_taken" and r.json()["error"]["message_vi"]
    assert count(conn, "session_addition") == 1
    assert conn.execute("select accepted_at from suggestion where id = %s", (b["id"],)).fetchone()["accepted_at"] is None
    assert learner_api.post(f"/v1/chat/suggestions/{a['id']}/accept").status_code == 200        # the first, again: still fine
