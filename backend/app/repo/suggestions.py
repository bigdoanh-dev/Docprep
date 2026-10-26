"""Suggestions made after a chat answer, and what accepting one writes."""
from datetime import date, datetime


def insert(conn, learner_id: int, message_id: int, kind: str, competency_code: str, n_items: int | None,
           reason_vi: str, now: datetime) -> dict:
    return conn.execute(
        """insert into suggestion(learner_id, message_id, kind, competency_code, n_items, reason_vi, created_at)
           values (%s, %s, %s, %s, %s, %s, %s) returning id, kind, n_items, reason_vi""",
        (learner_id, message_id, kind, competency_code, n_items, reason_vi, now)).fetchone()


def of_messages(conn, message_ids: list[int]) -> dict[int, list[dict]]:
    """The suggestions of those messages, in the order they were made."""
    by_message: dict[int, list[dict]] = {}
    for row in conn.execute(
            "select id, message_id, kind, n_items, reason_vi from suggestion where message_id = any(%s) order by id",
            (message_ids,)):
        by_message.setdefault(row["message_id"], []).append(row)
    return by_message


def own(conn, learner_id: int, suggestion_id: int) -> dict | None:
    """The learner's own suggestion, held for the transaction: two taps are taken in turn."""
    return conn.execute("select * from suggestion where id = %s and learner_id = %s for update",
                        (suggestion_id, learner_id)).fetchone()


def mark_accepted(conn, suggestion_id: int, now: datetime) -> None:
    conn.execute("update suggestion set accepted_at = %s where id = %s", (now, suggestion_id))


def practice_set_of(conn, learner_id: int, competency_code: str, accepted_at: datetime) -> dict | None:
    """The set built when that suggestion was accepted: both were written with the same instant."""
    return conn.execute(
        """select id from practice_set where learner_id = %s and source = 'chat_suggestion' and competency_code = %s
           and created_at = %s order by id limit 1""", (learner_id, competency_code, accepted_at)).fetchone()


def addition_of(conn, suggestion_id: int) -> dict | None:
    return conn.execute("select for_date from session_addition where suggestion_id = %s", (suggestion_id,)).fetchone()


def add_to_day(conn, learner_id: int, for_date: date, competency_code: str, suggestion_id: int, now: datetime) -> None:
    conn.execute(
        "insert into session_addition(learner_id, for_date, competency_code, suggestion_id, created_at) values (%s, %s, %s, %s, %s)",
        (learner_id, for_date, competency_code, suggestion_id, now))
