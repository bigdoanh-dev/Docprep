"""A unit, item by item, and the tutor on a quiz item."""
from fastapi import APIRouter, Request

from app.api.access import IDEMPOTENCY, MOCK_STATE, Learner, access, conflict
from app.api.chat import STREAM_DESCRIPTION
from app.api.deps import Conn, Gateway, Now
from app.api.mock_chat import mock_sse_response
from app.api.streams import sse_from
from app.api.stub import mock_example
from app.openapi import sse_responses
from app.schemas.units import Feedback, Hint, UnitAdvance, UnitAnswer, UnitView
from app.services import chat as chat_service
from app.services import hints as hints_service
from app.services import units as units_service
from app.services.idempotency import run_once
from app.sse import EventStreamResponse

router = APIRouter(tags=["units"])
LEARNER = access("learner")


@router.get("/units/{unit_id}/next", response_model=UnitView, summary="Current item of a unit", **LEARNER)
def unit_next(request: Request, unit_id: str, conn=Conn, now=Now, learner=Learner):
    return mock_example(request, UnitView) or units_service.next_item(conn, learner, unit_id, now)


@router.post("/units/{unit_id}/responses", response_model=Feedback, summary="Answer the current quiz item",
             **access("learner", responses=conflict(
                 "`not_current_item`: the item answered is not the step the learner is on.")))
def unit_answer(request: Request, unit_id: str, body: UnitAnswer, idempotency_key: str | None = IDEMPOTENCY,
                conn=Conn, now=Now, learner=Learner):
    return mock_example(request, Feedback) or run_once(
        conn, idempotency_key, learner["pseudonym_id"], f"POST /v1/units/{unit_id}/responses",
        lambda: units_service.answer(conn, learner, unit_id, body.unit_item_id, body.chosen, now, body.time_ms))


@router.post("/units/{unit_id}/advance", response_model=UnitView, summary="Move past the current item", **LEARNER)
def unit_advance(request: Request, unit_id: str, body: UnitAdvance, conn=Conn, now=Now, learner=Learner):
    return mock_example(request, UnitView) or units_service.advance(conn, learner, unit_id, body.unit_item_id, now)


@router.post("/items/{question_id}/explain", summary='Tutor "Giải thích thêm", after answering; streamed',
             response_class=EventStreamResponse,
             **access("learner", responses={**sse_responses(STREAM_DESCRIPTION), **conflict(
                 "`not_answered`: the learner has not answered this question yet.")}))
def explain_item(request: Request, question_id: str, x_mock_state: str | None = MOCK_STATE,
                 conn=Conn, now=Now, learner=Learner, gateway=Gateway):
    if request.app.state.mode == "mock":
        return mock_sse_response(request, x_mock_state)
    session_id, question, chosen = chat_service.begin_explain(conn, learner, question_id, now)
    return sse_from(request, lambda connect: chat_service.explain_events(
        connect, request.app.state.model_slots, gateway, session_id, question, chosen, now))


@router.post("/items/{question_id}/hint", response_model=Hint, summary='Tutor "Gợi ý", before answering',
             **access("learner", responses=conflict(
                 "`hint_unavailable`: the question is not waiting for the learner's answer, or is part of a running exam.")))
def get_hint(request: Request, question_id: str, conn=Conn, now=Now, learner=Learner, gateway=Gateway):
    return mock_example(request, Hint) or hints_service.hint(conn, gateway, learner, question_id, now)
