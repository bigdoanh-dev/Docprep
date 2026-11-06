"""Phase 1 AI endpoints; original paths and response media types are preserved."""
import asyncio
import json
import re
from typing import Literal
from uuid import UUID, uuid4
from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import JSONResponse
from app.api.access import IDEMPOTENCY, Learner, access
from app.api.deps import Conn, Now
from app.errors import ApiError
from app.openapi import sse_responses
from app.privacy import clean_tree
from app.repo import turns, chat, units, practice
from app.schemas.chat import NewChatMessage
from app.schemas.units import Hint
from app.schemas.base import Schema
from app.schemas.common import ErrorBody
from app.services import chat as service
from app.services.responses import require_question
from app.sse import EventStreamResponse, format_sse
from app.chat.worker import utcnow

router = APIRouter(tags=["chat"])
PHASE_ERRORS = {409: {"model": ErrorBody, "description": "Active turn, changed payload or AI blocked by an exam."},
                429: {"model": ErrorBody, "description": "ai_queue_full; retry with the same idempotency key."},
                503: {"model": ErrorBody, "description": "AI disabled, unavailable or turn failed."},
                410: {"model": ErrorBody, "description": "event_history_expired; load the durable turn snapshot."}}
LEARNER = access("learner", responses=PHASE_ERRORS)
SSE = access("learner", responses={**PHASE_ERRORS, **sse_responses(
    "Resumable Phase 1 stream; technical failures end with final, no fabricated answer. X-Turn-ID identifies the turn.")})


class TurnView(Schema):
    turn_id: str
    kind: str
    session_id: int | None = None
    turn_status: Literal['queued', 'running', 'completed', 'failed', 'cancelled', 'interrupted']
    result: dict | None = None
    error: dict | None = None


class ActiveTurn(Schema):
    item: TurnView | None = None


def _submit(request, conn, learner, now, kind, route, key, raw):
    cfg = request.app.state.phase_config
    if cfg.provider == "disabled":
        raise ApiError(503, "ai_disabled", "Tính năng sinh câu trả lời AI chưa được bật.")
    worker = request.app.state.worker
    if worker.draining or not worker.healthy():
        raise ApiError(503, "ai_unavailable", "Dịch vụ AI đang tạm dừng nhận lượt mới.")
    request.app.state.admission.require_ready()
    if key is not None and (not key.strip() or len(key) > 128):
        raise ApiError(422, "invalid_request", "Idempotency-Key phải có từ 1 đến 128 ký tự.")
    payload = clean_tree(raw)

    def begin():
        if kind == "chat":
            session = service.begin_turn(conn, learner, raw["session_id"], payload["text"], payload["detail"],
                                         now, payload.get("clarifies_message_id"))
            return session["id"]
        q = require_question(conn, payload["question_id"])
        if kind == "explain":
            return service.begin_explain(conn, learner, q["id"], now)[0]
        if not (units.awaiting_answer(conn, learner["id"], q["id"]) or
                practice.awaiting_answer(conn, learner["id"], q["id"])):
            raise ApiError(409, "hint_unavailable", "Gợi ý chỉ có trước khi bạn trả lời câu hỏi.")
        title = f"Gia sư · {q['id']}"
        session = chat.tutor_session(conn, learner["pseudonym_id"], title)
        sid = session["id"] if session else chat.create_session(conn, learner["pseudonym_id"], now,
                                                               title=title, kind="tutor", question_id=q["id"])
        chat.add_message(conn, sid, "user", "Gợi ý", now)
        from app import events
        events.record(conn, learner["pseudonym_id"], "chat_turn", now, ref_type="tutor_session", ref_id=sid)
        return sid

    return turns.submit(conn, cfg, learner["id"], kind, route, key or str(uuid4()), raw, payload, now, begin)


def _read(request, learner_id, turn_id):
    with request.app.state.pool.connection() as conn:
        from app.api.access import _bearer_token
        from app.services.auth import authenticate
        principal = authenticate(conn, _bearer_token(request), utcnow())
        if principal.subject_type != "learner" or principal.subject_id != learner_id:
            raise ApiError(403, "forbidden", "Bạn không có quyền đọc lượt AI.")
        # Revalidate consent/account on every poll, including a connection opened before revocation.
        from app.repo.consent import has_current_service_consent
        from app.config import settings
        learner = conn.execute("select active from learner where id=%s", (learner_id,)).fetchone()
        if not learner or not learner["active"] or not has_current_service_consent(
                conn, learner_id, settings()["consent"]["version"]):
            raise ApiError(403, "consent_required", "Quyền sử dụng đã thay đổi.")
        return turns.own(conn, learner_id, turn_id)


def _cursor(request, turn_id, cursor):
    if not cursor:
        return "0-0"
    if not re.fullmatch(r"\d+-\d+", cursor):
        raise ApiError(422, "invalid_event_id", "Mã sự kiện không hợp lệ.")
    first = request.app.state.admission.r.xrange(request.app.state.admission.key(f"events:{turn_id}"), count=1)
    if not first or tuple(map(int, cursor.split("-"))) < tuple(map(int, first[0][0].split("-"))):
        raise ApiError(410, "event_history_expired", "Tiến trình cũ đã hết hạn. Hãy tải trạng thái lượt AI.")
    return cursor


async def stream(request, learner_id, turn_id, cursor="0-0"):
    state = request.app.state
    key = state.admission.key(f"events:{turn_id}")
    last_heartbeat, position = 0.0, None
    answer_sent = False
    try:
        while True:
            turn = await asyncio.to_thread(_read, request, learner_id, turn_id)
            # XREAD in async Redis: waiting subscribers occupy neither DB connections nor worker threads.
            try:
                batches = await state.redis_async.xread({key: cursor}, block=500, count=100)
            except Exception:
                batches = []  # the DB snapshot still supplies a committed terminal result
            for _, entries in batches:
                for event_id, fields in entries:
                    cursor = event_id
                    event, data = fields["event"], json.loads(fields["data"])
                    # Lifecycle revocation cannot publish stale answer events.
                    if event in ("answer", "final"):
                        turn = await asyncio.to_thread(_read, request, learner_id, turn_id)
                        if turn["status"] != "completed":
                            continue
                        if event == "final" and not answer_sent:
                            # A reconnect may start immediately after answer, or the subscriber may have
                            # mounted after it. Replacing the same answer view is idempotent.
                            yield format_sse("answer", turn["result"]["answer"])
                            answer_sent = True
                        if event == "answer":
                            answer_sent = True
                    yield format_sse(event, data, event_id)
                    if event == "final":
                        return
            turn = await asyncio.to_thread(_read, request, learner_id, turn_id)
            if turns.terminal(turn):
                if turn["status"] == "completed":
                    if not answer_sent:
                        yield format_sse("answer", turn["result"]["answer"])
                    yield format_sse("final", turn["result"]["final"])
                else:
                    yield format_sse("final", turns.final_failure(turn))
                return
            if turn["status"] == "queued":
                try:
                    rank = await state.redis_async.zrank(state.admission.key("queue"), str(turn_id))
                    current = rank + 1 if rank is not None else 1
                    if current != position:
                        yield format_sse("status", {"status": "queued", "position": current, "turn_id": str(turn_id)})
                        position = current
                except Exception:
                    pass
            now = asyncio.get_running_loop().time()
            if now - last_heartbeat >= 10:
                yield ": heartbeat\n\n"
                last_heartbeat = now
            if await request.is_disconnected():
                return
    except ApiError as exc:
        yield format_sse("final", {"turn_id": str(turn_id), "turn_status": "cancelled", "state": None,
                                   "message_id": None, "error": {"code": exc.code, "message_vi": exc.message_vi}})


def _response(request, learner_id, turn):
    return EventStreamResponse(stream(request, learner_id, turn["id"]),
        headers={"X-Turn-ID": str(turn["id"]), "Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@router.post("/chat/sessions/{session_id}/messages", response_class=EventStreamResponse, **SSE)
def ask_question(request: Request, session_id: int, body: NewChatMessage,
                 idempotency_key: str | None = IDEMPOTENCY, conn=Conn, now=Now, learner=Learner):
    turn = _submit(request, conn, learner, now, "chat", f"/chat/sessions/{session_id}/messages", idempotency_key,
                   {**body.model_dump(), "session_id": session_id})
    return _response(request, learner["id"], turn)


@router.post("/items/{question_id}/explain", response_class=EventStreamResponse, **SSE)
def explain_item(request: Request, question_id: str, idempotency_key: str | None = IDEMPOTENCY,
                 conn=Conn, now=Now, learner=Learner):
    turn = _submit(request, conn, learner, now, "explain", f"/items/{question_id}/explain", idempotency_key,
                   {"question_id": question_id})
    return _response(request, learner["id"], turn)


class DeferredHint(Response):
    """Wait after function-scoped dependencies release, before sending HTTP headers."""
    media_type = "application/json"

    def __init__(self, request, learner_id, turn_id):
        super().__init__()
        self.request, self.learner_id, self.turn_id = request, learner_id, turn_id

    async def __call__(self, scope, receive, send):
        try:
            result = await wait_hint(self.request, self.learner_id, self.turn_id)
            reply = JSONResponse(Hint(**result).model_dump(mode="json"))
        except ApiError as exc:
            from app.errors import error_response
            reply = error_response(exc.status, exc.code, exc.message_vi, exc.details)
        reply.headers["X-Turn-ID"] = str(self.turn_id)
        await reply(scope, receive, send)


@router.post("/items/{question_id}/hint", response_model=Hint, **LEARNER)
def get_hint(request: Request, question_id: str, idempotency_key: str | None = IDEMPOTENCY,
             conn=Conn, now=Now, learner=Learner):
    turn = _submit(request, conn, learner, now, "hint", f"/items/{question_id}/hint",
                   idempotency_key, {"question_id": question_id})
    return DeferredHint(request, learner["id"], turn["id"])


async def wait_hint(request, learner_id, turn_id):
    while True:
        turn = await asyncio.to_thread(_read, request, learner_id, turn_id)
        if turns.terminal(turn):
            if turn["status"] != "completed":
                error = turn["error"] or {"code": "ai_cancelled", "message_vi": "Lượt AI đã dừng."}
                raise ApiError(503, error["code"], error["message_vi"], {"turn_id": str(turn_id)})
            return turn["result"]["hint"]
        if await request.is_disconnected():
            raise ApiError(499, "client_disconnected", "Kết nối đã đóng.")
        await asyncio.sleep(0.2)


@router.get("/chat/turns/active", response_model=ActiveTurn, **LEARNER)
def active_turn(conn=Conn, learner=Learner):
    row = conn.execute("select * from ai_turn where learner_id=%s and status in ('queued','running')",
                       (learner["id"],)).fetchone()
    return {"item": turns.snapshot(row) if row else None}


@router.get("/chat/turns/{turn_id}", response_model=TurnView, **LEARNER)
def get_turn(turn_id: UUID, conn=Conn, learner=Learner):
    return turns.snapshot(turns.own(conn, learner["id"], turn_id))


@router.get("/chat/turns/{turn_id}/events", response_class=EventStreamResponse, **SSE)
def turn_events(request: Request, turn_id: UUID, last_event_id: str | None = Header(None), conn=Conn, learner=Learner):
    request.app.state.reconnect_metric.inc()
    turns.own(conn, learner["id"], turn_id)
    request.app.state.admission.require_ready()
    cursor = _cursor(request, turn_id, last_event_id)
    return EventStreamResponse(stream(request, learner["id"], turn_id, cursor),
        headers={"X-Turn-ID": str(turn_id), "Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@router.delete("/chat/turns/{turn_id}", response_model=TurnView, **LEARNER)
def cancel_turn(turn_id: UUID, conn=Conn, learner=Learner):
    turns.lock_learner(conn, learner["id"])
    turns.own(conn, learner["id"], turn_id)
    turns.failure(conn, turn_id, "cancelled", "ai_cancelled", "Bạn đã hủy lượt AI.")
    return turns.snapshot(turns.own(conn, learner["id"], turn_id))
