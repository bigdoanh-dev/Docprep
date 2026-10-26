"""What to offer after a chat answer (handover/04-agentic-core.md, "Suggestions after an answer"). Pure.

A rule, not a model: when the answer's sources belong to a competency the learner has lately answered
wrongly, offer to practise it and to put it into tomorrow's session. The reason is a sentence over
the learner's own record. An offer is only a proposal: nothing is applied until the learner taps it.
"""


def label(kind: str, n_items: int | None) -> str:
    """What the button says."""
    return f"Luyện {n_items} câu đã duyệt" if kind == "practise" else "Thêm vào phiên ngày mai"


def propose(cited: list[str], wrong: dict[str, int], available: dict[str, int], names: dict[str, str],
            tomorrow_taken: bool, window_days: int, max_items: int) -> list[dict]:
    """`cited`: competency codes of the answer's sources. `wrong`: the learner's wrong answers per
    competency in the last `window_days`. `available`: approved questions per competency that can be
    asked now. Returns at most two offers, on one competency: the cited one with the most wrong
    answers (a tie goes to the first by code)."""
    weak = sorted((code for code in set(cited) if wrong.get(code, 0) > 0), key=lambda code: (-wrong[code], code))
    if not weak:
        return []
    code = weak[0]
    reason = f"Bạn đã trả lời sai {wrong[code]} câu về {names[code]} trong {window_days} ngày qua."
    offers = []
    n = min(max_items, available.get(code, 0))
    if n > 0:
        offers.append({"kind": "practise", "competency_code": code, "n_items": n, "label_vi": label("practise", n),
                       "reason_vi": reason})
    if not tomorrow_taken:
        offers.append({"kind": "add_to_tomorrow", "competency_code": code, "n_items": None,
                       "label_vi": label("add_to_tomorrow", None), "reason_vi": reason})
    return offers
