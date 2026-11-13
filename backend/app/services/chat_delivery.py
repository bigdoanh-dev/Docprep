"""Durable replay of Alpha SSE sends, without holding a DB connection during generation."""
import hashlib
import json
from typing import Callable, Iterator

from psycopg.types.json import Jsonb

from app.errors import ApiError
from app.repo import idempotency as repo


def fingerprint(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def begin(conn, key: str | None, subject: str, route: str, body: dict,
          start: Callable[[], dict]) -> tuple[dict | None, list | None]:
    if key is None:
        return start(), None
    repo.claim(conn, key, subject, route)
    saved = repo.find(conn, key, subject, route)
    if saved is not None:
        response = saved["response"]
        if response["fingerprint"] != fingerprint(body):
            raise ApiError(409, "idempotency_conflict", "Mã gửi lại không khớp câu hỏi ban đầu.")
        if response["events"] is None:
            raise ApiError(409, "chat_turn_pending", "Câu hỏi đang được xử lý. Vui lòng thử lại sau ít phút.")
        return None, response["events"]
    session = start()
    repo.store(conn, key, subject, route, 200, {"fingerprint": fingerprint(body), "events": None})
    return session, None


def remember(connect, key: str | None, subject: str, route: str, body: dict,
             events: Iterator[tuple[str, dict]]) -> Iterator[tuple[str, dict]]:
    saved = []
    for name, data in events:
        saved.append((name, data))
        if key is not None and name == "final":
            # Commit the replay before delivery of the last event. A lost response is still retryable.
            with connect() as conn:
                conn.execute(
                    """update idempotency_key set response = %s
                       where key = %s and subject = %s and route = %s""",
                    (Jsonb({"fingerprint": fingerprint(body), "events": saved}), key, subject, route))
        yield name, data
