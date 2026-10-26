"""The daily session's rules (handover/05-algorithms.md §11): pure, no database."""
from datetime import datetime, timedelta, timezone

from app.engine.session import (Seen, cards_step, continue_step, item_reason, minutes, pick_items, practice_step,
                                topic_reason, weak_spot, weak_spots)

NOW = datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc)
TIMING = {"practice_items": 6, "wrong_window_days": 7, "seen_window_days": 14, "card_seconds": 30,
          "item_seconds": 80, "unit_item_seconds": 90}
WEIGHTS = {"FND": 2.0, "CI-01": 3.6, "CI-04": 3.6}


def days(n: int) -> datetime:
    return NOW - timedelta(days=n)


def test_the_weak_spot_is_where_most_answers_were_wrong():
    assert weak_spot({"FND": 3, "CI-04": 1}, WEIGHTS) == "FND"
    assert weak_spot({"FND": 2, "CI-04": 2}, WEIGHTS) == "CI-04"            # tie: the heavier topic
    assert weak_spot({"CI-04": 2, "CI-01": 2}, WEIGHTS) == "CI-01"          # same weight: the lower code
    assert weak_spot({"FND": 0}, WEIGHTS) is None and weak_spot({}, WEIGHTS) is None
    # every topic with a wrong answer, worst first: the next one is tried when the first has nothing to ask
    assert weak_spots({"FND": 2, "CI-04": 2, "CI-01": 1, "CI-02": 0}, WEIGHTS) == ["CI-04", "FND", "CI-01"]


def test_items_seen_lately_are_left_out_and_unseen_ones_come_first():
    candidates = [Seen("q5", days(20)), Seen("q1", days(3)), Seen("q3", None), Seen("q2", None),
                  Seen("q4", days(30)), Seen("q6", days(14) + timedelta(hours=1))]
    assert pick_items(candidates, NOW, 14, 6) == ["q2", "q3", "q4", "q5"]     # q1 and q6 were seen within 14 days
    assert pick_items(candidates, NOW, 14, 2) == ["q2", "q3"]
    assert pick_items([], NOW, 14, 6) == []


def test_minutes_round_up_and_nothing_takes_no_time():
    assert (minutes(8, 30), minutes(6, 80), minutes(1, 30), minutes(0, 80)) == (4, 8, 1, 0)


def test_the_cards_step_counts_what_is_due_up_to_the_daily_cap():
    step = cards_step(8, 2, 200, TIMING)
    assert (step.kind, step.count, step.minutes) == ("cards", 8, 4)
    assert step.reason_vi == "8 thẻ đến hạn hôm nay, 2 thẻ quá hạn ôn trước."
    assert cards_step(8, 0, 200, TIMING).reason_vi == "8 thẻ đến hạn hôm nay."
    capped = cards_step(300, 250, 200, TIMING)
    assert capped.count == 200 and capped.reason_vi == "200 trong 300 thẻ đến hạn hôm nay, 200 thẻ quá hạn ôn trước."
    assert cards_step(0, 0, 200, TIMING) is None


def test_the_practice_step_says_why_this_topic():
    step = practice_step("Đo lường tần suất bệnh", 3, 6, False, TIMING)
    assert (step.kind, step.count, step.minutes) == ("practice", 6, 8)
    assert step.reason_vi == "Bạn sai 3 câu về Đo lường tần suất bệnh trong 7 ngày qua."
    assert practice_step("X", 0, 4, True, TIMING).reason_vi == "Bạn đã thêm từ Hỏi đáp."
    assert practice_step("X", 3, 0, False, TIMING) is None


def test_the_window_in_the_reason_is_the_configured_one():
    step = practice_step("X", 2, 6, False, {**TIMING, "wrong_window_days": 10})
    assert step.reason_vi == "Bạn sai 2 câu về X trong 10 ngày qua."
    timing = {**TIMING, "wrong_window_days": 10, "seen_window_days": 21}
    assert item_reason(topic_reason("X", 2, False, timing), True, timing) == (
        "Bạn sai 2 câu về X trong 10 ngày qua · bạn chưa gặp câu này trong 21 ngày.")


def test_the_continue_step_names_the_hoc_phan():
    step = continue_step("u-dt-02", "Sức khỏe quần thể và dự phòng", 4, TIMING)
    assert (step.kind, step.count, step.minutes, step.unit_id) == ("continue", 4, 6, "u-dt-02")
    assert step.reason_vi == "Học tiếp học phần đang ưu tiên: Sức khỏe quần thể và dự phòng."
    assert continue_step("u-dt-02", "X", 0, TIMING) is None


def test_every_item_says_why_it_was_chosen():
    why = topic_reason("Đo lường tần suất bệnh", 3, False, TIMING)
    assert why == "Bạn sai 3 câu về Đo lường tần suất bệnh trong 7 ngày qua"
    assert item_reason(why, True, TIMING) == (
        "Bạn sai 3 câu về Đo lường tần suất bệnh trong 7 ngày qua · bạn chưa gặp câu này trong 14 ngày.")
    assert item_reason(topic_reason("X", 0, True, TIMING), True, TIMING) == (
        "Bạn đã thêm từ Hỏi đáp · bạn chưa gặp câu này trong 14 ngày.")
    # once the learner has answered the question, the claim that they have not met it is dropped
    assert item_reason(why, False, TIMING) == "Bạn sai 3 câu về Đo lường tần suất bệnh trong 7 ngày qua."
