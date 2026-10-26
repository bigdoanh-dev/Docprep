"""Topic priority (handover/05-algorithms.md §3). Pure and stable."""
from dataclasses import dataclass


@dataclass(frozen=True)
class TopicState:
    code: str
    name: str
    weight: float
    module_id: str
    mastery: float | None  # None = unassessed


def rank_topics(topics: list[TopicState], focus_module_ids: list[str], neutral_mastery: float) -> list[str]:
    def key(t: TopicState):
        mastery = neutral_mastery if t.mastery is None else t.mastery
        return (t.module_id not in focus_module_ids, -t.weight * (1.0 - mastery), t.code)

    return [t.code for t in sorted(topics, key=key)]
