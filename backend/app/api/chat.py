"""Hỏi đáp: sessions, the streamed answer, suggestions, sources, rating."""
from fastapi import APIRouter, Query, Request

from app.api.access import MOCK_STATE, Learner, access, conflict
from app.api.deps import Conn, Gateway, Now
from app.api.mock_chat import mock_sse_response
from app.api.streams import sse_from
from app.api.stub import mock_example
from app.openapi import sse_responses
from app.schemas.chat import (ChatMessageList, ChatSessionList, ChatSessionRef, NewChatMessage, NewChatSession,
                              PassageView, RatingRequest, SuggestionAccepted)
from app.schemas.common import Ok
from app.services import chat as chat_service
from app.services import suggestions as suggestions_service
from app.sse import EventStreamResponse

router = APIRouter(tags=["chat"])
LEARNER = access("learner")

STREAM_DESCRIPTION = (
    "Server-sent events, in this order: `status` queued with a position (only if the request waited) → "
    "`step` events for search and reading → `status` answering → `status` checking_sources → the check `step` → "
    "`answer` → `final`. A step is sent once as running and once as done, with the same id. "
    "The answer text is sent only after the post-check. `final` is always the last event."
)


@router.post("/chat/sessions", response_model=ChatSessionRef, summary="Start a chat session",
             **access("learner", responses=conflict(
                 "`not_answered`: `question_id` names a question the learner has not answered yet. "
                 "`tutor_unavailable`: that question is part of an exam the learner is sitting.")))
def create_chat_session(request: Request, body: NewChatSession, conn=Conn, now=Now, learner=Learner):
    return mock_example(request, ChatSessionRef) or chat_service.create_session(
        conn, learner, body.title, body.module_id, body.question_id, now)


@router.get("/chat/sessions", response_model=ChatSessionList, summary="List chat sessions, newest first", **LEARNER)
def list_chat_sessions(request: Request, cursor: str | None = None, limit: int = Query(20, ge=1, le=100),
                       conn=Conn, learner=Learner):
    return mock_example(request, ChatSessionList) or chat_service.list_sessions(conn, learner, cursor, limit)


@router.get("/chat/sessions/{session_id}/messages", response_model=ChatMessageList,
            summary="Messages of a session", **LEARNER)
def list_chat_messages(request: Request, session_id: int, cursor: str | None = None,
                       limit: int = Query(20, ge=1, le=100), conn=Conn, learner=Learner):
    return mock_example(request, ChatMessageList) or chat_service.list_messages(
        conn, learner, session_id, cursor, limit)


@router.post("/chat/sessions/{session_id}/messages", summary="Ask a question; the answer is streamed",
             response_class=EventStreamResponse, **access("learner", responses=sse_responses(STREAM_DESCRIPTION)))
def ask_question(request: Request, session_id: int, body: NewChatMessage, x_mock_state: str | None = MOCK_STATE,
                 conn=Conn, now=Now, learner=Learner, gateway=Gateway):
    if request.app.state.mode == "mock":
        return mock_sse_response(request, x_mock_state)
    session = chat_service.begin_turn(conn, learner, session_id, body.text, body.detail, now, body.clarifies_message_id)
    return sse_from(request, lambda connect: chat_service.answer_events(
        connect, request.app.state.model_slots, gateway, learner, session, body.text, body.detail,
        body.clarifies_message_id is not None, now))


@router.post("/chat/suggestions/{suggestion_id}/accept", response_model=SuggestionAccepted,
             summary="Run a suggestion the learner tapped",
             **access("learner", responses=conflict(
                 "`nothing_to_practise`: no approved question of the competency is left to ask. "
                 "`tomorrow_taken`: tomorrow's session already has a topic added from chat.")))
def accept_suggestion(request: Request, suggestion_id: int, conn=Conn, now=Now, learner=Learner):
    return mock_example(request, SuggestionAccepted) or suggestions_service.accept(conn, learner, suggestion_id, now)


@router.get("/passages/{passage_id}", response_model=PassageView, summary="Source excerpt behind a citation",
            **LEARNER)
def get_passage(request: Request, passage_id: str, conn=Conn):
    return mock_example(request, PassageView) or chat_service.passage(conn, passage_id)


@router.post("/messages/{message_id}/rating", response_model=Ok, summary="Mark an answer helpful or not", **LEARNER)
def rate_message(request: Request, message_id: int, body: RatingRequest, conn=Conn, learner=Learner):
    return mock_example(request, Ok) or chat_service.rate(conn, learner, message_id, body.helpful)
