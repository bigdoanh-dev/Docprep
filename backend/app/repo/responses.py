"""Scored answers, mastery per topic, and the running statistics of a question."""
from datetime import datetime


def insert(conn, learner_id: int, question: dict, context: str, chosen: str | None, correct: bool, now: datetime, *,
           attempt_id: int | None = None, unit_session_id: int | None = None, unit_item_id: str | None = None,
           practice_set_id: int | None = None, time_ms: int | None = None) -> int:
    return conn.execute(
        """insert into item_response(learner_id, question_id, question_version, context, attempt_id,
             unit_session_id, unit_item_id, practice_set_id, chosen, correct, time_ms, created_at)
           values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning id""",
        (learner_id, question["id"], question["version"], context, attempt_id, unit_session_id, unit_item_id,
         practice_set_id, chosen, correct, time_ms, now)).fetchone()["id"]


def link_card(conn, response_id: int, card_id: int) -> None:
    conn.execute("update item_response set card_id = %s where id = %s", (card_id, response_id))


def mastery(conn, learner_id: int, competency_code: str) -> dict:
    """theta and the number of responses on a topic; zeros before the first answer."""
    return conn.execute("select theta, n_responses from mastery where learner_id = %s and competency_code = %s",
                        (learner_id, competency_code)).fetchone() or {"theta": 0.0, "n_responses": 0}


def mastery_rows(conn, learner_id: int) -> dict[str, dict]:
    return {r["competency_code"]: r for r in conn.execute(
        "select competency_code, theta, n_responses from mastery where learner_id = %s", (learner_id,))}


def set_mastery(conn, learner_id: int, competency_code: str, theta: float, now: datetime) -> None:
    conn.execute(
        """insert into mastery(learner_id, competency_code, theta, n_responses, updated_at) values (%s, %s, %s, 1, %s)
           on conflict (learner_id, competency_code)
           do update set theta = excluded.theta, n_responses = mastery.n_responses + 1, updated_at = excluded.updated_at""",
        (learner_id, competency_code, theta, now))


def set_difficulty(conn, question_id: str, version: int, b: float) -> None:
    """Addressed by version, not by status: a question retired mid-attempt is still scored."""
    conn.execute("update question set difficulty_b = %s, n_responses = n_responses + 1 where id = %s and version = %s",
                 (b, question_id, version))


def find_unit_response(conn, unit_session_id: int, unit_item_id: str) -> dict | None:
    return conn.execute("select * from item_response where unit_session_id = %s and unit_item_id = %s",
                        (unit_session_id, unit_item_id)).fetchone()


def last_for_question(conn, learner_id: int, question_id: str) -> dict | None:
    return conn.execute(
        "select * from item_response where learner_id = %s and question_id = %s order by id desc limit 1",
        (learner_id, question_id)).fetchone()
