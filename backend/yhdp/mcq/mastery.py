"""Learner model, phase 1: per-vấn đề mastery as a Beta estimate over the attempts log.

Nothing is stored: it is recomputed from mcq_attempts on every read, counting only items that
are still usable, so when a reviewer rejects an item its answers stop counting for everyone.
"""

import sqlite3
from datetime import datetime

from yhdp.mcq.deck import now_utc
from yhdp.mcq.items import USABLE

PRIOR = 1.0                      # Beta(1, 1): 50% before any answer
HALF_LIFE_DAYS = 21              # older answers count less
CREDIT = {"sure": 1.0, "unsure": 0.7, "guess": 0.3, None: 0.8}  # None = exam, not asked
CONFIDENT_MISS = 1.5             # a confident wrong answer is stronger evidence of a gap


def mastery(con: sqlite3.Connection, username: str,
            now: datetime | None = None) -> dict[int, dict]:
    """van_de → {"p": estimated P(correct), "n": answers, "correct": n correct, "de_muc"}."""
    now = now or now_utc()
    out: dict[int, dict] = {}
    rows = con.execute(
        "SELECT a.correct, a.confidence, a.ts, i.van_de, i.de_muc FROM mcq_attempts a "
        "JOIN mcq_items i ON i.id = a.item_id WHERE a.username = ? AND i.status IN (?, ?)",
        (username, *USABLE))
    for r in rows:
        age = (now - datetime.fromisoformat(r["ts"] + "+00:00")).total_seconds() / 86400
        w = 0.5 ** (max(age, 0) / HALF_LIFE_DAYS)
        m = out.setdefault(r["van_de"], {"a": PRIOR, "b": PRIOR, "n": 0, "correct": 0,
                                         "de_muc": r["de_muc"]})
        m["n"] += 1
        if r["correct"]:
            m["correct"] += 1
            m["a"] += w * CREDIT.get(r["confidence"], CREDIT[None])
        else:
            m["b"] += w * (CONFIDENT_MISS if r["confidence"] == "sure" else 1.0)
    return {v: {"p": round(m["a"] / (m["a"] + m["b"]), 3), "n": m["n"], "correct": m["correct"],
                "de_muc": m["de_muc"]} for v, m in out.items()}


def need(m: dict[int, dict], van_de: int) -> float:
    """How much practice a vấn đề needs: 1 − mastery, 0.5 when never practised."""
    return 1 - m[van_de]["p"] if van_de in m else 1 - PRIOR / (2 * PRIOR)
