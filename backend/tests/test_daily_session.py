"""Phiên hôm nay: built by rules once per local day, stored, and marked done as the learner goes."""
import threading
from datetime import datetime, timedelta, timezone

from psycopg.types.json import Jsonb

from app.engine.scheduler import new_state
from app.repo import content
from app.schemas.session import SessionToday
from app.services import session
from app.services.responses import record_response
from tests.conftest import _issue, _test_conn, correct_key, make_wrong_unit_answer, walk_unit, wrong_key

NOW = datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc)      # the test clock's start: 16:00 in Hà Nội
FND = "Khái niệm cơ bản của y học dự phòng"


def record_wrong(conn, learner, question_id: str, now: datetime = NOW) -> None:
    """A wrong unit-quiz answer, committed."""
    record_response(conn, learner, content.approved_question(conn, question_id), wrong_key(conn, question_id), "unit", now)
    conn.commit()


def add_due_cards(conn, learner, n: int) -> None:
    for offset in range(n):
        conn.execute(
            "insert into card(learner_id, source_question_id, source_context, front, back, citation, fsrs_card, due_at) "
            "select %s, id, 'unit', stem, 'Đáp án', 'Nguồn', %s, %s from question order by id offset %s limit 1",
            (learner["id"], Jsonb(new_state(NOW)), NOW - timedelta(days=1), offset))
    conn.commit()


def sign_in_again(client, learner, clock) -> None:
    client.headers.update(_issue("learner", learner["id"], clock()))    # access tokens last 30 minutes


def step(body: dict, kind: str) -> dict:
    return next(s for s in body["steps"] if s["kind"] == kind)


def test_a_new_learner_has_only_the_continue_step(learner_api):
    body = learner_api.get("/v1/session/today").json()
    SessionToday.model_validate(body)
    assert body["local_date"] == "2026-10-10"
    assert [(s["kind"], s["count"], s["unit_id"], s["done"]) for s in body["steps"]] == [("continue", 6, "u-dt-01", False)]
    assert body["steps"][0]["reason_vi"] == "Học tiếp học phần đang ưu tiên: Sức khỏe quần thể và dự phòng."
    assert body["total_minutes"] == 9                                      # 6 items × 90 s
    r = learner_api.get("/v1/session/today/practice")
    assert r.status_code == 404 and r.json()["error"]["code"] == "no_practice_today"
    for path, body in [("/v1/session/today/practice/responses", {"question_id": "q-dt-01", "chosen": "a"}),
                       ("/v1/session/today/practice/complete", None)]:
        assert learner_api.post(path, json=body).json()["error"]["code"] == "no_practice_today"


def test_a_wrong_answer_yesterday_gives_all_three_steps_today(learner_api, conn, clock, learner):
    make_wrong_unit_answer(learner_api)                                    # one wrong answer on FND, one card
    clock.advance(days=1)
    sign_in_again(learner_api, learner, clock)
    body = learner_api.get("/v1/session/today").json()
    cards, practice_step, cont = body["steps"]
    assert (cards["kind"], cards["count"], cards["minutes"]) == ("cards", 1, 1)
    assert cards["reason_vi"] == "1 thẻ đến hạn hôm nay, 1 thẻ quá hạn ôn trước."
    assert (practice_step["kind"], practice_step["count"], practice_step["minutes"]) == ("practice", 6, 8)
    assert practice_step["reason_vi"] == f"Bạn sai 1 câu về {FND} trong 7 ngày qua."
    assert practice_step["practice_set_id"] == conn.execute("select id from practice_set").fetchone()["id"]
    assert (cont["kind"], cont["unit_id"], cont["count"]) == ("continue", "u-dt-01", 6)     # opened yesterday: 6 of 7 left
    assert cards["practice_set_id"] is None and cont["practice_set_id"] is None and practice_step["unit_id"] is None
    assert body["total_minutes"] == sum(s["minutes"] for s in body["steps"]) == 1 + 8 + 9
    view = learner_api.get("/v1/session/today/practice").json()
    assert view["id"] == practice_step["practice_set_id"] and view["source"] == "session"
    assert "q-dt-01" not in [i["question_id"] for i in view["items"]]      # seen yesterday


def test_the_session_does_not_change_during_the_day(learner_api, conn, clock, learner):
    make_wrong_unit_answer(learner_api)
    first = learner_api.get("/v1/session/today").json()
    record_wrong(conn, learner, "q-tc-01")                                 # a heavier weak spot appears after the build
    record_wrong(conn, learner, "q-tc-02")
    again = learner_api.get("/v1/session/today").json()
    key = lambda body: [(s["kind"], s["count"], s["minutes"], s["reason_vi"], s["practice_set_id"]) for s in body["steps"]]
    assert key(again) == key(first) and again["local_date"] == first["local_date"]
    assert conn.execute("select count(*) c from daily_session").fetchone()["c"] == 1
    assert conn.execute("select count(*) c from practice_set").fetchone()["c"] == 1


def test_after_midnight_there_is_a_new_session_and_yesterdays_set_still_opens(learner_api, conn, clock, learner):
    make_wrong_unit_answer(learner_api)
    clock.now = datetime(2026, 10, 10, 16, 50, tzinfo=timezone.utc)        # 23:50 in Hà Nội
    sign_in_again(learner_api, learner, clock)
    before = learner_api.get("/v1/session/today").json()
    clock.advance(minutes=20)                                              # 00:10 the next day
    after = learner_api.get("/v1/session/today").json()
    assert (before["local_date"], after["local_date"]) == ("2026-10-10", "2026-10-11")
    old_set, new_set = step(before, "practice")["practice_set_id"], step(after, "practice")["practice_set_id"]
    assert old_set != new_set
    assert learner_api.get(f"/v1/practice-sets/{old_set}").status_code == 200
    assert learner_api.post(f"/v1/practice-sets/{old_set}/complete").status_code == 200
    assert learner_api.get("/v1/session/today/practice").json()["id"] == new_set
    assert step(learner_api.get("/v1/session/today").json(), "practice")["done"] is False    # yesterday's set is not today's


def test_two_requests_at_once_build_one_session(conn, learner):
    record_wrong(conn, learner, "q-dt-01")
    results, errors = [], []

    def open_session():
        try:
            with _test_conn() as c:
                results.append(session.today(c, learner, NOW))
        except Exception as e:  # noqa: BLE001 — the test reports whatever went wrong
            errors.append(e)

    threads = [threading.Thread(target=open_session) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(20)
    assert errors == [] and len(results) == 2 and results[0] == results[1]
    counts = conn.execute("select (select count(*) from daily_session) s, (select count(*) from practice_set) p").fetchone()
    assert counts == {"s": 1, "p": 1}


def test_the_steps_are_marked_done_as_the_learner_goes(learner_api, conn, clock, learner):
    make_wrong_unit_answer(learner_api)
    clock.advance(days=1)
    sign_in_again(learner_api, learner, clock)
    learner_api.get("/v1/session/today")
    card = learner_api.get("/v1/cards/due").json()["items"][0]
    learner_api.post(f"/v1/cards/{card['id']}/reviews", json={"rating": 3})
    assert step(learner_api.get("/v1/session/today").json(), "cards")["done"] is True
    for item in learner_api.get("/v1/session/today/practice").json()["items"]:
        r = learner_api.post("/v1/session/today/practice/responses",
                             json={"question_id": item["question_id"], "chosen": correct_key(conn, item["question_id"])},
                             headers={"Idempotency-Key": f"k-{item['question_id']}"})
        assert r.status_code == 200 and r.json()["correct"] is True
    summary = learner_api.post("/v1/session/today/practice/complete").json()
    assert summary["graded"] == {"correct": 6, "total": 6}
    walk_unit(learner_api, "u-dt-01")
    steps = {s["kind"]: s["done"] for s in learner_api.get("/v1/session/today").json()["steps"]}
    assert steps == {"cards": True, "practice": True, "continue": True}
    done = [e["ref_id"] for e in conn.execute("select ref_id from activity_event where kind = 'session_step_completed' order by id")]
    assert done == ["cards", "practice", "continue"]
    assert learner_api.post("/v1/session/today/practice/complete").json() == summary      # a repeat adds no event
    assert conn.execute("select count(*) c from activity_event where kind = 'session_step_completed'").fetchone()["c"] == 3


def test_work_outside_the_session_marks_no_step(learner_api, conn, learner):
    learner_api.get("/v1/session/today")                                   # today: only "continue" on u-dt-01
    walk_unit(learner_api, "u-dt-02")                                      # another unit than the session's
    assert conn.execute("select count(*) c from activity_event where kind = 'session_step_completed'").fetchone()["c"] == 0
    assert step(learner_api.get("/v1/session/today").json(), "continue")["done"] is False


def test_a_topic_added_from_chat_is_the_practice_step(learner_api, conn, learner):
    conn.execute("insert into session_addition(learner_id, for_date, competency_code) values (%s, '2026-10-10', 'CI-04')",
                 (learner["id"],))
    conn.commit()
    body = learner_api.get("/v1/session/today").json()
    assert step(body, "practice")["reason_vi"] == "Bạn đã thêm từ Hỏi đáp."
    view = learner_api.get("/v1/session/today/practice").json()
    assert view["competency_code"] == "CI-04" and view["total"] == 6
    assert view["items"][0]["reason_vi"] == "Bạn đã thêm từ Hỏi đáp · bạn chưa gặp câu này trong 14 ngày."


def test_the_weak_spot_is_the_topic_with_most_wrong_answers_in_seven_days(learner_api, conn, clock, learner):
    record_wrong(conn, learner, "q-tc-01", NOW - timedelta(days=8))        # CI-04, too long ago to count
    record_wrong(conn, learner, "q-dt-01")                                 # FND, today
    body = learner_api.get("/v1/session/today").json()
    assert step(body, "practice")["reason_vi"] == f"Bạn sai 1 câu về {FND} trong 7 ngày qua."


def test_the_daily_review_cap_limits_the_cards_step(learner_api, conn, learner):
    add_due_cards(conn, learner, 3)
    conn.execute("update learner set max_reviews_per_day = 2")
    conn.commit()
    cards = learner_api.get("/v1/session/today").json()["steps"][0]
    assert (cards["kind"], cards["count"], cards["reason_vi"]) == ("cards", 2, "2 trong 3 thẻ đến hạn hôm nay, 2 thẻ quá hạn ôn trước.")


def test_a_suspended_card_does_not_hold_the_cards_step_open(learner_api, conn, learner):
    add_due_cards(conn, learner, 2)
    learner_api.get("/v1/session/today")
    first, second = learner_api.get("/v1/cards/due").json()["items"]
    learner_api.patch(f"/v1/cards/{first['id']}", json={"suspended": True})
    assert step(learner_api.get("/v1/session/today").json(), "cards")["done"] is False
    learner_api.post(f"/v1/cards/{second['id']}/reviews", json={"rating": 3})
    assert step(learner_api.get("/v1/session/today").json(), "cards")["done"] is True
    assert conn.execute("select count(*) c from activity_event where kind = 'session_step_completed'").fetchone()["c"] == 1


def test_another_learner_has_their_own_session(api, learner_api, tokens_for_new_learner):
    make_wrong_unit_answer(learner_api)
    learner_api.get("/v1/session/today")
    other = api.get("/v1/session/today", headers=tokens_for_new_learner()).json()
    assert [s["kind"] for s in other["steps"]] == ["continue"]


def test_mock_mode_still_serves_the_examples(mock_client):
    assert mock_client.get("/v1/session/today").status_code == 200
    assert mock_client.get("/v1/session/today/practice").status_code == 200
