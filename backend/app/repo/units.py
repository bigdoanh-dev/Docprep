"""Units, their items, and a learner's pass through a unit."""
from datetime import datetime


def get(conn, unit_id: str) -> dict | None:
    return conn.execute("select * from unit where id = %s", (unit_id,)).fetchone()


def item(conn, item_id: str) -> dict:
    return conn.execute("select * from unit_item where id = %s", (item_id,)).fetchone()


def quiz_item(conn, unit_id: str, item_id: str) -> dict | None:
    return conn.execute("select * from unit_item where id = %s and unit_id = %s and kind = 'quiz'",
                        (item_id, unit_id)).fetchone()


def authored_item_ids(conn, unit_id: str) -> list[str]:
    """The unit's items in authored order, without the remediation items a wrong answer may add."""
    return [r["id"] for r in conn.execute(
        "select id from unit_item where unit_id = %s and kind <> 'remediation' order by ord", (unit_id,))]


def remediation_after(conn, unit_id: str, item_id: str) -> dict | None:
    return conn.execute(
        "select id, note from unit_item where unit_id = %s and kind = 'remediation' and after_item_id = %s",
        (unit_id, item_id)).fetchone()


def open_session(conn, learner_id: int, unit_id: str) -> dict | None:
    """The learner's unfinished pass through the unit. Locked: two taps of the same button wait in turn."""
    return conn.execute(
        """select * from unit_session where learner_id = %s and unit_id = %s and not done
           order by id desc limit 1 for update""", (learner_id, unit_id)).fetchone()


def create_session(conn, learner_id: int, unit_id: str, queue: list[str], now: datetime) -> dict:
    return conn.execute(
        """insert into unit_session(learner_id, unit_id, queue, started_at, updated_at)
           values (%s, %s, %s, %s, %s) returning *""", (learner_id, unit_id, queue, now, now)).fetchone()


def record_answer(conn, session_id: int, queue: list[str], card_created: bool, now: datetime) -> dict:
    return conn.execute(
        """update unit_session set queue = %s, cards_created = cards_created + %s, updated_at = %s
           where id = %s returning *""", (queue, 1 if card_created else 0, now, session_id)).fetchone()


def move_to(conn, session_id: int, cursor: int, done: bool, now: datetime) -> dict:
    return conn.execute(
        "update unit_session set cursor = %s, done = %s, updated_at = %s where id = %s returning *",
        (cursor, done, now, session_id)).fetchone()


def finished(conn, learner_id: int, unit_id: str) -> bool:
    return conn.execute("select 1 from unit_session where learner_id = %s and unit_id = %s and done limit 1",
                        (learner_id, unit_id)).fetchone() is not None


def next_unfinished(conn, learner_id: int, module_ids: list[str]) -> dict | None:
    """The first unit the learner has not finished, by học phần in the order given and then in
    authored order. `remaining` is what is left of an open pass, else the unit's authored items."""
    return conn.execute(
        """select u.id as unit_id, m.short_name as module_short_name,
                  coalesce(
                    (select cardinality(s.queue) - s.cursor from unit_session s
                     where s.learner_id = %(learner)s and s.unit_id = u.id and not s.done order by s.id desc limit 1),
                    (select count(*) from unit_item i where i.unit_id = u.id and i.kind <> 'remediation')) as remaining
           from unit u join module m on m.id = u.module_id
           where u.module_id = any(%(modules)s)
             and not exists (select 1 from unit_session s
                             where s.learner_id = %(learner)s and s.unit_id = u.id and s.done)
           order by array_position(%(modules)s, u.module_id), u.ord limit 1""",
        {"learner": learner_id, "modules": module_ids}).fetchone()


def awaiting_answer(conn, learner_id: int, question_id: str) -> bool:
    """Whether the question is the quiz item the learner is on, unanswered, in one of their open passes."""
    return conn.execute(
        """select 1 from unit_session s join unit_item i on i.id = s.queue[s.cursor + 1]
           where s.learner_id = %s and not s.done and i.kind = 'quiz' and i.question_id = %s
             and not exists (select 1 from item_response r where r.unit_session_id = s.id and r.unit_item_id = i.id)
           limit 1""", (learner_id, question_id)).fetchone() is not None
