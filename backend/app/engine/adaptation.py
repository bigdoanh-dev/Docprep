"""The adaptation summary shown after a practice set, "Gia sư đang điều chỉnh"
(handover/05-algorithms.md §13). Pure.

It reports what the set changed, from stored results. A line whose result is zero or false is None,
so the screen cannot show work that was not done.
"""


def summarise(*, total: int, correct: int, competencies_answered: int, cards_created: int,
              tomorrow_before: str | None, tomorrow_after: str | None, tomorrow_after_name: str | None) -> dict:
    """`total` is the number of questions the set asks; unanswered ones count as not correct.

    "Tomorrow" is about tomorrow's practice step and nothing else: `tomorrow_before` is the topic it
    would be on had this set's answers not been given, `tomorrow_after` the topic it will be on now
    (None: no practice step). The line appears only when the set changed that topic, and names it."""
    changed = tomorrow_after is not None and tomorrow_after != tomorrow_before and bool(tomorrow_after_name)
    return {
        "graded": {"correct": correct, "total": total},
        # every recorded answer moves the learner's ability on that question's competency
        "mastery_updated": {"competencies": competencies_answered} if competencies_answered > 0 else None,
        "cards_created": {"n": cards_created} if cards_created > 0 else None,
        "tomorrow": {"reordered": True, "top_item": tomorrow_after_name} if changed else None,
    }
