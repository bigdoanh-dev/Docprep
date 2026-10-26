"""The daily session as built for a learner's local day, and what was added to it from chat."""
from datetime import date, datetime

from psycopg.types.json import Jsonb


def find(conn, learner_id: int, local_date: date) -> dict | None:
    return conn.execute("select * from daily_session where learner_id = %s and local_date = %s",
                        (learner_id, local_date)).fetchone()


def create(conn, learner_id: int, local_date: date, steps: list[dict], practice_set_id: int | None,
           now: datetime) -> dict:
    return conn.execute(
        """insert into daily_session(learner_id, local_date, steps, practice_set_id, built_at)
           values (%s, %s, %s, %s, %s) returning *""",
        (learner_id, local_date, Jsonb(steps), practice_set_id, now)).fetchone()


def addition(conn, learner_id: int, for_date: date) -> dict | None:
    """What the learner added to that day's session from chat ("Thêm vào phiên ngày mai"): the latest one."""
    return conn.execute(
        "select * from session_addition where learner_id = %s and for_date = %s order by id desc limit 1",
        (learner_id, for_date)).fetchone()


def step_logged(conn, learner_pid: str, kind: str, since: datetime) -> bool:
    """Whether that step of the session was already logged as completed since the day began."""
    return conn.execute(
        """select 1 from activity_event where learner_pid = %s and kind = 'session_step_completed'
           and ref_id = %s and occurred_at >= %s limit 1""", (learner_pid, kind, since)).fetchone() is not None


def latest(conn, learner_id: int, limit: int) -> list[dict]:
    """The learner's newest sessions, today's first if there is one."""
    return conn.execute("select * from daily_session where learner_id = %s order by local_date desc limit %s",
                        (learner_id, limit)).fetchall()
