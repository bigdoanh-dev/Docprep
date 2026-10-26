"""FSRS scheduling via py-fsrs, run on the server (handover/05-algorithms.md §5).

Card state is the dict form of fsrs.Card. Due dates never pass the learner's exam date.
"""
from datetime import date, datetime, time, timezone

from fsrs import Card, Rating, Scheduler


def _scheduler(retention: float) -> Scheduler:
    return Scheduler(desired_retention=retention, enable_fuzzing=False)


def _cap(due: datetime, now: datetime, exam_date: date) -> datetime:
    limit = datetime.combine(exam_date, time(0), tzinfo=timezone.utc)
    return max(min(due, limit), now)


def new_state(now: datetime) -> dict:
    return Card(due=now).to_dict()


def review(state: dict, rating: int, now: datetime, exam_date: date, retention: float) -> tuple[dict, datetime, int]:
    card, _log = _scheduler(retention).review_card(Card.from_dict(state), Rating(rating), now)
    due = _cap(card.due, now, exam_date)
    card.due = due
    return card.to_dict(), due, int((due - now).total_seconds())


def preview(state: dict, now: datetime, exam_date: date, retention: float) -> dict[int, int]:
    return {r: review(state, r, now, exam_date, retention)[2] for r in (1, 2, 3, 4)}
