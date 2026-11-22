"""Rerank and sufficiency gate for hybrid retrieval: one model call scores the RRF top 30 (0–3).

The model reached by API key scores every pooled passage; the best `top_k` by score are sent to the
answer model, ties keeping the RRF order. If even the best scores below `min_score`, the turn ends as
insufficient_evidence before any answer is written: the gate the hybrid path lacked.

Measured on the silver set (experiments/retrieval_eval, 2026-11-22): Hit@5 81% → 100%, Hit@1 38% → 96%,
and a gate at 2 kept 0/79 valid questions out and stopped 24/24 out-of-scope ones (Gemini Flash-Lite).

The call is optional: when it fails (quota, overload, a malformed reply), retrieval falls back to the
RRF top `top_k` with no gate, as before. A cancellation or a deadline still ends the turn.
"""
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from app.chat.retrieval import Found
from app.config import settings
from app.gateway import GatewayError, ModelUnavailable

PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "rerank_v1.txt"
# ask(system, user) -> parsed JSON or None
Ask = Callable[[str, str], dict | None]


@dataclass(frozen=True)
class Reranked:
    found: Found               # what the answer model gets; empty when the gate stopped the turn
    gated: bool                # True: the best score was below min_score
    failure: str | None        # why the RRF order was kept ("model_error", "malformed"), else None
    top_score: int | None


def cfg() -> dict:
    return settings()["retrieval"]["rerank"]


def _scores(data: dict | None, n: int) -> list[int] | None:
    raw = data.get("scores") if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        return None
    got = {}
    for k, v in raw.items():
        m = re.fullmatch(r"P?(\d+)", str(k).strip())
        if m and isinstance(v, (int, float)) and 0 <= v <= 3:
            got[int(m.group(1))] = int(v)
    if not got:
        return None
    return [got.get(i + 1, 0) for i in range(n)]       # a passage left unscored counts as unrelated


def user_message(question: str, found: Found, chars: int) -> str:
    blocks = "\n\n".join(f"[P{i + 1}] ({p.document_title} › {p.chapter or ''} › {p.section or ''})\n{p.text[:chars]}"
                         for i, p in enumerate(found.passages))
    return f"Câu hỏi: {question}\n\n{blocks}"


def apply(ask: Ask, question: str, pool: Found) -> Reranked:
    c = cfg()
    keep = lambda: Found(pool.passages[:c["top_k"]], pool.nearest)
    if not pool.passages:
        return Reranked(pool, False, None, None)
    try:
        scores = _scores(ask(PROMPT.read_text(encoding="utf-8"), user_message(question, pool, c["passage_chars"])),
                         len(pool.passages))
    except (GatewayError, ModelUnavailable):            # the chat worker raises the latter for a refused call
        return Reranked(keep(), False, "model_error", None)
    if scores is None:
        return Reranked(keep(), False, "malformed", None)
    best = max(scores)
    if best < c["min_score"]:
        # Nothing answers it: no passage is sent. The nearest one still names where the search came closest.
        return Reranked(Found([], pool.passages[0]), True, None, best)
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    chosen = [replace(pool.passages[i], score=float(scores[i])) for i in order[:c["top_k"]] if scores[i] > 0]
    return Reranked(Found(chosen, pool.nearest), False, None, best)
