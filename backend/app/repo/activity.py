"""The activity log (append-only) and what Home reads back from a learner's recent work."""
from datetime import datetime


def insert(conn, learner_pid: str, kind: str, occurred_at: datetime, duration_ms: int | None, ref_type: str | None,
           ref_id: str | None) -> None:
    """The row takes `is_synthetic` from the learner here: the table refuses updates, so it cannot be set later."""
    conn.execute(
        """insert into activity_event(learner_pid, kind, occurred_at, duration_ms, ref_type, ref_id, is_synthetic)
           values (%s, %s, %s, %s, %s, %s,
                   coalesce((select is_synthetic from learner where pseudonym_id = %s), false))""",
        (learner_pid, kind, occurred_at, duration_ms, ref_type, ref_id, learner_pid))


def happened_since(conn, learner_pid: str, kind: str, since: datetime) -> bool:
    return conn.execute(
        "select 1 from activity_event where learner_pid = %s and kind = %s and occurred_at > %s limit 1",
        (learner_pid, kind, since)).fetchone() is not None


def recent(conn, learner_id: int, learner_pid: str, limit: int) -> list[dict]:
    """The units the learner opened and the chats they titled by asking, newest activity first.
    A unit comes with its place in its học phần and how far the newest pass through it has got."""
    return conn.execute(
        """select kind, id, title, module_short_name, position, units_in_module, progress from (
             select 'unit' as kind, u.id::text as id, u.topic as title, m.short_name as module_short_name,
                    (select count(*) from unit o where o.module_id = u.module_id and o.ord <= u.ord) as position,
                    (select count(*) from unit o where o.module_id = u.module_id) as units_in_module,
                    (select case when s.done then 1.0
                                 else round(s.cursor::numeric / greatest(cardinality(s.queue), 1), 2) end
                     from unit_session s where s.learner_id = %(learner)s and s.unit_id = u.id
                     order by s.updated_at desc, s.id desc limit 1) as progress,
                    (select max(s.updated_at) from unit_session s
                     where s.learner_id = %(learner)s and s.unit_id = u.id) as at
             from unit u join module m on m.id = u.module_id
             where exists (select 1 from unit_session s where s.learner_id = %(learner)s and s.unit_id = u.id)
             union all
             select 'chat', c.id::text, c.title, null, null, null, null, c.updated_at from chat_session c
             where c.learner_pid = %(pid)s and c.kind = 'chat' and c.title is not null
           ) x order by at desc, id desc limit %(limit)s""",
        {"learner": learner_id, "pid": learner_pid, "limit": limit}).fetchall()


def visits(conn, learner_pid: str, limit: int) -> list[datetime]:
    """When the learner's latest visits began, newest first."""
    return [r["occurred_at"] for r in conn.execute(
        "select occurred_at from activity_event where learner_pid = %s and kind = 'visit' order by occurred_at desc, id desc limit %s",
        (learner_pid, limit))]


def counts_between(conn, learner_pid: str, kinds: list[str], after: datetime, until: datetime) -> dict[str, int]:
    """How many events of each kind happened after one time and no later than another."""
    return {r["kind"]: r["n"] for r in conn.execute(
        """select kind, count(*) as n from activity_event
           where learner_pid = %s and kind = any(%s) and occurred_at > %s and occurred_at <= %s group by kind""",
        (learner_pid, kinds, after, until))}


def happened_between(conn, learner_pid: str, kind: str, ref_id: str, after: datetime, until: datetime) -> bool:
    return conn.execute(
        """select 1 from activity_event where learner_pid = %s and kind = %s and ref_id = %s
           and occurred_at > %s and occurred_at <= %s limit 1""", (learner_pid, kind, ref_id, after, until)).fetchone() is not None
