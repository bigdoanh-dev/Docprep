"""Assemble a mock exam for one learner (handover/05-algorithms.md §7, greedy constrained selection).

Pure and deterministic: the same candidates and settings always give the same exam.
Two targets are balanced:
  - topics: how many questions each topic gets (shares come from blueprint weight, Elo mastery
    and whether the learner has completed that topic's content);
  - the mix: new questions, questions last answered wrong, and review questions (last answered
    correctly).
When both cannot be met, topic balance is kept and the mix gives way.
Nothing here predicts an exam outcome.
"""
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone

BUCKETS = ("new", "wrong", "review")
# Wrong and review questions are scarce and tied to particular topics, so they take their
# topic slots first; new questions are plentiful and fill what is left.
PICK_ORDER = ("wrong", "review", "new")
MIN_WEAKNESS = 0.1  # a mastered topic still appears now and then
_NEVER = datetime.min.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class Candidate:
    id: str
    topic: str
    bucket: str                 # "new" | "wrong" | "review", from the learner's latest answer
    p_correct: float            # Elo: chance this learner answers it correctly
    last_seen: datetime | None  # when it was last answered (None for new questions)


@dataclass(frozen=True)
class Plan:
    question_ids: list[str]
    composition: dict[str, int]  # how many new / wrong / review questions
    topics: dict[str, int]       # how many questions per topic


def topic_shares(topics: list, completed: set[str], neutral_mastery: float, unstudied_factor: float) -> dict[str, float]:
    """Relative weight of each topic in the exam.

    blueprint weight x weakness (1 - mastery from Elo; an unassessed topic counts as neutral)
    x 1 for a topic whose content the learner has completed, `unstudied_factor` otherwise.
    `topics` are engine.priority.TopicState values.
    """
    shares = {}
    for t in topics:
        mastery = neutral_mastery if t.mastery is None else t.mastery
        studied = 1.0 if t.code in completed else unstudied_factor
        shares[t.code] = t.weight * max(1.0 - mastery, MIN_WEAKNESS) * studied
    return shares


def allocate(shares: dict[str, float], n: int, caps: dict[str, int]) -> dict[str, int]:
    """Split n into whole numbers in proportion to `shares` (largest remainders), never more
    than `caps` allows; what a capped key cannot take goes to the others."""
    out = {k: 0 for k in shares}
    keys = [k for k in shares if shares[k] > 0 and caps.get(k, 0) > 0]
    left = min(n, sum(caps[k] for k in keys))
    while left > 0 and keys:
        total = sum(shares[k] for k in keys)
        ideal = {k: left * shares[k] / total for k in keys}
        give = {k: min(int(ideal[k]), caps[k] - out[k]) for k in keys}
        rest = left - sum(give.values())
        for k in sorted(keys, key=lambda k: (-(ideal[k] - int(ideal[k])), -shares[k], k)):
            if rest == 0:
                break
            if give[k] < caps[k] - out[k]:
                give[k] += 1
                rest -= 1
        for k in keys:
            out[k] += give[k]
        left = rest
        keys = [k for k in keys if out[k] < caps[k]]
    return out


def assemble(candidates: list[Candidate], n: int, topic_shares: dict[str, float], mix: dict[str, float],
             target_p: float) -> Plan:
    pool = sorted(candidates, key=lambda c: c.id)
    n = min(n, len(pool))
    topic_left = allocate(topic_shares, n, Counter(c.topic for c in pool))
    bucket_left = allocate({b: mix.get(b, 0.0) for b in BUCKETS}, n, Counter(c.bucket for c in pool))

    def fit(c: Candidate):
        # New questions: closest to the target chance of a correct answer (desirable difficulty).
        # Wrong and review questions: the one not seen for longest comes back first.
        return abs(c.p_correct - target_p) if c.bucket == "new" else (c.last_seen or _NEVER)

    def preference(c: Candidate):
        wanted = bucket_left[c.bucket] > 0
        order = PICK_ORDER.index(c.bucket) if wanted else BUCKETS.index(c.bucket)
        return (not wanted, order, -topic_left.get(c.topic, 0), fit(c), c.id)

    # Constraint levels, strictest first. Topic balance outlasts the mix (level 2 before level 3).
    levels = (
        lambda c: topic_left.get(c.topic, 0) > 0 and bucket_left[c.bucket] > 0,
        lambda c: topic_left.get(c.topic, 0) > 0,
        lambda c: bucket_left[c.bucket] > 0,
        lambda c: True,
    )
    chosen: list[Candidate] = []
    while len(chosen) < n:
        for allowed in levels:
            options = [c for c in pool if allowed(c)]
            if options:
                break
        pick = min(options, key=preference)
        pool.remove(pick)
        chosen.append(pick)
        if topic_left.get(pick.topic, 0) > 0:
            topic_left[pick.topic] -= 1
        if bucket_left[pick.bucket] > 0:
            bucket_left[pick.bucket] -= 1

    composition = Counter(c.bucket for c in chosen)
    return Plan(question_ids=[c.id for c in chosen],
                composition={b: composition.get(b, 0) for b in BUCKETS},
                topics=dict(sorted(Counter(c.topic for c in chosen).items())))
