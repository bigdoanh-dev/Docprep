"""The daily session, "Phiên hôm nay" (handover/05-algorithms.md §11). Pure and deterministic.

Three steps at most, in this order: the cards that are due, a short practice on the learner's weak
spot, and the unit to continue. A step with nothing behind it is not built. Every reason line is a
template filled from the numbers the rule used; no model writes any of it.

`timing` is the `session` key of config.yaml.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil
from typing import Literal


@dataclass(frozen=True)
class Seen:
    """An approved question of the chosen competency, and when the learner last answered it."""
    question_id: str
    last_seen: datetime | None


@dataclass(frozen=True)
class Step:
    kind: Literal["cards", "practice", "continue"]
    count: int
    minutes: int
    reason_vi: str
    unit_id: str | None = None


def weak_spots(wrong_by_code: dict[str, int], weights: dict[str, float]) -> list[str]:
    """Every competency with a wrong answer, worst first: the most wrong answers, then the higher
    blueprint weight, then the lower code. The caller practises the first one that has a question to ask."""
    wrong = {code: n for code, n in wrong_by_code.items() if n > 0}
    return sorted(wrong, key=lambda code: (-wrong[code], -weights.get(code, 0.0), code))


def weak_spot(wrong_by_code: dict[str, int], weights: dict[str, float]) -> str | None:
    ranked = weak_spots(wrong_by_code, weights)
    return ranked[0] if ranked else None


def pick_items(candidates: list[Seen], now: datetime, seen_window_days: int, n: int) -> list[str]:
    """At most n questions the learner has not answered within the window: never-seen ones first,
    then the longest unseen, ties by question id."""
    horizon = now - timedelta(days=seen_window_days)
    eligible = [c for c in candidates if c.last_seen is None or c.last_seen <= horizon]
    eligible.sort(key=lambda c: (c.last_seen is not None, c.last_seen or now, c.question_id))
    return [c.question_id for c in eligible[:n]]


def minutes(count: int, seconds_each: int) -> int:
    """Whole minutes, rounded up; nothing takes no time."""
    return ceil(count * seconds_each / 60) if count > 0 else 0


def cards_step(due: int, overdue: int, review_cap: int, timing: dict) -> Step | None:
    """The step holds the cards due when the session is built, up to the daily limit, and says so
    when the limit left some out."""
    if due <= 0:
        return None
    count = min(due, review_cap)
    late = min(overdue, count)
    held = f"{count} thẻ đến hạn hôm nay" if count == due else f"{count} trong {due} thẻ đến hạn hôm nay"
    reason = f"{held}." if late == 0 else f"{held}, {late} thẻ quá hạn ôn trước."
    return Step("cards", count, minutes(count, timing["card_seconds"]), reason)


def topic_reason(topic_name: str, wrong: int, added_from_chat: bool, timing: dict) -> str:
    """Why this topic, without a full stop: it is a sentence of its own or the start of an item's reason."""
    if added_from_chat:
        return "Bạn đã thêm từ Hỏi đáp"
    return f"Bạn sai {wrong} câu về {topic_name} trong {timing['wrong_window_days']} ngày qua"


def practice_step(topic_name: str, wrong: int, n_items: int, added_from_chat: bool, timing: dict) -> Step | None:
    if n_items <= 0:
        return None
    return Step("practice", n_items, minutes(n_items, timing["item_seconds"]),
                topic_reason(topic_name, wrong, added_from_chat, timing) + ".")


def continue_step(unit_id: str, module_short_name: str, remaining: int, timing: dict) -> Step | None:
    if remaining <= 0:
        return None
    return Step("continue", remaining, minutes(remaining, timing["unit_item_seconds"]),
                f"Học tiếp học phần đang ưu tiên: {module_short_name}.", unit_id)


def item_reason(why_this_topic: str, unseen: bool, timing: dict) -> str:
    """"Vì sao câu này?": why the topic and, for as long as it is true, that the learner has not met
    the question lately."""
    if not unseen:
        return f"{why_this_topic}."
    return f"{why_this_topic} · bạn chưa gặp câu này trong {timing['seen_window_days']} ngày."
