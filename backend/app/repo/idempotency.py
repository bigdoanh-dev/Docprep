"""Stored responses of writes the app may retry."""
from psycopg.types.json import Jsonb


def claim(conn, key: str, subject: str, route: str) -> None:
    """Wait until no other transaction is working on this key, and hold it until this one ends."""
    conn.execute("select pg_advisory_xact_lock(hashtextextended(%s, 0))", (f"{subject}\x1f{route}\x1f{key}",))


def find(conn, key: str, subject: str, route: str) -> dict | None:
    return conn.execute("select status_code, response from idempotency_key where key = %s and subject = %s and route = %s",
                        (key, subject, route)).fetchone()


def store(conn, key: str, subject: str, route: str, status_code: int, response) -> None:
    conn.execute(
        """insert into idempotency_key(key, subject, route, status_code, response) values (%s, %s, %s, %s, %s)
           on conflict (key, subject, route) do nothing""",
        (key, subject, route, status_code, Jsonb(response)))
