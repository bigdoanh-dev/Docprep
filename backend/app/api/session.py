"""Phiên hôm nay. Its step 2 is a practice set; these routes are the session's view of that set."""
from fastapi import APIRouter, Request

from app.api.access import IDEMPOTENCY, Learner, access
from app.api.deps import Conn, Now
from app.api.practice import ANSWER
from app.api.stub import mock_example
from app.schemas.practice import AdaptationSummary, PracticeAnswer, PracticeFeedback, PracticeSetView
from app.schemas.session import SessionToday
from app.services import practice as practice_service
from app.services import session as session_service
from app.services.idempotency import run_once

router = APIRouter(tags=["session"])
LEARNER = access("learner")


@router.get("/session/today", response_model=SessionToday, summary="Today's session: steps, minutes, reasons",
            **LEARNER)
def get_session_today(request: Request, conn=Conn, now=Now, learner=Learner):
    return mock_example(request, SessionToday) or session_service.today(conn, learner, now)


@router.get("/session/today/practice", response_model=PracticeSetView, summary="Step 2: the weak-spot set",
            **LEARNER)
def get_session_practice(request: Request, conn=Conn, now=Now, learner=Learner):
    return mock_example(request, PracticeSetView) or session_service.practice_view(conn, learner, now)


@router.post("/session/today/practice/responses", response_model=PracticeFeedback, summary="Answer one item",
             **ANSWER)
def answer_session_practice(request: Request, body: PracticeAnswer, idempotency_key: str | None = IDEMPOTENCY,
                            conn=Conn, now=Now, learner=Learner):
    if example := mock_example(request, PracticeFeedback):
        return example
    # The key is scoped to the set the answer is for, so a retry is recognised across midnight and
    # on either address of the set.
    set_id = session_service.practice_target(conn, learner, now, body.question_id)
    return run_once(
        conn, idempotency_key, learner["pseudonym_id"], f"POST /v1/practice-sets/{set_id}/responses",
        lambda: practice_service.answer(conn, learner, set_id, body.question_id, body.chosen, now, body.time_ms))


@router.post("/session/today/practice/complete", response_model=AdaptationSummary,
             summary='Finish step 2; returns what it changed ("Gia sư đang điều chỉnh")', **LEARNER)
def complete_session_practice(request: Request, conn=Conn, now=Now, learner=Learner):
    return mock_example(request, AdaptationSummary) or practice_service.complete(
        conn, learner, session_service.practice_target(conn, learner, now), now)
