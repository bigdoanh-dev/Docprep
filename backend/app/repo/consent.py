"""Consent records: service (required) and research (optional), each withdrawable."""


def has_current_service_consent(conn, learner_id: int, version: str) -> bool:
    return conn.execute(
        """select 1 from consent_record
           where learner_id = %s and kind = 'service' and version = %s and withdrawn_at is null limit 1""",
        (learner_id, version)).fetchone() is not None


def active(conn, learner_id: int, kind: str) -> dict | None:
    """The latest record of that kind that has not been withdrawn."""
    return conn.execute(
        """select * from consent_record where learner_id = %s and kind = %s and withdrawn_at is null
           order by id desc limit 1""", (learner_id, kind)).fetchone()


def give(conn, learner_id: int, kind: str, version: str, now) -> None:
    conn.execute("insert into consent_record(learner_id, kind, version, given_at) values (%s, %s, %s, %s)",
                 (learner_id, kind, version, now))


def withdraw(conn, learner_id: int, kind: str, now) -> None:
    conn.execute(
        "update consent_record set withdrawn_at = %s where learner_id = %s and kind = %s and withdrawn_at is null",
        (now, learner_id, kind))
