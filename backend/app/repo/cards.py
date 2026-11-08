"""Revision cards and their reviews."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

from app.repo.content import ONCE_APPROVED
from app.config import settings


def create(conn, learner_id: int, question_id: str, context: str, front: str, back: str, citation: str,
           fsrs_card: dict, now: datetime) -> int | None:
    """At most one card per learner and question: the new card's id, or None when one exists."""
    row = conn.execute(
        """insert into card(learner_id, source_question_id, source_context, front, back, citation, fsrs_card, due_at)
           values (%s, %s, %s, %s, %s, %s, %s, %s)
           on conflict (learner_id, source_question_id) do nothing returning id""",
        (learner_id, question_id, context, front, back, citation, Jsonb(fsrs_card), now)).fetchone()
    return row["id"] if row else None


_DUE = "c.learner_id = %s and not c.suspended and c.due_at <= %s"


def budget(conn, learner_id: int, now: datetime) -> dict:
    """Every rating consumes a review; a card's first rating also consumes a new-card slot.

    Count history even for suspended cards, with the same local day as sessions.
    """
    zone = ZoneInfo(settings()["local_timezone"])
    start = datetime.combine(now.astimezone(zone).date(), time.min, tzinfo=zone)
    # Request time is captured before the learner lock. A later-arriving request may
    # commit first, so count its review too when it belongs to this same local day.
    end = start + timedelta(days=1)
    row = conn.execute(
        """select count(*) as reviews,
                  count(distinct r.card_id) filter (where not exists (
                    select 1 from card_review old where old.card_id = r.card_id and old.reviewed_at < %s
                  )) as new
           from card_review r join card c on c.id = r.card_id
           where c.learner_id = %s and r.reviewed_at >= %s and r.reviewed_at < %s""",
        (start, learner_id, start, end)).fetchone()
    limits = conn.execute("select new_cards_per_day, max_reviews_per_day from learner where id = %s",
                          (learner_id,)).fetchone()
    return {"reviews": max(0, limits["max_reviews_per_day"] - row["reviews"]),
            "new": max(0, limits["new_cards_per_day"] - row["new"])}


def available(conn, learner_id: int, now: datetime) -> list[dict]:
    """One budgeted queue shared by cards, decks, home, progress and the daily session."""
    left = budget(conn, learner_id, now)
    if not left["reviews"]:
        return []
    return conn.execute(
        f"""with waiting as (
              select c.id, c.due_at, c.reps,
                     sum(case when c.reps = 0 then 1 else 0 end) over (order by c.due_at, c.id) as new_rank
              from card c where {_DUE}
            ) select id, due_at from waiting where reps > 0 or new_rank <= %s
              order by due_at, id limit %s""", (learner_id, now, left["new"], left["reviews"])).fetchall()


def due(conn, learner_id: int, now: datetime, limit: int, offset: int = 0) -> list[dict]:
    """Cards due now, the longest overdue first, each with its question's topic and first source.
    A card outlives the retirement of its question, so the question is read in its approved
    version or, failing that, the last one that was approved; never in an unapproved draft."""
    return conn.execute(
        f"""select c.id, c.front, c.back, c.citation, c.source_context, c.fsrs_card,
                   q.competency_code, q.source_passage_ids[1] as source_passage_id
            from card c
            join lateral (select q.competency_code, q.source_passage_ids from question q
                          where q.id = c.source_question_id and {ONCE_APPROVED}
                          order by (q.status = 'approved') desc, q.version desc limit 1) q on true
            where c.id = any(%s)
            order by c.due_at, c.id""", ([r["id"] for r in available(conn, learner_id, now)[offset:offset + limit]],)).fetchall()


def due_counts(conn, learner_id: int, now: datetime, day_start: datetime) -> dict:
    """How many cards are due now, and how many of them were already due before the learner's day began."""
    queue = available(conn, learner_id, now)
    total = conn.execute(f"select count(*) n from card c where {_DUE}", (learner_id, now)).fetchone()["n"]
    return {"due": len(queue), "total": total, "overdue": sum(c["due_at"] < day_start for c in queue)}


def due_ids(conn, learner_id: int, now: datetime, limit: int) -> list[int]:
    """The cards due now, the longest overdue first: the order the due queue serves them in."""
    return [r["id"] for r in available(conn, learner_id, now)[:limit]]


def all_reviewed_since(conn, card_ids: list[int], since: datetime) -> bool:
    """Whether every one of those cards has a review at or after that time. A card the learner has
    suspended is no longer served, so it is not waited for."""
    waiting = conn.execute(
        """select count(*) n from card c where c.id = any(%s) and not c.suspended
           and not exists (select 1 from card_review r where r.card_id = c.id and r.reviewed_at >= %s)""",
        (card_ids, since)).fetchone()["n"]
    return waiting == 0


def count_due(conn, learner_id: int, now: datetime) -> int:
    return len(available(conn, learner_id, now))


def own_card(conn, learner_id: int, card_id: int) -> dict | None:
    """The learner's own card, locked for the review."""
    return conn.execute("select * from card where id = %s and learner_id = %s for update",
                        (card_id, learner_id)).fetchone()


def apply_review(conn, card_id: int, fsrs_card: dict, due_at: datetime, rating: int, scheduled_seconds: int,
                 time_ms: int | None, now: datetime) -> None:
    conn.execute(
        "update card set fsrs_card = %s, due_at = %s, reps = reps + 1, lapses = lapses + %s where id = %s",
        (Jsonb(fsrs_card), due_at, 1 if rating == 1 else 0, card_id))
    conn.execute(
        "insert into card_review(card_id, rating, reviewed_at, scheduled_seconds, time_ms) values (%s, %s, %s, %s, %s)",
        (card_id, rating, now, scheduled_seconds, time_ms))


def set_suspended(conn, card_id: int, suspended: bool) -> dict:
    return conn.execute("update card set suspended = %s where id = %s returning id, suspended",
                        (suspended, card_id)).fetchone()
