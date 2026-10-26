"""Practice sets, and what the rules read to build one."""
from datetime import datetime

from psycopg.types.json import Jsonb


def create(conn, learner_id: int, source: str, competency_code: str, question_ids: list[str],
           question_versions: dict[str, int], reasons: dict[str, str], now: datetime) -> dict:
    return conn.execute(
        """insert into practice_set(learner_id, source, competency_code, question_ids, question_versions, reasons,
             created_at) values (%s, %s, %s, %s, %s, %s, %s) returning *""",
        (learner_id, source, competency_code, question_ids, Jsonb(question_versions), Jsonb(reasons), now)).fetchone()


def own_set(conn, learner_id: int, set_id: int, lock: bool = False) -> dict | None:
    """The learner's own set. lock=True holds the row, so two answers to one set are taken in turn."""
    return conn.execute("select * from practice_set where id = %s and learner_id = %s" + (" for update" if lock else ""),
                        (set_id, learner_id)).fetchone()


def responses(conn, set_id: int) -> dict[str, dict]:
    """The set's answers by question id. A question is answered once: the set row is locked while
    answering, and a unique index backs that."""
    return {r["question_id"]: r for r in conn.execute(
        "select * from item_response where practice_set_id = %s order by id", (set_id,))}


def complete(conn, set_id: int, summary: dict, now: datetime) -> dict:
    return conn.execute("update practice_set set completed_at = %s, summary = %s where id = %s returning *",
                        (now, Jsonb(summary), set_id)).fetchone()


# `without_set` leaves one practice set's answers out of the count: what the learner's record would
# be had that set not been answered. The adaptation summary compares the two.
_NOT_THIS_SET = "(%(without)s::int is null or r.practice_set_id is distinct from %(without)s)"


def wrong_counts(conn, learner_id: int, since: datetime, without_set: int | None = None) -> dict[str, int]:
    """Wrong answers per competency since that time, from quizzes, practice and exams alike."""
    return {r["competency_code"]: r["n"] for r in conn.execute(
        f"""select q.competency_code, count(*) as n
            from item_response r join question q on q.id = r.question_id and q.version = r.question_version
            where r.learner_id = %(learner)s and not r.correct and r.created_at > %(since)s and {_NOT_THIS_SET}
            group by q.competency_code""", {"learner": learner_id, "since": since, "without": without_set})}


def seen(conn, learner_id: int, competency_code: str, without_set: int | None = None, *,
         synthetic: bool) -> list[dict]:
    """Every approved question of the competency, with the learner's latest answer to it in any context.
    The sample bank is offered to synthetic learners only."""
    return conn.execute(
        f"""select q.id as question_id, q.version,
                   (select max(r.created_at) from item_response r
                    where r.learner_id = %(learner)s and r.question_id = q.id and {_NOT_THIS_SET}) as last_seen
            from question q
            where q.status = 'approved' and q.competency_code = %(code)s and (not q.is_synthetic or %(synthetic)s)
            order by q.id""",
        {"learner": learner_id, "code": competency_code, "without": without_set, "synthetic": synthetic}).fetchall()


def answered_since(conn, learner_id: int, question_ids: list[str], since: datetime) -> set[str]:
    """Which of those questions the learner has answered, anywhere, since that time."""
    return {r["question_id"] for r in conn.execute(
        """select distinct question_id from item_response
           where learner_id = %s and question_id = any(%s) and created_at >= %s""", (learner_id, question_ids, since))}


def awaiting_answer(conn, learner_id: int, question_id: str) -> bool:
    """Whether the question is an unanswered one of an open practice set of the learner."""
    return conn.execute(
        """select 1 from practice_set p
           where p.learner_id = %s and p.completed_at is null and %s = any(p.question_ids)
             and not exists (select 1 from item_response r where r.practice_set_id = p.id and r.question_id = %s)
           limit 1""", (learner_id, question_id, question_id)).fetchone() is not None
