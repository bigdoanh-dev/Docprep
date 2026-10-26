"""The activity log: what a learner did and when, under their pseudonym. Append-only.

The ministry dashboard and Nhịp học are computed from these rows, so every learner-facing use case
records one. A duration reported by the app is capped: a phone left open is not study time.
"""
from datetime import datetime, timedelta

from app.config import settings
from app.repo import activity as repo


def record(conn, learner_pid: str, kind: str, occurred_at: datetime, *, duration_ms: int | None = None,
           ref_type: str | None = None, ref_id: str | int | None = None, measured: bool = False) -> None:
    """`duration_ms` is what the app reported and is capped, unless `measured` says the server
    measured it itself (an exam, bounded by its own deadline)."""
    if duration_ms is not None and not measured:
        duration_ms = min(duration_ms, settings()["activity"]["max_duration_ms"])
    repo.insert(conn, learner_pid, kind, occurred_at, duration_ms, ref_type, None if ref_id is None else str(ref_id))


def record_visit(conn, learner_pid: str, now: datetime) -> None:
    """One visit per stretch of use: opening Home again within the gap is the same visit."""
    gap = timedelta(minutes=settings()["activity"]["visit_gap_minutes"])
    if not repo.happened_since(conn, learner_pid, "visit", now - gap):
        record(conn, learner_pid, "visit", now)
