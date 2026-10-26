"""The sample cohort: a flagged sample question bank and synthetic learners whose history is written
by the real services. Dev and test only.

    python -m seed.cohort --learners 300 --weeks 12 --seed 42

Order matters. The approved sample bank is dated before the first learner; then the people; then
each learner's history; then the rest of the bank's review history, dated inside the window, so no
learner was served an item before its approval.
"""
import time
from datetime import datetime, timedelta, timezone

from app.config import app_env
from seed.blueprint import load_blueprint, validate_blueprint
from seed.cohort import bank, logs, people, simulate
from seed.cohort.params import rng_for
from seed.dev import ensure_demo_reviewers


def _count(conn, sql: str) -> int:
    return conn.execute(f"select count(*) n from {sql}").fetchone()["n"]


def run(conn, learners: int, weeks: int, seed: int, end: datetime | None = None) -> dict:
    """Generate the cohort and return a summary of what was written. Commits as it goes."""
    if app_env() == "production":
        raise RuntimeError("the sample cohort is for dev and test: it writes synthetic learners and sample questions")
    # Arguments first: a run refused after the sample bank is written would leave it behind, and every
    # later run would then be refused as "a cohort already exists".
    if weeks < 1:
        raise ValueError("a cohort needs at least one week")
    people.school_sizes(learners)
    if _count(conn, "learner where is_synthetic") or _count(conn, "question where is_synthetic"):
        # The activity log is append-only, so a second run cannot clean up after the first.
        raise RuntimeError("a cohort already exists: run `python -m app.cli reset-dev` first, then the cohort")
    if not _count(conn, "core_issue"):
        raise RuntimeError("the blueprint is not loaded: run `python -m app.cli seed` first")
    blueprint = load_blueprint()
    errors = validate_blueprint(blueprint)
    if errors:
        raise ValueError("invalid blueprint:\n" + "\n".join(errors))

    began = time.monotonic()
    end = end or datetime.now(timezone.utc)
    start = end - timedelta(weeks=weeks)
    reviewers = ensure_demo_reviewers(conn)

    bank.write_core(conn, blueprint, reviewers, start, rng_for(seed, "bank"))
    conn.commit()
    sims = people.enrol(conn, learners, start, end, reviewers, seed)
    conn.commit()

    keys = bank.answer_keys(conn)
    visits: dict[str, list[datetime]] = {}
    for done, sim in enumerate(sims, start=1):
        times = simulate.run_learner(conn, sim, keys, end, seed)
        if sim.leaves_at is None:       # a deleted account's reports are erased with it
            visits[sim.learner["pseudonym_id"]] = times
        if done % 25 == 0 or done == len(sims):
            print(f"  {done} / {len(sims)} learners, {time.monotonic() - began:.0f} s", flush=True)

    bank.write_pipeline(conn, blueprint, reviewers, start, end, rng_for(seed, "pipeline"))
    logs.write_error_reports(conn, visits, end, rng_for(seed, "reports"))
    conn.commit()
    return summary(conn, start, end, time.monotonic() - began)


def summary(conn, start: datetime, end: datetime, seconds: float) -> dict:
    """What a cohort database holds, for reading against `params.py`."""

    def rows(sql: str) -> list[dict]:
        return conn.execute(sql).fetchall()

    scores = [r["score"] for r in rows("select score from exam_attempt where submitted_at is not null order by score")]
    return {
        "window": [start.isoformat(), end.isoformat()], "seconds": round(seconds),
        "schools": rows(
            """select o.name, o.region, count(c.id) as issued, count(c.activated_at) as activated,
                      (select count(*) from learner l where l.organisation_id = o.id) as learners
               from organisation o left join activation_code c on c.organisation_id = o.id
               where o.is_synthetic group by o.id order by o.name"""),
        "learners": _count(conn, "learner where is_synthetic"),
        "research_consent": _count(conn, "consent_record where kind = 'research' and withdrawn_at is null"),
        "withdrawals": _count(conn, "consent_record where kind = 'research' and withdrawn_at is not null"),
        "deletions": _count(conn, "deletion_request"),
        "events": {r["kind"]: r["n"] for r in rows(
            "select kind, count(*) n from activity_event group by kind order by kind")},
        "events_after_end": conn.execute(
            "select count(*) n from activity_event where occurred_at > %s", (end,)).fetchone()["n"],
        "responses": {r["context"]: r["n"] for r in rows(
            "select context, count(*) n from item_response group by context order by context")},
        "mock_attempts": len(scores),
        "mock_median_score": scores[len(scores) // 2] if scores else None,
        "cards": _count(conn, "card"), "card_reviews": _count(conn, "card_review"),
        "practice_sets_completed": _count(conn, "practice_set where completed_at is not null"),
        "chat_answers": {r["state"]: r["n"] for r in rows(
            "select state, count(*) n from chat_message where role = 'assistant' group by state order by state")},
        "sample_questions": {r["status"]: r["n"] for r in rows(
            "select status, count(*) n from question where is_synthetic group by status order by status")},
        "error_reports": {r["status"]: r["n"] for r in rows(
            "select status, count(*) n from error_report group by status order by status")},
    }
