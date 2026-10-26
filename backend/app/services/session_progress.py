"""Marking a step of today's session as completed, from wherever the learner did the work.

Kept apart from services/session.py because the services that do the work (cards, units, practice
sets) call this, and the session service calls them.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo

from app import events
from app.config import settings
from app.repo import cards as cards_repo
from app.repo import sessions as repo
from app.services.account import local_date


def day_start(now: datetime) -> datetime:
    """The instant the learner's local day began."""
    return datetime.combine(local_date(now), time.min, tzinfo=ZoneInfo(settings()["local_timezone"]))


def cards_reviewed(conn, session: dict, step: dict) -> bool:
    """Whether the cards step is done: every card it held when the session was built has been
    reviewed since. A card that comes due again minutes later, or a new card from a wrong answer,
    does not undo it."""
    return cards_repo.all_reviewed_since(conn, step.get("card_ids", []), session["built_at"])


def step_completed(conn, learner: dict, kind: str, now: datetime, *, unit_id: str | None = None,
                   practice_set_id: int | None = None) -> None:
    """Log `session_step_completed` once, when today's session has that step and the work just done
    completes it: the step's own cards, the unit it names, the practice set it holds. Work outside
    the session, or a learner who has not opened today's session, logs nothing."""
    session = repo.find(conn, learner["id"], local_date(now))
    if session is None:
        return
    step = next((s for s in session["steps"] if s["kind"] == kind), None)
    if step is None:
        return
    if kind == "cards" and not cards_reviewed(conn, session, step):
        return
    if kind == "continue" and step["unit_id"] != unit_id:
        return
    if kind == "practice" and session["practice_set_id"] != practice_set_id:
        return
    if repo.step_logged(conn, learner["pseudonym_id"], kind, day_start(now)):
        return
    events.record(conn, learner["pseudonym_id"], "session_step_completed", now, ref_type="step", ref_id=kind)
