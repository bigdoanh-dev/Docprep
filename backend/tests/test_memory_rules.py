"""Memory rules for the progress screens (handover/05-algorithms.md §12): pure, no database."""
from datetime import datetime, timedelta, timezone

from app.engine.memory import curve, mean_recall, replay, retrievability, stage
from app.engine.scheduler import new_state

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
R = 0.9


def days(n: float) -> datetime:
    return T0 + timedelta(days=n)


def local_date(at: datetime):
    return at.date()


def test_recall_is_full_right_after_a_review_and_fades():
    state = replay(T0, [(days(0), 3), (days(1), 3)], R)[-1]
    just_after = retrievability(state, days(1), R)
    a_week_on = retrievability(state, days(8), R)
    assert just_after > 0.99 and 0 < a_week_on < just_after


def test_a_card_never_reviewed_has_no_recall():
    assert retrievability(new_state(T0), days(3), R) == 0.0
    assert mean_recall([], days(3), R) is None


def test_mean_recall_is_the_average_over_the_cards():
    fresh = replay(T0, [(days(10), 3)], R)[-1]
    older = replay(T0, [(days(0), 3)], R)[-1]
    both = mean_recall([fresh, older], days(10), R)
    assert retrievability(older, days(10), R) < both < retrievability(fresh, days(10), R) + 0.01


def test_stages():
    assert stage(new_state(T0), 0, 21) == "new"
    learning = replay(T0, [(days(0), 3)], R)[-1]                 # still in its learning steps
    assert stage(learning, 1, 21) == "learning"
    reviews = [(days(0), 3), (days(0.01), 3)]                     # graduates to the review state
    state = replay(T0, reviews, R)[-1]
    at = datetime.fromisoformat(state["due"])
    for _ in range(8):                                            # "Tốt" at each due date: the interval grows
        reviews.append((at, 3))
        state = replay(T0, reviews, R)[-1]
        at = datetime.fromisoformat(state["due"])
    assert stage(state, len(reviews), 21) == "mature"
    assert stage(state, len(reviews), 100_000) == "learning"      # the threshold decides
    # a due date held back to the exam date does not make a well-known card "learning" again
    capped = {**state, "due": (datetime.fromisoformat(state["last_review"]) + timedelta(days=5)).isoformat()}
    assert stage(capped, len(reviews), 21) == "mature"


def test_replay_is_deterministic():
    reviews = [(days(0), 3), (days(1), 1), (days(2), 4)]
    assert replay(T0, reviews, R) == replay(T0, reviews, R) and len(replay(T0, reviews, R)) == 3


def test_the_curve_follows_the_real_reviews_and_projects_one_step():
    assert curve(T0, [], days(10), R, 7, local_date) == []
    points = curve(T0, [(days(0), 3), (days(3), 3)], days(10), R, 7, local_date)
    assert [p["kind"] for p in points] == ["review", "decay", "review", "decay", "projected"]
    assert [p["date"] for p in points] == [days(0).date(), days(3).date(), days(3).date(), days(10).date(), days(17).date()]
    assert all(0 <= p["recall"] <= 1 for p in points) and points[0]["recall"] == points[2]["recall"] == 1.0
    assert points[4]["recall"] < points[3]["recall"] < 1.0


def test_times_in_another_zone_object_are_accepted():
    from zoneinfo import ZoneInfo
    hanoi = ZoneInfo("Asia/Ho_Chi_Minh")
    reviews = [(days(0).astimezone(hanoi), 3), (days(1).astimezone(hanoi), 3)]
    state = replay(T0.astimezone(hanoi), reviews, R)[-1]
    assert replay(T0, [(days(0), 3), (days(1), 3)], R)[-1] == state
    assert retrievability(state, days(8).astimezone(hanoi), R) == retrievability(state, days(8), R)
