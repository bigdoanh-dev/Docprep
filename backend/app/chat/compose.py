"""Prompt assembly (G20, step 2.5.1): the one place a model prompt's user message is put together.

A prompt is built only from parts of an allowlisted kind, then the evidence passages. No part kind
exists for a pseudonym, a session id, a time, an IP address or a device, so there is nothing to fill
with them. A new source of context (a learner summary, past turns) must be added here as a new kind,
on purpose, and is then covered by the same budget and by the gateway's identifier check.

The budget is an estimate in tokens, without a tokenizer: the prompt may not outgrow the model's
context. When it would, the lowest-ranked passages are left out, never cut mid-text (a quote the
post-check compares must stay whole), and at least the best passage is always kept. Callers check
the answer against the passages that were actually sent, which `Composed.passages` returns.
"""
import math
from dataclasses import dataclass
from typing import Callable, Literal

from app.chat.retrieval import Passage
from app.config import settings

PartKind = Literal["question", "instruction", "previous_answer", "item"]
ALLOWED_KINDS: frozenset[str] = frozenset(PartKind.__args__)
EVIDENCE_HEADER = "Passages:\n"
# Characters per token for Vietnamese text in the tokenizers of the configured models: a cautious
# figure, so the estimate errs on the large side.
CHARS_PER_TOKEN = 3


@dataclass(frozen=True)
class Part:
    """A piece of the prompt: its kind says where it comes from; text carries its own separators."""
    kind: PartKind
    text: str

    def __post_init__(self):
        if self.kind not in ALLOWED_KINDS:
            raise ValueError(f"prompt part kind not allowed: {self.kind}")


@dataclass(frozen=True)
class Composed:
    user: str
    passages: list[Passage]       # the passages sent, best first; fewer than given when the budget was short
    dropped: int                  # how many passages the budget left out


def source_label(p: Passage) -> str:
    return f"{p.document_title}, {'tr. ' + str(p.page_start) if p.page_start else p.article}"


def evidence_block(passages: list[Passage], label: Callable[[Passage], str] = source_label) -> str:
    return "\n\n".join(f"[{p.id}] ({label(p)})\n{p.text}" for p in passages)


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def budget() -> int:
    return settings()["chat"]["prompt_token_budget"]


def compose(parts: list[Part], passages: list[Passage], *, system: str = "",
            label: Callable[[Passage], str] = source_label, max_tokens: int | None = None) -> Composed:
    """The parts in order, then the evidence. `system` counts toward the budget but is not included."""
    limit = budget() if max_tokens is None else max_tokens
    head = "".join(part.text for part in parts) + EVIDENCE_HEADER
    kept = list(passages)
    while len(kept) > 1 and estimate_tokens(system + head + evidence_block(kept, label)) > limit:
        kept.pop()
    return Composed(head + evidence_block(kept, label), kept, len(passages) - len(kept))
