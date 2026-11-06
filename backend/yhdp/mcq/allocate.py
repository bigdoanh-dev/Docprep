"""Question allocation for practice sets and mock exams (design §7).

Đề mục get questions by blueprint midpoint weights with largest-remainder rounding, then each
range's minimum where the set size allows, capped by what the bank has. Small đề mục (2.5–3.5%)
round to 0 in a 10-question set; `rotation` (the learner's set count) shifts near-ties so they
take turns instead of being skipped every time. Miền (18–22 / 37–43 / 32–38 / 4–6 %) are
balanced when picking items inside each đề mục.
"""

import math
import random


def largest_remainder(weights: dict, n: int, rotation: int = 0) -> dict:
    """Split n across keys in proportion to weights; leftover units go to the largest fractional
    parts, with near-ties (within 0.1) broken by rotation order."""
    total = sum(weights.values())
    if n <= 0 or total <= 0:
        return {k: 0 for k in weights}
    exact = {k: n * w / total for k, w in weights.items()}
    out = {k: math.floor(x) for k, x in exact.items()}
    keys = list(weights)
    rot = {k: (i - rotation) % len(keys) for i, k in enumerate(keys)}
    order = sorted(keys, key=lambda k: (-round((exact[k] - out[k]) * 10), rot[k]))
    for k in order[: n - sum(out.values())]:
        out[k] += 1
    return out


def allocate(size: int, ranges: dict[int, tuple[float, float]], available: dict[int, int],
             rotation: int = 0) -> tuple[dict[int, int], list[str]]:
    """Questions per đề mục for a set of `size`, plus notes on where the bank fell short."""
    notes = []
    live = {d: r for d, r in ranges.items() if available.get(d, 0) > 0}
    for d in ranges:
        if d not in live:
            notes.append(f"Đề mục {d}: chưa có câu hỏi trong ngân hàng")
    if not live:
        return {d: 0 for d in ranges}, notes
    size = min(size, sum(available[d] for d in live))
    quota = largest_remainder({d: (lo + hi) / 2 for d, (lo, hi) in live.items()}, size, rotation)
    # Each range's minimum where the set is big enough, taken from whoever has the most slack.
    scale = sum((lo + hi) / 2 for lo, hi in live.values()) / 100
    mins = {d: math.floor(size * lo / 100 / scale) for d, (lo, _) in live.items()}
    if sum(mins.values()) <= size:
        for d in live:
            while quota[d] < mins[d]:
                donor = max(live, key=lambda x: quota[x] - mins[x])
                if quota[donor] - mins[donor] <= 0:
                    break
                quota[donor] -= 1
                quota[d] += 1
    # Đề mục rounded to 0 take turns: each set gives one of them a question from the most
    # over-allocated đề mục, cycling with `rotation`.
    exact = {d: size * (lo + hi) / 2 / 100 / scale for d, (lo, hi) in live.items()}
    zeros = [d for d in live if quota[d] == 0]
    if zeros and size >= len(live) // 2:
        d = zeros[rotation % len(zeros)]
        donors = [x for x in live if quota[x] > 1]
        if donors:
            donor = max(donors, key=lambda x: quota[x] - exact[x])
            quota[donor] -= 1
            quota[d] += 1
    # Cap by availability; hand the overflow to đề mục that still have unused items.
    overflow = 0
    for d in live:
        if quota[d] > available[d]:
            overflow += quota[d] - available[d]
            notes.append(f"Đề mục {d}: chỉ có {available[d]} câu, ít hơn tỷ lệ đề thi ({quota[d]})")
            quota[d] = available[d]
    while overflow:
        spare = [d for d in live if quota[d] < available[d]]
        if not spare:
            break
        d = max(spare, key=lambda x: sum(live[x]) / 2 / (quota[x] + 1))
        quota[d] += 1
        overflow -= 1
    return {d: quota.get(d, 0) for d in ranges}, notes


def pick_items(candidates: list[dict], k: int, mien_weights: dict[str, float],
               counts: dict[str, int], rnd: random.Random) -> list[dict]:
    """Pick k items, unseen first, steering miền groups (first digit of the miền id) toward
    their blueprint weights. `counts` is updated in place across đề mục."""
    pool = candidates[:]
    rnd.shuffle(pool)
    pool.sort(key=lambda c: c.get("seen", 0))
    chosen = []


    def deficit(c: dict, total: int) -> float:
        g = c["mien"].split(".")[0]
        return mien_weights.get(g, 0) / 100 - counts.get(g, 0) / total

    while pool and len(chosen) < k:
        total = sum(counts.values()) + 1
        best_seen = pool[0].get("seen", 0)
        tier = [c for c in pool if c.get("seen", 0) == best_seen]
        pick = max(tier, key=lambda c: deficit(c, total))
        pool.remove(pick)
        chosen.append(pick)
        g = pick["mien"].split(".")[0]
        counts[g] = counts.get(g, 0) + 1
    return chosen
