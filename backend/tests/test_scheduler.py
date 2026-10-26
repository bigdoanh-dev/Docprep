from datetime import date, datetime, timezone

from app.engine.scheduler import new_state, preview, review

UTC = timezone.utc
NOW = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)


def test_preview_has_four_increasing_intervals():
    p = preview(new_state(NOW), NOW, date(2027, 3, 15), 0.9)
    assert list(p) == [1, 2, 3, 4] and p[1] <= p[2] <= p[3] <= p[4]
    assert p[1] > 0


def test_review_returns_state_due_and_seconds():
    state, due, secs = review(new_state(NOW), 3, NOW, date(2027, 3, 15), 0.9)
    assert due > NOW and secs == int((due - NOW).total_seconds()) and state["due"]


def test_due_never_after_exam_date():
    s = new_state(NOW)
    now = NOW
    for _ in range(8):
        s, due, _secs = review(s, 4, now, date(2026, 10, 20), 0.9)
        assert due <= datetime(2026, 10, 20, tzinfo=UTC)
        now = due


def test_due_never_before_now_when_exam_date_has_passed():
    _s, due, secs = review(new_state(NOW), 4, NOW, date(2026, 10, 1), 0.9)
    assert due == NOW and secs == 0
