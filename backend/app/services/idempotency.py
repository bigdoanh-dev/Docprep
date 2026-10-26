"""Safe retries: a write repeated with the same Idempotency-Key is applied once."""
from typing import Callable

from fastapi.encoders import jsonable_encoder

from app.repo import idempotency as repo


def run_once(conn, key: str | None, subject: str, route: str, fn: Callable[[], dict]) -> dict:
    """Without a key, runs `fn`. With one, returns the response stored for (key, subject, route) or
    runs `fn` and stores its result, in the caller's transaction: a write that fails stores nothing.
    A retry that arrives while the first request is still running waits for it and gets its answer.
    The result is made JSON-safe either way, so the first and the repeated answer are the same value."""
    if key is None:
        return jsonable_encoder(fn())
    repo.claim(conn, key, subject, route)
    stored = repo.find(conn, key, subject, route)
    if stored is not None:
        return stored["response"]
    response = jsonable_encoder(fn())
    repo.store(conn, key, subject, route, 200, response)
    return response
