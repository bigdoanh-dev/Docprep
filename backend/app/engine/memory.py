"""Memory figures for Tiến độ · Nhịp học (handover/05-algorithms.md §12). Pure.

Everything is read off the FSRS state of the learner's own cards: how likely a card is to be
recalled at a given time, which stage it is in, and the curve of one card through its real reviews.
Nothing here says anything about an exam result.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Literal

from fsrs import Card, Rating, Scheduler, State

Stage = Literal["new", "learning", "mature"]


def _scheduler(retention: float) -> Scheduler:
    return Scheduler(desired_retention=retention, enable_fuzzing=False)


def _utc(at: datetime) -> datetime:
    """py-fsrs takes UTC only; a time read from the database carries another zone object for the same instant."""
    return at.astimezone(timezone.utc)


def retrievability(state: dict, at: datetime, retention: float) -> float:
    """The chance, 0 to 1, that the card is recalled at that time. A card never reviewed has none to speak of."""
    card = Card.from_dict(state)
    if card.last_review is None:
        return 0.0
    return min(1.0, max(0.0, float(_scheduler(retention).get_card_retrievability(card, _utc(at)))))


def mean_recall(states: list[dict], at: datetime, retention: float) -> float | None:
    """Mean recall over reviewed cards; None when there is no card to average."""
    if not states:
        return None
    return round(sum(retrievability(s, at, retention) for s in states) / len(states), 2)


def stage(state: dict, reps: int, mature_days: int) -> Stage:
    """new: never reviewed. mature: in the review state with a stability of `mature_days` or more
    (stability is the interval FSRS gives at 90% recall). learning: everything in between, the
    learning and relearning steps included. The due date is not used: it is held back to the exam
    date, which would turn every well-known card into "learning" in the weeks before the exam."""
    if reps == 0:
        return "new"
    card = Card.from_dict(state)
    if card.state == State.Review and card.stability is not None and card.stability >= mature_days:
        return "mature"
    return "learning"


def replay(created_at: datetime, reviews: list[tuple[datetime, int]], retention: float) -> list[dict]:
    """The card's state after each of its reviews, replayed from the ratings in time order."""
    scheduler, card, states = _scheduler(retention), Card(card_id=0, due=_utc(created_at)), []   # a fixed id: same input, same output
    for at, rating in sorted(reviews, key=lambda r: r[0]):
        card, _log = scheduler.review_card(card, Rating(rating), _utc(at))
        states.append(card.to_dict())
    return states


def curve(created_at: datetime, reviews: list[tuple[datetime, int]], today: datetime, retention: float,
          projection_days: int, local_date: Callable[[datetime], date]) -> list[dict]:
    """One card's memory curve from its real reviews: recall falls until a review brings it back to
    1, then falls more slowly. It ends with today's value and one projected point further on, with
    no review in between. It illustrates the mechanism and claims nothing else."""
    ordered = sorted(reviews, key=lambda r: r[0])
    if not ordered:
        return []
    points, state = [], None
    for (at, _rating), after in zip(ordered, replay(created_at, ordered, retention)):
        if state is not None:
            points.append({"date": local_date(at), "recall": round(retrievability(state, at, retention), 2), "kind": "decay"})
        points.append({"date": local_date(at), "recall": 1.0, "kind": "review"})
        state = after
    later = today + timedelta(days=projection_days)
    points.append({"date": local_date(today), "recall": round(retrievability(state, today, retention), 2), "kind": "decay"})
    points.append({"date": local_date(later), "recall": round(retrievability(state, later, retention), 2), "kind": "projected"})
    return points
