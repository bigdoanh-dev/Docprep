"""Tiến độ · Nhịp học: study time from the activity log, memory from the learner's cards."""
import json
import re
from datetime import datetime, timedelta, timezone

from psycopg.types.json import Jsonb

from app import events
from app.engine.scheduler import new_state
from app.schemas.progress import ProgressRhythm
from app.services import practice
from tests.conftest import answer_all, correct_key, make_wrong_unit_answer, walk_unit

NOW = datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc)      # Saturday, 16:00 in Hà Nội
PID = "HV-DEMO-001"
PREDICTION = re.compile(r"dự đoán|xác suất|khả năng đỗ|khả năng đậu|điểm dự kiến|xu hướng", re.IGNORECASE)


def rhythm(client) -> dict:
    r = client.get("/v1/progress/rhythm")
    assert r.status_code == 200, r.text
    return r.json()


def log(conn, at: datetime, minutes: int = 1) -> None:
    events.record(conn, PID, "unit_response", at, duration_ms=minutes * 60_000)
    conn.commit()


def add_card(conn, learner, question_id: str, due_at: datetime) -> None:
    conn.execute(
        "insert into card(learner_id, source_question_id, source_context, front, back, citation, fsrs_card, due_at) "
        "select %s, id, 'unit', stem, 'Đáp án', 'Nguồn', %s, %s from question where id = %s",
        (learner["id"], Jsonb(new_state(NOW)), due_at, question_id))
    conn.commit()


def test_a_new_learner_gets_empty_blocks(learner_api):
    body = rhythm(learner_api)
    ProgressRhythm.model_validate(body)
    assert body["week"] == {"minutes": 0, "previous_minutes": 0, "study_days": 0, "days_elapsed": 6}
    assert len(body["heatmap"]) == 56 and body["heatmap"][-1] == {"date": "2026-10-10", "minutes": 0}
    assert body["heatmap"][0]["date"] == "2026-08-16" and all(d["minutes"] == 0 for d in body["heatmap"])
    assert body["memory"] == {"recall_rate": None, "window_days": 30, "reviews": 0, "new": 0, "learning": 0,
                              "mastered": 0, "due_today": 0}
    assert body["curve"] == [] and body["recall_by_module"] == [] and body["activity"] == []
    assert [d["date"] for d in body["due_forecast"]] == [f"2026-10-{10 + i}" for i in range(7)]
    assert all(d["count"] == 0 for d in body["due_forecast"])


def test_time_is_counted_where_it_was_spent(learner_api, clock):
    learner_api.get("/v1/units/u-dt-01/next")
    learner_api.post("/v1/units/u-dt-01/advance", json={"unit_item_id": "u1-c1"})
    learner_api.post("/v1/units/u-dt-01/responses", json={"unit_item_id": "u1-q1", "chosen": "b", "time_ms": 120_000})
    card = learner_api.get("/v1/cards/due").json()["items"][0]
    learner_api.post(f"/v1/cards/{card['id']}/reviews", json={"rating": 3, "time_ms": 60_000})
    body = rhythm(learner_api)
    assert (body["week"]["minutes"], body["week"]["study_days"], body["heatmap"][-1]["minutes"]) == (3, 1, 3)
    attempt = learner_api.post("/v1/exams/de-thi-thu-1/attempts", json={}).json()
    clock.advance(seconds=90)
    learner_api.post(f"/v1/attempts/{attempt['attempt_id']}/submit")
    assert rhythm(learner_api)["week"]["minutes"] == 5                     # 270 s in the day, rounded half up


def test_days_and_weeks_are_the_learners_local_ones(learner_api, conn):
    log(conn, datetime(2026, 10, 9, 16, 30, tzinfo=timezone.utc))          # Friday 23:30 in Hà Nội
    log(conn, datetime(2026, 10, 9, 17, 30, tzinfo=timezone.utc), 2)       # Saturday 00:30
    log(conn, datetime(2026, 10, 4, 5, 0, tzinfo=timezone.utc), 7)         # the Sunday before: last week
    log(conn, datetime(2026, 10, 4, 17, 30, tzinfo=timezone.utc), 4)       # Monday 00:30: this week
    body = rhythm(learner_api)
    days = {d["date"]: d["minutes"] for d in body["heatmap"]}
    assert (days["2026-10-09"], days["2026-10-10"], days["2026-10-04"], days["2026-10-05"]) == (1, 2, 7, 4)
    assert body["week"] == {"minutes": 7, "previous_minutes": 7, "study_days": 3, "days_elapsed": 6}


def test_memory_follows_the_cards(learner_api, conn, clock):
    make_wrong_unit_answer(learner_api)
    memory = rhythm(learner_api)["memory"]
    assert (memory["new"], memory["learning"], memory["mastered"], memory["due_today"], memory["recall_rate"]) == (1, 0, 0, 1, None)
    card = learner_api.get("/v1/cards/due").json()["items"][0]
    learner_api.post(f"/v1/cards/{card['id']}/reviews", json={"rating": 3})
    memory = rhythm(learner_api)["memory"]
    assert (memory["new"], memory["learning"], memory["reviews"], memory["recall_rate"], memory["due_today"]) == (0, 1, 1, 1.0, 0)
    clock.advance(minutes=11)
    learner_api.post(f"/v1/cards/{card['id']}/reviews", json={"rating": 1})
    assert rhythm(learner_api)["memory"]["recall_rate"] == 0.5
    conn.execute("update card set suspended = true")
    conn.commit()
    memory = rhythm(learner_api)["memory"]
    assert (memory["new"], memory["learning"], memory["mastered"], memory["due_today"]) == (0, 0, 0, 0)


def test_the_curve_and_recall_by_hoc_phan_come_from_real_reviews(learner_api, clock):
    make_wrong_unit_answer(learner_api)
    assert rhythm(learner_api)["curve"] == [] and rhythm(learner_api)["recall_by_module"] == []     # not reviewed yet
    card = learner_api.get("/v1/cards/due").json()["items"][0]
    learner_api.post(f"/v1/cards/{card['id']}/reviews", json={"rating": 3})
    clock.advance(minutes=11)
    learner_api.post(f"/v1/cards/{card['id']}/reviews", json={"rating": 3})
    body = rhythm(learner_api)
    assert [p["kind"] for p in body["curve"]] == ["review", "decay", "review", "decay", "projected"]
    assert all(0 <= p["recall"] <= 1 for p in body["curve"]) and body["curve"][-1]["date"] == "2026-10-17"
    recall = body["recall_by_module"]
    assert [(r["module_id"], r["short_name"]) for r in recall] == [("g1", "Sức khỏe quần thể và dự phòng")]
    assert 0 <= recall[0]["in_7_days"] <= recall[0]["now"] <= 1


def test_the_forecast_groups_by_local_day_and_today_holds_the_overdue(learner_api, conn, learner):
    add_card(conn, learner, "q-dt-01", NOW - timedelta(days=3))            # overdue
    add_card(conn, learner, "q-dt-02", NOW + timedelta(days=2))            # the day after tomorrow
    add_card(conn, learner, "q-dt-03", datetime(2026, 10, 11, 17, 30, tzinfo=timezone.utc))     # Monday 00:30 local
    add_card(conn, learner, "q-dt-04", NOW + timedelta(days=1))
    conn.execute("update card set suspended = true where source_question_id = 'q-dt-04'")
    conn.commit()
    assert [d["count"] for d in rhythm(learner_api)["due_forecast"]] == [1, 0, 2, 0, 0, 0, 0]


def test_this_weeks_activity_lists_what_was_done_newest_first(learner_api, conn, clock, learner):
    walk_unit(learner_api, "u-dt-02")                                      # a unit finished
    clock.advance(minutes=1)
    built = practice.build(conn, learner, "session", "CI-04", 1, False, clock())
    conn.commit()
    for question_id in built["question_ids"][:2]:
        learner_api.post(f"/v1/practice-sets/{built['id']}/responses",
                         json={"question_id": question_id, "chosen": correct_key(conn, question_id), "time_ms": 60_000})
    learner_api.post(f"/v1/practice-sets/{built['id']}/complete")
    clock.advance(minutes=1)
    sid = learner_api.post("/v1/chat/sessions", json={}).json()["id"]
    learner_api.post(f"/v1/chat/sessions/{sid}/messages", json={"text": "Con tôi sốt 39 độ nên uống thuốc gì?"})
    clock.advance(minutes=1)
    attempt = learner_api.post("/v1/exams/de-thi-thu-1/attempts", json={}).json()
    answer_all(learner_api, attempt, wrong=2)
    clock.advance(minutes=2)
    learner_api.post(f"/v1/attempts/{attempt['attempt_id']}/submit")
    clock.advance(minutes=1)
    for card in learner_api.get("/v1/cards/due").json()["items"]:
        learner_api.post(f"/v1/cards/{card['id']}/reviews", json={"rating": 3, "time_ms": 30_000})
    log(conn, NOW - timedelta(days=9))                                     # last week: not listed
    activity = rhythm(learner_api)["activity"]
    assert [(a["kind"], a["title"], a["minutes"], a["result_vi"]) for a in activity] == [
        ("cards", "Ôn 2 thẻ", 1, "2/2"),
        ("exam", "Đề thi thử số 1", 2, "8/10"),
        ("chat", "Con tôi sốt 39 độ nên uống thuốc gì?", None, None),
        ("practice", "Luyện điểm yếu: Tiêm phòng/Tiêm chủng trẻ em và người lớn", 2, "2/6"),
        ("unit", "Sức khỏe quần thể và dự phòng · Đo lường kết hợp và sàng lọc", None, "Hoàn thành"),
    ]


def test_opening_the_app_is_not_a_study_day(learner_api):
    learner_api.get("/v1/home")                                            # a visit, and whatever the rules build
    learner_api.get("/v1/session/today")
    assert rhythm(learner_api)["week"]["study_days"] == 0


def test_a_card_seen_twice_is_one_card_and_a_phone_left_open_is_not_study_time(learner_api, clock):
    make_wrong_unit_answer(learner_api)
    card = learner_api.get("/v1/cards/due").json()["items"][0]
    learner_api.post(f"/v1/cards/{card['id']}/reviews", json={"rating": 1, "time_ms": 3_600_000})      # forgotten; an hour open
    clock.advance(minutes=11)
    learner_api.post(f"/v1/cards/{card['id']}/reviews", json={"rating": 3, "time_ms": 30_000})
    entry = next(a for a in rhythm(learner_api)["activity"] if a["kind"] == "cards")
    # one card, not remembered when first shown today; 10 minutes at most for one review, plus 30 seconds
    assert (entry["title"], entry["result_vi"], entry["minutes"]) == ("Ôn 1 thẻ", "0/1", 11)


def test_nothing_predicts_the_exam_and_another_learner_sees_nothing(api, learner_api, tokens_for_new_learner):
    make_wrong_unit_answer(learner_api)
    card = learner_api.get("/v1/cards/due").json()["items"][0]
    learner_api.post(f"/v1/cards/{card['id']}/reviews", json={"rating": 3, "time_ms": 60_000})
    assert not PREDICTION.search(json.dumps(rhythm(learner_api), ensure_ascii=False))
    other = api.get("/v1/progress/rhythm", headers=tokens_for_new_learner()).json()
    assert other["week"]["minutes"] == 0 and other["memory"]["reviews"] == 0 and other["activity"] == [] and other["curve"] == []


def test_mock_mode_still_serves_the_example(mock_client):
    assert mock_client.get("/v1/progress/rhythm").status_code == 200
