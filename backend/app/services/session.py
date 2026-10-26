"""Phiên hôm nay: the daily session, built by rules once per local day and stored.

It is built by whichever read first needs it that day (Home or the session screen) and does not
change afterwards, so the practice set and the reasons stay put while the learner works. Whether a
step is done is read from the learner's records each time. A write never builds a session: an
answer sent a minute after midnight belongs to the set the learner was working on.
"""
from dataclasses import asdict
from datetime import datetime, timedelta

from app.config import settings
from app.engine.session import cards_step, continue_step, practice_step
from app.errors import ApiError
from app.repo import cards as cards_repo
from app.repo import content
from app.repo import learners as learners_repo
from app.repo import practice as practice_repo
from app.repo import sessions as repo
from app.repo import units as units_repo
from app.services import practice
from app.services.account import local_date
from app.services.responses import ranking
from app.services.session_progress import cards_reviewed, day_start, step_completed  # noqa: F401 — part of this service


def _build(conn, learner: dict, day, now: datetime) -> dict:
    cfg = settings()["session"]
    topics = {t["code"]: t for t in content.topics(conn)}
    steps = []

    # 1. The cards that are due, the longest overdue first, up to the learner's daily limit. The
    #    step keeps which cards they are: it is done when those have been reviewed.
    counts = cards_repo.due_counts(conn, learner["id"], now, day_start(now))
    cards = cards_step(counts["due"], counts["overdue"], learner["max_reviews_per_day"], cfg)
    if cards:
        steps.append({**asdict(cards), "card_ids": cards_repo.due_ids(conn, learner["id"], now, cards.count)})

    # 2. Practice on the topic the learner pinned from chat for today, else on the weak spot: the
    #    worst topic that still has a question the learner has not met lately.
    practice_set = None
    pinned = repo.addition(conn, learner["id"], day)
    choice = practice.choose_topic(conn, learner, now, pinned=pinned["competency_code"] if pinned else None)
    if choice:
        practice_set = practice.build(conn, learner, "session", choice.competency_code, choice.wrong,
                                      choice.added_from_chat, now)
        steps.append(asdict(practice_step(topics[choice.competency_code]["name"], choice.wrong,
                                          len(practice_set["question_ids"]), choice.added_from_chat, cfg)))

    # 3. The unit to continue: the first unfinished one of the học phần whose topics rank highest.
    by_priority = (topics[topic]["module_id"] for topic in ranking(conn, learner))
    module_order = list(dict.fromkeys(module_id for module_id in by_priority if module_id))
    unit = units_repo.next_unfinished(conn, learner["id"], module_order)
    if unit:
        steps.append(asdict(continue_step(unit["unit_id"], unit["module_short_name"], unit["remaining"], cfg)))

    # A step with nothing behind it was not built.
    return repo.create(conn, learner["id"], day, steps, practice_set["id"] if practice_set else None, now)


def _stored(conn, learner: dict, now: datetime) -> dict:
    """Today's session row, built first if this is the day's first read. The learner's row is locked
    for the build, so two requests arriving together make one session."""
    day = local_date(now)
    session = repo.find(conn, learner["id"], day)
    if session is None:
        learners_repo.lock(conn, learner["id"])
        session = repo.find(conn, learner["id"], day) or _build(conn, learner, day, now)
    return session


def _done(conn, learner: dict, session: dict, step: dict) -> bool:
    if step["kind"] == "cards":
        return cards_reviewed(conn, session, step)
    if step["kind"] == "practice":
        practice_set = practice_repo.own_set(conn, learner["id"], session["practice_set_id"])
        return practice_set is not None and practice_set["completed_at"] is not None
    return units_repo.finished(conn, learner["id"], step["unit_id"])


def today(conn, learner: dict, now: datetime) -> dict:
    session = _stored(conn, learner, now)
    steps = [{"kind": step["kind"], "count": step["count"], "minutes": step["minutes"], "reason_vi": step["reason_vi"],
              "unit_id": step.get("unit_id"), "done": _done(conn, learner, session, step),
              "practice_set_id": session["practice_set_id"] if step["kind"] == "practice" else None}
             for step in session["steps"]]
    return {"local_date": session["local_date"], "steps": steps, "total_minutes": sum(s["minutes"] for s in steps)}


def practice_set_id(conn, learner: dict, now: datetime) -> int | None:
    """The id of today's practice set, None when today's session has no practice step."""
    return _stored(conn, learner, now)["practice_set_id"]


def _no_practice() -> ApiError:
    return ApiError(404, "no_practice_today", "Hôm nay không có bài luyện điểm yếu.")


def practice_view(conn, learner: dict, now: datetime) -> dict:
    set_id = practice_set_id(conn, learner, now)
    if set_id is None:
        raise _no_practice()
    return practice.view(conn, learner, set_id)


def practice_target(conn, learner: dict, now: datetime, question_id: str | None = None) -> int:
    """The practice set a write on "today's practice" is for. A write builds nothing. It goes to
    today's set; or, when the day changed while the learner was working, to yesterday's set if that
    one is still open (for an answer: if the question is one of its own)."""
    today_date = local_date(now)
    todays = previous = None
    for session in repo.latest(conn, learner["id"], 2):
        if session["practice_set_id"] is None:
            continue
        if session["local_date"] == today_date:
            todays = session["practice_set_id"]
        elif session["local_date"] == today_date - timedelta(days=1):
            still_open = practice_repo.own_set(conn, learner["id"], session["practice_set_id"])
            if still_open and still_open["completed_at"] is None:
                previous = still_open
    if previous and (todays is None or (question_id is not None and question_id in previous["question_ids"]
                                         and not _holds(conn, learner, todays, question_id))):
        return previous["id"]
    if todays is None:
        raise _no_practice()
    return todays


def _holds(conn, learner: dict, set_id: int, question_id: str) -> bool:
    practice_set = practice_repo.own_set(conn, learner["id"], set_id)
    return practice_set is not None and question_id in practice_set["question_ids"]
