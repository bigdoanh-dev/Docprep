"""Tokens (stored as digests) and the failed sign-in log."""
from datetime import datetime


def insert_token(conn, token_hash: str, subject_type: str, subject_id: int, kind: str, expires_at: datetime,
                 family_id: str, now: datetime) -> None:
    conn.execute(
        """insert into auth_token(token_hash, subject_type, subject_id, kind, expires_at, family_id, created_at)
           values (%s, %s, %s, %s, %s, %s, %s)""",
        (token_hash, subject_type, subject_id, kind, expires_at, family_id, now))


def find_token(conn, token_hash: str, lock: bool = False) -> dict | None:
    """lock=True holds the row until the transaction ends, so a second request presenting the same
    token waits and then sees what the first one did."""
    return conn.execute("select * from auth_token where token_hash = %s" + (" for update" if lock else ""),
                        (token_hash,)).fetchone()


def family_is_live(conn, family_id: str, now: datetime) -> bool:
    """Whether the device still has a usable token: the family was rotated, not signed out."""
    return conn.execute(
        "select 1 from auth_token where family_id = %s and revoked_at is null and expires_at > %s limit 1",
        (family_id, now)).fetchone() is not None


def revoke_family(conn, family_id: str, now: datetime) -> None:
    conn.execute("update auth_token set revoked_at = %s where family_id = %s and revoked_at is null", (now, family_id))


def record_failure(conn, ip: str, kind: str, now: datetime) -> None:
    conn.execute("insert into auth_failure(ip, kind, at) values (%s, %s, %s)", (ip, kind, now))


def count_failures(conn, ip: str, kind: str, since: datetime) -> int:
    return conn.execute("select count(*) c from auth_failure where ip = %s and kind = %s and at > %s",
                        (ip, kind, since)).fetchone()["c"]


def find_activation_code(conn, code_hash: str) -> dict | None:
    """Locked until the transaction ends: two first uses of one code must not each create a learner."""
    return conn.execute("select * from activation_code where code_hash = %s for update", (code_hash,)).fetchone()


def bind_activation_code(conn, code_id: int, learner_id: int, now: datetime) -> None:
    """The code now belongs to this learner. The name it held has moved to learner_identity."""
    conn.execute(
        """update activation_code set learner_id = %s, activated_at = coalesce(activated_at, %s), display_name = null
           where id = %s""", (learner_id, now, code_id))


def delete_subject_tokens(conn, subject_type: str, subject_id: int) -> None:
    conn.execute("delete from auth_token where subject_type = %s and subject_id = %s", (subject_type, subject_id))
