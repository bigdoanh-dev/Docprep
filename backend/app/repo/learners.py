"""Learners. Name and contact live in learner_identity, apart from the learner row."""


def get(conn, learner_id: int) -> dict | None:
    return conn.execute("select * from learner where id = %s", (learner_id,)).fetchone()


def find_by_pseudonym(conn, pseudonym_id: str) -> dict | None:
    return conn.execute("select * from learner where pseudonym_id = %s", (pseudonym_id,)).fetchone()


def lock(conn, learner_id: int) -> None:
    """Hold the learner's row until the transaction ends: for a use case that must not run twice at
    once for one learner and has no row of its own to lock yet."""
    conn.execute("select 1 from learner where id = %s for update", (learner_id,))


def next_pseudonym(conn) -> str:
    return f"HV-{conn.execute('select nextval(%s) as n', ('learner_pseudonym_seq',)).fetchone()['n']:06d}"


def create(conn, pseudonym_id: str, organisation_id: int | None, audience: str, exam_date, target_retention: float,
           display_name: str) -> int:
    learner_id = conn.execute(
        """insert into learner(pseudonym_id, organisation_id, audience, exam_date, target_retention)
           values (%s, %s, %s, %s, %s) returning id""",
        (pseudonym_id, organisation_id, audience, exam_date, target_retention)).fetchone()["id"]
    conn.execute("insert into learner_identity(learner_id, display_name) values (%s, %s)", (learner_id, display_name))
    return learner_id


def profile(conn, learner_id: int) -> dict:
    """The learner with their name and their organisation's name."""
    return conn.execute(
        """select l.*, i.display_name, o.name as organisation
           from learner l
           left join learner_identity i on i.learner_id = l.id
           left join organisation o on o.id = l.organisation_id
           where l.id = %s""", (learner_id,)).fetchone()


# The columns a learner may change on their own row.
SETTINGS = ("focus_module_ids", "exam_date", "target_retention", "new_cards_per_day", "max_reviews_per_day",
            "diagnostic_prompt_dismissed")


def update_settings(conn, learner_id: int, changes: dict) -> None:
    columns = [c for c in SETTINGS if c in changes]
    if columns:
        assignments = ", ".join(f"{c} = %s" for c in columns)
        conn.execute(f"update learner set {assignments} where id = %s", (*[changes[c] for c in columns], learner_id))


def set_display_name(conn, learner_id: int, display_name: str) -> None:
    conn.execute(
        """insert into learner_identity(learner_id, display_name) values (%s, %s)
           on conflict (learner_id) do update set display_name = excluded.display_name""", (learner_id, display_name))


def unknown_modules(conn, module_ids: list[str]) -> list[str]:
    known = {r["id"] for r in conn.execute("select id from module where id = any(%s)", (module_ids,))}
    return [m for m in module_ids if m not in known]


def export_rows(conn, learner_id: int, pseudonym_id: str) -> dict:
    """The learner's own records, for the data export."""
    return {
        "responses": conn.execute(
            """select question_id, question_version, context, chosen, correct, created_at
               from item_response where learner_id = %s order by id""", (learner_id,)).fetchall(),
        "attempts": conn.execute(
            """select id as attempt_id, form_id, started_at, submitted_at, score
               from exam_attempt where learner_id = %s order by id""", (learner_id,)).fetchall(),
        "cards": conn.execute(
            "select id, front, back, due_at, suspended from card where learner_id = %s order by id",
            (learner_id,)).fetchall(),
        "chat_sessions": conn.execute(
            """select s.id, s.title, (select count(*) from chat_message m where m.session_id = s.id) as messages
               from chat_session s where s.learner_pid = %s order by s.id""", (pseudonym_id,)).fetchall(),
    }


def record_deletion_request(conn, pseudonym_id: str, now) -> int:
    return conn.execute("insert into deletion_request(learner_pid, requested_at) values (%s, %s) returning id",
                        (pseudonym_id, now)).fetchone()["id"]


def complete_deletion_request(conn, request_id: int, now) -> None:
    conn.execute("update deletion_request set completed_at = %s where id = %s", (now, request_id))


def erase(conn, learner_id: int, pseudonym_id: str) -> None:
    """Remove the learner and everything of theirs. Rows keyed by learner_id go with the learner row
    (foreign keys cascade); rows keyed by pseudonym are deleted here. The activity log is append-only
    and stays, as pseudonymous records."""
    conn.execute("delete from chat_session where learner_pid = %s", (pseudonym_id,))   # messages, suggestions cascade
    conn.execute("delete from error_report where learner_pid = %s", (pseudonym_id,))
    conn.execute("delete from idempotency_key where subject = %s", (pseudonym_id,))
    conn.execute("delete from learner where id = %s", (learner_id,))


def close_keeping_records(conn, learner_id: int) -> None:
    """Remove the identity and close the account; the learning records stay under the pseudonym."""
    conn.execute("delete from learner_identity where learner_id = %s", (learner_id,))
    conn.execute("update learner set active = false where id = %s", (learner_id,))
