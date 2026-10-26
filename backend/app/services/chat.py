"""Hỏi đáp and the tutor's "Giải thích thêm": sessions, history, and the answer as a stream of events.

The pipeline (app/chat/) decides the answer; this module logs the turn and turns the pipeline's
progress into the contract's events. Only what really ran is sent: a `step` for each stage as it
runs, `status` while the model answers and its answer is checked, then `answer` after the
post-check, then `final`. The model sees the question and the passages, never who is asking.
"""
import base64
import json
import logging
from datetime import datetime
from typing import Callable, Iterator

from app import events
from app.api.streams import Connect
from app.chat import trace
from app.chat.slots import QueueTimeout
from app.chat.pipeline import (UNANSWERED_COPY, ChatOutcome, generate, prepare_answer, prepare_explain,
                               prepare_quiz_chat)
from app.config import settings
from app.errors import ApiError
from app.repo import chat as repo
from app.repo import content
from app.repo import exams as exams_repo
from app.repo import responses as responses_repo
from app.schemas.chat import AnswerEvent, FinalEvent, StatusEvent, StepEvent
from app.services import suggestions
from app.services.responses import require_question

log = logging.getLogger(__name__)
Event = tuple[str, dict]
TITLE_LENGTH = 80
DETAIL_TEXT = "Giải thích thêm"
FAILED_NOTICE = "Có lỗi xảy ra. Vui lòng thử lại."
BUSY_NOTICE = "Hệ thống đang bận. Vui lòng thử lại sau ít phút."


# ---- cursors ------------------------------------------------------------------------------------

def _encode(value) -> str:
    return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")


def _invalid_cursor() -> ApiError:
    return ApiError(422, "invalid_cursor", "Con trỏ phân trang không hợp lệ.")


def _decode(cursor: str):
    """A cursor is opaque to the client; one that was not issued here is refused, never guessed at."""
    try:
        return json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    except ValueError:
        raise _invalid_cursor()


# ---- sessions and history -----------------------------------------------------------------------

def create_session(conn, learner: dict, title: str | None, module_id: str | None, question_id: str | None,
                   now: datetime) -> dict:
    if module_id is not None and content.module(conn, module_id) is None:
        raise ApiError(404, "module_not_found", "Không tìm thấy học phần.")
    if question_id is not None:
        # Opened from a quiz item: only once the learner has answered it, and never during an exam it is part of.
        require_question(conn, question_id)
        if responses_repo.last_for_question(conn, learner["id"], question_id) is None:
            raise ApiError(409, "not_answered", "Hãy trả lời câu hỏi trước khi hỏi gia sư.")
        if exams_repo.in_running_attempt(conn, learner["id"], question_id, now):
            raise ApiError(409, "tutor_unavailable", "Không hỏi gia sư trong khi làm bài thi.")
    title = title.strip()[:TITLE_LENGTH] if title and title.strip() else None
    return {"id": repo.create_session(conn, learner["pseudonym_id"], now, title=title, module_id=module_id,
                                      question_id=question_id)}


def list_sessions(conn, learner: dict, cursor: str | None, limit: int) -> dict:
    before = None
    if cursor is not None:
        value = _decode(cursor)
        try:
            before = (datetime.fromisoformat(value[0]), int(value[1]))
        except (TypeError, ValueError, IndexError, KeyError):
            raise _invalid_cursor()
    rows = repo.sessions(conn, learner["pseudonym_id"], before, limit + 1)
    page = rows[:limit]
    more = len(rows) > limit
    return {"items": page,
            "next_cursor": _encode([page[-1]["updated_at"].isoformat(), page[-1]["id"]]) if more else None}


def _own_session(conn, learner: dict, session_id: int) -> dict:
    session = repo.own_session(conn, learner["pseudonym_id"], session_id)
    if session is None:
        raise ApiError(404, "session_not_found", "Không tìm thấy cuộc trò chuyện.")
    return session


def list_messages(conn, learner: dict, session_id: int, cursor: str | None, limit: int) -> dict:
    _own_session(conn, learner, session_id)
    after_id = 0
    if cursor is not None:
        value = _decode(cursor)
        if not isinstance(value, int) or isinstance(value, bool):
            raise _invalid_cursor()
        after_id = value
    rows = repo.messages(conn, session_id, after_id, limit + 1)
    page = rows[:limit]
    suggested = suggestions.of_messages(conn, [m["id"] for m in page])
    items = [{**m, "citations": m["citations"] or [], "clarify_options": m["clarify_options"] or [],
              "searched": m["searched"] or [], "suggestions": suggested.get(m["id"], []), "trace": m["trace"] or [],
              "trace_summary": _summary(m["citations"] or [], m["claims_checked"], m["claims_removed"])} for m in page]
    return {"items": items, "next_cursor": _encode(page[-1]["id"]) if len(rows) > limit else None}


def passage(conn, passage_id: str) -> dict:
    view = content.passage_view(conn, passage_id)
    if view is None:
        raise ApiError(404, "passage_not_found", "Không tìm thấy trích đoạn.")
    return view


def rate(conn, learner: dict, message_id: int, helpful: bool) -> dict:
    """ "Hữu ích": the learner's verdict on an answer they were given. The last one stands."""
    if not repo.rate_answer(conn, learner["pseudonym_id"], message_id, helpful):
        raise ApiError(404, "message_not_found", "Không tìm thấy tin nhắn.")
    return {"ok": True}


# ---- one turn -----------------------------------------------------------------------------------

def begin_turn(conn, learner: dict, session_id: int, text: str, detail: bool, now: datetime,
               clarifies_message_id: int | None = None) -> dict:
    """Check the session is the learner's and log their message. Returns the session.
    Runs in the request's transaction, which is committed before the answer stream starts.
    A message that says it clarifies another must name an answer of this session that asked back."""
    session = _own_session(conn, learner, session_id)
    if clarifies_message_id is not None:
        asked_back = repo.answer_in_session(conn, session_id, clarifies_message_id)
        if asked_back is None:
            raise ApiError(404, "message_not_found", "Không tìm thấy tin nhắn.")
        if asked_back["state"] != "needs_clarification":
            raise ApiError(422, "not_a_clarification", "Tin nhắn này không phải là câu hỏi lại.")
    if session["title"] is None and not detail:
        repo.set_title(conn, session_id, text[:TITLE_LENGTH])
    repo.add_message(conn, session_id, "user", DETAIL_TEXT if detail else text, now,
                     clarifies_message_id=clarifies_message_id)
    events.record(conn, learner["pseudonym_id"], "chat_turn", now, ref_type="chat_session", ref_id=session_id)
    return session


def begin_explain(conn, learner: dict, question_id: str, now: datetime) -> tuple[int, dict, str | None]:
    """The tutor on a quiz item, only after the learner answered it. Returns the tutor session's id,
    the question and what the learner chose. The turn is logged outside the chat list."""
    question = require_question(conn, question_id)
    last = responses_repo.last_for_question(conn, learner["id"], question_id)
    if last is None:
        raise ApiError(409, "not_answered", "Hãy trả lời câu hỏi trước khi xem giải thích thêm.")
    title = f"Gia sư · {question_id}"
    session = repo.tutor_session(conn, learner["pseudonym_id"], title)
    session_id = session["id"] if session else repo.create_session(
        conn, learner["pseudonym_id"], now, title=title, kind="tutor", question_id=question_id)
    repo.add_message(conn, session_id, "user", DETAIL_TEXT, now)
    events.record(conn, learner["pseudonym_id"], "chat_turn", now, ref_type="tutor_session", ref_id=session_id)
    return session_id, question, last["chosen"]


def _summary(citations: list[dict], claims_checked: int | None, claims_removed: int | None) -> dict | None:
    """ "Đã tra N nguồn · kiểm tra M nhận định": only for an answer the model produced claims for."""
    if claims_checked is None:
        return None
    return {"sources": len({c["passage_id"] for c in citations}), "claims_checked": claims_checked,
            "claims_removed": claims_removed or 0}


def _turn(connect: Connect, slots, gateway, session_id: int, prepare: Callable[[object], Iterator[tuple[str, object]]],
          now: datetime, *, after_answer: Callable[[object, int, ChatOutcome], list[dict]] | None = None) -> Iterator[Event]:
    """One turn as contract events, in three parts: what code decides, on a connection it gives back
    at once; the model call and the post-check, in one of the model's slots and with no connection
    held; storing the answer, on a
    second connection. Each stage that runs is sent as a `step`. Whatever happens, the stream ends
    with `answer` then `final`, and the assistant's message is stored before either is sent."""
    outcome, steps = None, []
    try:
        prepared = None
        with connect() as conn:
            for kind, payload in prepare(conn):
                if kind == "step":
                    yield "step", StepEvent(**payload).model_dump(mode="json")
                else:
                    prepared = payload
        steps, outcome = prepared.steps, prepared.outcome
        if outcome is None:
            # The model is asked by a few turns at a time. A turn that has to wait says its place.
            try:
                cfg = settings()["gateway"]
                for position in slots.acquire(cfg["queue_timeout_s"], max_waiting=cfg["max_waiting"]):
                    yield "status", StatusEvent(status="queued", position=position).model_dump(mode="json")
            except QueueTimeout:        # waited too long, or the line was full
                outcome = ChatOutcome("insufficient_evidence", UNANSWERED_COPY, [], [p.id for p in prepared.passages],
                                      notice=BUSY_NOTICE)
            else:
                try:
                    for kind, payload in generate(gateway, prepared):
                        if kind == "status":
                            yield "status", StatusEvent(status=payload).model_dump(mode="json")
                        elif kind == "step":
                            yield "step", StepEvent(**payload).model_dump(mode="json")
                        else:
                            outcome = payload
                finally:
                    slots.release()
    except Exception:
        # The pipeline turns a failed model call into an outcome itself; this is for what nobody foresaw.
        log.exception("answer pipeline failed")
    if outcome is None:
        outcome = ChatOutcome("insufficient_evidence", UNANSWERED_COPY, [], [], notice=FAILED_NOTICE)

    model = outcome.model
    with connect() as conn:
        message_id = repo.add_message(
            conn, session_id, "assistant", outcome.text, now, state=outcome.state, answer_format="text",
            citations=outcome.citations, retrieved_passage_ids=outcome.retrieved_ids, notice=outcome.notice,
            trace=trace.stored(steps) or None, claims_checked=outcome.claims_checked, claims_removed=outcome.claims_removed,
            clarify_options=outcome.clarify_options or None, searched=outcome.searched or None,
            nearest_chapter=outcome.nearest_chapter,
            model_version=model.model if model else None, prompt_version=model.prompt_version if model else None,
            corpus_version=settings()["corpus_version"], latency_ms=model.latency_ms if model else None,
            tokens_in=model.tokens_in if model else None, tokens_out=model.tokens_out if model else None,
            cost=model.cost if model else None)
    # The answer is kept (the block above committed) before anything else can fail. Suggestions are an
    # extra: if making them fails, the answer still goes out, without them.
    offers: list[dict] = []
    if after_answer:
        try:
            with connect() as conn:
                offers = after_answer(conn, message_id, outcome)
        except Exception:
            log.exception("suggestions after an answer failed")
            offers = []
    # Announced only now: a client acting on `final` finds the message.
    yield "answer", AnswerEvent(text=outcome.text, citations=outcome.citations,
                                notice=outcome.notice).model_dump(mode="json")
    yield "final", FinalEvent(
        state=outcome.state, message_id=message_id,
        trace_summary=_summary(outcome.citations, outcome.claims_checked, outcome.claims_removed),
        clarify_options=outcome.clarify_options, searched=outcome.searched, nearest_chapter=outcome.nearest_chapter,
        suggestions=offers).model_dump(mode="json")


def answer_events(connect: Connect, slots, gateway, learner: dict, session: dict, text: str, detail: bool,
                  clarifying: bool, now: datetime) -> Iterator[Event]:
    """The answer to a chat question, and the suggestions the learner's own record calls for.
    In a chat opened from a quiz item the first answer is about that item; later ones are ordinary."""
    def prepare(conn):
        question_id = session.get("question_id")
        if question_id and not repo.has_answer(conn, session["id"]):
            question = content.approved_question(conn, question_id)
            if question is not None:
                last = responses_repo.last_for_question(conn, learner["id"], question_id)
                return prepare_quiz_chat(conn, question, last["chosen"] if last else None, text)
        return prepare_answer(conn, text, session["module_id"], detail, clarifying)

    return _turn(connect, slots, gateway, session["id"], prepare, now,
                 after_answer=lambda conn, message_id, outcome: suggestions.after_answer(conn, learner, message_id, outcome, now))


def explain_events(connect: Connect, slots, gateway, session_id: int, question: dict, chosen: str | None,
                   now: datetime) -> Iterator[Event]:
    """The tutor's "Giải thích thêm" on a quiz item."""
    return _turn(connect, slots, gateway, session_id, lambda conn: prepare_explain(conn, question, chosen), now)
