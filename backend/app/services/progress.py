"""Tiến độ: Năng lực (what the learner knows) and Nhịp học (how they study).

Every figure is counted from the learner's own stored records. With no records a block is empty,
zero or null. Nothing here predicts an exam outcome: no predicted score, no chance of passing, no
pass line, no trend direction (FR-LRN-26).
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.config import settings
from app.engine import memory
from app.repo import content
from app.repo import progress as repo
from app.repo import responses as responses_repo
from app.services.account import local_date
from app.services.responses import ranking

LEVELS = {1: "Nhớ, Hiểu", 2: "Vận dụng", 3: "Phân tích, Đánh giá"}
ACTIVITY_LIMIT = 20
# What makes a day a study day: the learner answered, reviewed, sat an exam or asked. Opening the app,
# and what the rules build on their own, do not.
STUDY_KINDS = ["unit_response", "practice_response", "card_review", "exam_started", "exam_submitted", "chat_turn"]


def _days_to_exam(learner: dict, now: datetime) -> int:
    return max(0, (learner["exam_date"] - local_date(now)).days)


# ---- Năng lực ------------------------------------------------------------------------------------

def skills(conn, learner: dict, scope: str, now: datetime) -> dict:
    topics = {t["code"]: t for t in content.topics(conn)}
    minimum = settings()["mastery"]["min_responses"]
    assessed = {code for code, row in responses_repo.mastery_rows(conn, learner["id"]).items()
                if row["n_responses"] >= minimum}
    # Coverage is over the blueprint's 54 core issues; the foundation topic is not one of them.
    core = {code: t for code, t in topics.items() if code.startswith("CI-")}
    modules = [{"module_id": m["id"], "short_name": m["short_name"],
                "topics_assessed": sum(1 for code, t in core.items() if t["module_id"] == m["id"] and code in assessed),
                "topics_total": sum(1 for t in core.values() if t["module_id"] == m["id"])}
               for m in content.modules(conn, learner["id"])]

    # The three topics to work on first, among those that have a question to practise with.
    practisable = repo.topics_with_questions(conn, learner["is_synthetic"])
    counts = repo.answer_counts(conn, learner["id"])
    weakest = repo.weakest_units(conn, learner["id"])
    priorities = []
    for code in ranking(conn, learner):
        if code not in practisable:
            continue
        answered = counts.get(code, {"correct": 0, "total": 0})
        priorities.append({"rank": len(priorities) + 1, "competency_code": code, "name": topics[code]["name"],
                           "module_id": topics[code]["module_id"], "correct": answered["correct"],
                           "total": answered["total"], "weakest_vi": weakest.get(code)})
        if len(priorities) == 3:
            break

    # Real scores of finished mock attempts, oldest first, and the answers given in them by level.
    attempts = list(reversed(repo.mock_attempts(conn, learner["id"], 3 if scope == "latest3" else None)))
    by_level = repo.level_counts(conn, [a["attempt_id"] for a in attempts])
    levels = [{"level": level, "label_vi": label, "correct": by_level.get(level, {}).get("correct", 0),
               "total": by_level.get(level, {}).get("total", 0)} for level, label in LEVELS.items()]
    return {
        "days_to_exam": _days_to_exam(learner, now),
        "scope": scope,
        "coverage": {"assessed_topics": len(assessed & set(core)), "total_topics": len(core), "modules": modules},
        "priorities": priorities,
        "mock_scores": attempts,
        "group_grid": None,     # the group × exam grid waits for open issue 20
        "levels": levels,
    }


# ---- Nhịp học ------------------------------------------------------------------------------------

def _minutes(ms: int | None) -> int:
    """Whole minutes, rounded half up."""
    return int((ms or 0) / 60000 + 0.5)


def _start_of(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=ZoneInfo(settings()["local_timezone"]))


def _activity(conn, learner: dict, week_start: datetime) -> list[dict]:
    timezone, max_ms = settings()["local_timezone"], settings()["activity"]["max_duration_ms"]
    names = {t["code"]: t["name"] for t in content.topics(conn)}
    entries = []
    for u in repo.unit_activity(conn, learner["id"], week_start, max_ms):
        entries.append({"kind": "unit", "title": f"{u['short_name']} · {u['topic']}", "occurred_at": u["occurred_at"],
                        "minutes": _minutes(u["ms"]) if u["ms"] else None, "result_vi": "Hoàn thành" if u["done"] else None})
    for p in repo.practice_activity(conn, learner["id"], week_start, max_ms):
        graded = (p["summary"] or {}).get("graded")
        entries.append({"kind": "practice", "title": f"Luyện điểm yếu: {names[p['competency_code']]}",
                        "occurred_at": p["occurred_at"], "minutes": _minutes(p["ms"]) if p["ms"] else None,
                        "result_vi": f"{graded['correct']}/{graded['total']}" if graded else None})
    for c in repo.chat_activity(conn, learner["pseudonym_id"], week_start):
        entries.append({"kind": "chat", "title": c["title"], "occurred_at": c["occurred_at"], "minutes": None,
                        "result_vi": None})
    for d in repo.card_activity(conn, learner["id"], timezone, week_start, max_ms):
        entries.append({"kind": "cards", "title": f"Ôn {d['cards']} thẻ", "occurred_at": d["occurred_at"],
                        "minutes": _minutes(d["ms"]) if d["ms"] else None, "result_vi": f"{d['recalled']}/{d['cards']}"})
    for e in repo.exam_activity(conn, learner["id"], week_start):
        entries.append({"kind": "exam", "title": e["title"], "occurred_at": e["occurred_at"],
                        "minutes": _minutes(int(e["ms"])), "result_vi": f"{e['score']}/{e['total']}"})
    entries.sort(key=lambda entry: entry["occurred_at"], reverse=True)
    return entries[:ACTIVITY_LIMIT]


def rhythm(conn, learner: dict, now: datetime) -> dict:
    cfg = settings()
    timezone, mem = cfg["local_timezone"], cfg["memory"]
    today = local_date(now)
    monday = today - timedelta(days=today.weekday())
    first_day = today - timedelta(days=55)

    # Study time: the durations in the activity log, per local day.
    ms_by_day = repo.study_ms_by_day(conn, learner["pseudonym_id"], timezone, _start_of(min(first_day, monday - timedelta(days=7))))
    minutes = {day: _minutes(ms) for day, ms in ms_by_day.items()}
    this_week = [monday + timedelta(days=i) for i in range(today.weekday() + 1)]
    last_week = [monday - timedelta(days=7 - i) for i in range(7)]
    active = repo.active_days(conn, learner["pseudonym_id"], timezone, _start_of(monday), STUDY_KINDS)

    # Memory: the learner's cards, read off their FSRS state.
    retention = learner["target_retention"]
    cards = repo.cards(conn, learner["id"])
    stages = [memory.stage(c["fsrs_card"], c["reps"], mem["mature_days"]) for c in cards]
    window = repo.review_counts(conn, learner["id"], now - timedelta(days=mem["window_days"]))
    reviewed = [c for c in cards if c["reps"] > 0]
    later = now + timedelta(days=mem["projection_days"])

    curve = []
    if reviewed:
        card = min(reviewed, key=lambda c: (-c["reps"], c["created_at"], c["id"]))      # the most reviewed, then the oldest
        curve = memory.curve(card["created_at"], repo.reviews_of(conn, card["id"]), now, retention,
                             mem["projection_days"], local_date)

    module_of = {t["code"]: t["module_id"] for t in content.topics(conn)}
    recall_by_module = []
    for m in content.modules(conn, learner["id"]):
        states = [c["fsrs_card"] for c in reviewed if module_of[c["competency_code"]] == m["id"]]
        if states:      # a học phần with no reviewed card has no recall to show
            recall_by_module.append({"module_id": m["id"], "short_name": m["short_name"],
                                     "now": memory.mean_recall(states, now, retention),
                                     "in_7_days": memory.mean_recall(states, later, retention)})

    forecast = []
    for i in range(7):
        day = today + timedelta(days=i)
        due = [c for c in cards if (local_date(c["due_at"]) <= day if i == 0 else local_date(c["due_at"]) == day)]
        forecast.append({"date": day, "count": len(due)})

    return {
        "days_to_exam": _days_to_exam(learner, now),
        "week": {"minutes": sum(minutes.get(d, 0) for d in this_week),
                 "previous_minutes": sum(minutes.get(d, 0) for d in last_week),
                 "study_days": len(active & set(this_week)), "days_elapsed": today.weekday() + 1},
        "heatmap": [{"date": first_day + timedelta(days=i), "minutes": minutes.get(first_day + timedelta(days=i), 0)}
                    for i in range(56)],
        "memory": {"recall_rate": round(window["recalled"] / window["reviews"], 2) if window["reviews"] else None,
                   "window_days": mem["window_days"], "reviews": window["reviews"],
                   "new": stages.count("new"), "learning": stages.count("learning"), "mastered": stages.count("mature"),
                   "due_today": sum(1 for c in cards if c["due_at"] <= now)},
        "curve": curve,
        "recall_by_module": recall_by_module,
        "due_forecast": forecast,
        "activity": _activity(conn, learner, _start_of(monday)),
    }
