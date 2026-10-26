"""Exam forms, attempts and their saved answers; what an assembled form is chosen from."""
from datetime import datetime

from psycopg.types.json import Jsonb


def form(conn, form_id: str, synthetic: bool) -> dict | None:
    """An approved form the learner may open. A form of the sample bank is for synthetic learners only."""
    return conn.execute(
        "select * from exam_form where id = %s and status = 'approved' and (not is_synthetic or %s)",
        (form_id, synthetic)).fetchone()


def form_of_attempt(conn, form_id: str) -> dict:
    """The form an existing attempt was started on, whatever its status is now."""
    return conn.execute("select * from exam_form where id = %s", (form_id,)).fetchone()


def forms(conn, kinds: list[str], synthetic: bool) -> list[dict]:
    return conn.execute(
        """select * from exam_form where status = 'approved' and kind = any(%s) and (not is_synthetic or %s)
           order by id""", (kinds, synthetic)).fetchall()


def attempts_used(conn, learner_id: int, form_id: str) -> int:
    return conn.execute("select count(*) c from exam_attempt where learner_id = %s and form_id = %s",
                        (learner_id, form_id)).fetchone()["c"]


def finished(conn, learner_id: int, form_id: str) -> list[dict]:
    """Handed-in attempts, newest first."""
    return conn.execute(
        """select id, started_at, submitted_at, score, auto_submitted from exam_attempt
           where learner_id = %s and form_id = %s and submitted_at is not null
           order by submitted_at desc, id desc""", (learner_id, form_id)).fetchall()


def running(conn, learner_id: int, form_id: str, lock: bool = False) -> dict | None:
    return conn.execute(
        """select * from exam_attempt where learner_id = %s and form_id = %s and submitted_at is null
           order by id desc limit 1""" + (" for update" if lock else ""), (learner_id, form_id)).fetchone()


def expired(conn, learner_id: int, now: datetime) -> list[dict]:
    """Attempts still open although their deadline has passed. Locked for the hand-in."""
    return conn.execute(
        """select * from exam_attempt where learner_id = %s and submitted_at is null and deadline_at < %s
           order by id for update""", (learner_id, now)).fetchall()


def attempt(conn, learner_id: int, attempt_id: int) -> dict | None:
    """The learner's own attempt, locked: a save and a hand-in of the same attempt wait in turn."""
    return conn.execute("select * from exam_attempt where id = %s and learner_id = %s for update",
                        (attempt_id, learner_id)).fetchone()


def create_attempt(conn, learner_id: int, form_id: str, order: list[str], option_orders: dict,
                   question_versions: dict[str, int], now: datetime, deadline: datetime,
                   assembly: dict | None) -> dict:
    return conn.execute(
        """insert into exam_attempt(learner_id, form_id, question_order, option_orders, question_versions,
             started_at, deadline_at, assembly) values (%s, %s, %s, %s, %s, %s, %s, %s) returning *""",
        (learner_id, form_id, order, Jsonb(option_orders), Jsonb(question_versions), now, deadline,
         Jsonb(assembly) if assembly else None)).fetchone()


def close(conn, attempt_id: int, now: datetime, auto: bool, score: int, summary: dict) -> dict:
    return conn.execute(
        """update exam_attempt set submitted_at = %s, auto_submitted = %s, score = %s, summary = %s
           where id = %s returning *""", (now, auto, score, Jsonb(summary), attempt_id)).fetchone()


def answers(conn, attempt_id: int) -> dict[str, dict]:
    return {r["question_id"]: r for r in conn.execute(
        "select question_id, chosen, flagged from attempt_answer where attempt_id = %s", (attempt_id,))}


def save_answer(conn, attempt_id: int, question_id: str, chosen: str | None, flagged: bool, now: datetime) -> None:
    """Keeps the latest choice and counts how often it changed."""
    conn.execute(
        """insert into attempt_answer(attempt_id, question_id, chosen, flagged, changes, updated_at)
           values (%s, %s, %s, %s, %s, %s)
           on conflict (attempt_id, question_id) do update set
             changes = attempt_answer.changes + (attempt_answer.chosen is distinct from excluded.chosen)::int,
             chosen = excluded.chosen, flagged = excluded.flagged, updated_at = excluded.updated_at""",
        (attempt_id, question_id, chosen, flagged, 1 if chosen is not None else 0, now))


def completed_topics(conn, learner_id: int) -> set[str]:
    """Topics whose Luyện tập content the learner has finished: the topic of every completed unit,
    plus the topics of the quiz questions inside it."""
    rows = conn.execute(
        """select u.competency_code as code from unit u
           where u.id in (select unit_id from unit_session where learner_id = %(l)s and done)
           union
           select q.competency_code from unit_item i join question q on q.id = i.question_id and q.status = 'approved'
           where i.unit_id in (select unit_id from unit_session where learner_id = %(l)s and done)""",
        {"l": learner_id}).fetchall()
    return {r["code"] for r in rows}


def candidate_rows(conn, learner_id: int, synthetic: bool) -> list[dict]:
    """Every approved question with the learner's latest answer to it, in a unit quiz or an exam."""
    return conn.execute(
        """select q.id, q.competency_code, q.difficulty_b, last.correct, last.created_at
           from question q
           left join lateral (
             select r.correct, r.created_at from item_response r
             where r.learner_id = %s and r.question_id = q.id order by r.created_at desc, r.id desc limit 1
           ) last on true
           where q.status = 'approved' and (not q.is_synthetic or %s) order by q.id""",
        (learner_id, synthetic)).fetchall()


def next_mock(conn, learner_id: int, synthetic: bool) -> dict | None:
    """The mock form Home offers: the first the learner has not finished, else the first."""
    return conn.execute(
        """select f.id, f.title, coalesce(f.n_questions, cardinality(f.question_ids)) as n, f.seconds_per_question as spq
           from exam_form f
           where f.kind in ('mock', 'demo_short') and f.status = 'approved' and (not f.is_synthetic or %s)
           order by exists(select 1 from exam_attempt a where a.form_id = f.id and a.learner_id = %s
                           and a.submitted_at is not null), f.id limit 1""", (synthetic, learner_id)).fetchone()


def in_running_attempt(conn, learner_id: int, question_id: str, now: datetime) -> bool:
    """Whether the question is part of an exam the learner is sitting right now."""
    return conn.execute(
        """select 1 from exam_attempt where learner_id = %s and submitted_at is null and deadline_at > %s
           and %s = any(question_order) limit 1""", (learner_id, now, question_id)).fetchone() is not None
