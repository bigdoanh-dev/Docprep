"""Trang chủ: what to do now, the next mock exam, what the rules did since last time, and where
the learner left off.

Everything under "Đề xuất từ gia sư" is a rule event from the activity log with a fixed sentence
around its count; no model writes any of it in R1.0.
"""
from datetime import datetime

from app import events
from app.repo import activity as activity_repo
from app.repo import cards as cards_repo
from app.repo import exams as exams_repo
from app.repo import learners as learners_repo
from app.repo import practice as practice_repo
from app.services import session as session_service
from app.services.exams import close_expired

RECENT_LIMIT = 4


def _todays_set(conn, learner: dict, now: datetime) -> dict | None:
    """Today's practice set while it is still open. Reading it builds the day's session if this is
    the day's first request."""
    set_id = session_service.practice_set_id(conn, learner, now)
    practice_set = practice_repo.own_set(conn, learner["id"], set_id) if set_id else None
    return practice_set if practice_set and practice_set["completed_at"] is None else None


def _since_previous_visit(conn, learner: dict, todays_set: dict | None) -> tuple[list[dict], str | None]:
    """What the rules did between the previous visit and the start of this one: at most one line per
    kind, and the note under "Ôn nhanh". Empty on a first visit. Each thing is listed in one visit
    only: what happens during a visit is news at the next."""
    visits = activity_repo.visits(conn, learner["pseudonym_id"], 2)
    if len(visits) < 2:
        return [], None
    this_visit, previous_visit = visits
    counts = activity_repo.counts_between(conn, learner["pseudonym_id"], ["cards_created", "remediation_inserted"],
                                          previous_visit, this_visit)
    suggestions, note = [], None
    if cards := counts.get("cards_created"):
        suggestions.append({"kind": "cards_created", "text_vi": f"Tạo {cards} thẻ ôn từ câu bạn trả lời sai",
                            "action": {"label_vi": "Xem thẻ", "target": "cards", "id": None}})
        note = f"{cards} thẻ mới từ câu bạn trả lời sai"
    if examples := counts.get("remediation_inserted"):
        suggestions.append({"kind": "example_added", "text_vi": f"Thêm {examples} ví dụ vào lộ trình vì câu bạn trả lời sai",
                            "action": None})
    # The practice line is about today's set and nothing older, for as long as that set is open.
    if todays_set and activity_repo.happened_between(conn, learner["pseudonym_id"], "practice_set_built",
                                                     str(todays_set["id"]), previous_visit, this_visit):
        suggestions.append({"kind": "practice_added",
                            "text_vi": f"Bổ sung {len(todays_set['question_ids'])} câu luyện cho hôm nay",
                            "action": {"label_vi": "Luyện", "target": "practice_set", "id": str(todays_set["id"])}})
    return suggestions, note


def _recent(conn, learner: dict) -> list[dict]:
    items = []
    for r in activity_repo.recent(conn, learner["id"], learner["pseudonym_id"], RECENT_LIMIT):
        if r["kind"] == "unit":
            subtitle = f"{r['module_short_name']} · chủ đề {r['position']}/{r['units_in_module']}"
        else:
            subtitle = "Hỏi đáp"
        items.append({"kind": r["kind"], "id": r["id"], "title": r["title"], "subtitle_vi": subtitle,
                      "progress": float(r["progress"]) if r["progress"] is not None else None})
    return items


def home(conn, learner: dict, now: datetime) -> dict:
    # The session first, then the expired attempts: starting an exam takes its locks in that order too.
    todays_set = _todays_set(conn, learner, now)
    close_expired(conn, learner, now)
    practice_left = len(todays_set["question_ids"]) - len(practice_repo.responses(conn, todays_set["id"])) if todays_set else 0
    due = cards_repo.count_due(conn, learner["id"], now)
    form = exams_repo.next_mock(conn, learner["id"], learner["is_synthetic"])
    next_mock = None
    if form:
        running = exams_repo.running(conn, learner["id"], form["id"])
        next_mock = {"form_id": form["id"], "title": form["title"], "n_questions": form["n"],
                     "minutes": form["n"] * form["spq"] // 60, "open_attempt_id": running["id"] if running else None}
    events.record_visit(conn, learner["pseudonym_id"], now)
    suggestions, note = _since_previous_visit(conn, learner, todays_set)
    return {
        "name": learners_repo.profile(conn, learner["id"])["display_name"],
        "quick_review_count": due + practice_left,
        "quick_review_note_vi": note,
        "due_cards": due,
        "next_mock": next_mock,
        "tutor_suggestions": suggestions,
        "recent": _recent(conn, learner),
    }
