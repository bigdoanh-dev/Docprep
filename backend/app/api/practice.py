"""Practice sets opened from a chat suggestion or from "Làm câu tương tự"."""
from fastapi import APIRouter, Request

from app.api.access import IDEMPOTENCY, Learner, access, conflict
from app.api.deps import Conn, Now
from app.api.stub import mock_example
from app.schemas.practice import AdaptationSummary, PracticeAnswer, PracticeFeedback, PracticeSetView
from app.services import practice as practice_service
from app.services.idempotency import run_once

router = APIRouter(tags=["practice"])
LEARNER = access("learner")
# Shared with the daily session's view of its set (api/session.py).
ANSWER = access("learner", responses=conflict("`set_completed`: the set was already finished."))


@router.get("/practice-sets/{set_id}", response_model=PracticeSetView, summary="A practice set and its progress",
            **LEARNER)
def get_practice_set(request: Request, set_id: int, conn=Conn, learner=Learner):
    return mock_example(request, PracticeSetView) or practice_service.view(conn, learner, set_id)


@router.post("/practice-sets/{set_id}/responses", response_model=PracticeFeedback, summary="Answer one item",
             **ANSWER)
def answer_practice_set(request: Request, set_id: int, body: PracticeAnswer,
                        idempotency_key: str | None = IDEMPOTENCY, conn=Conn, now=Now, learner=Learner):
    return mock_example(request, PracticeFeedback) or run_once(
        conn, idempotency_key, learner["pseudonym_id"], f"POST /v1/practice-sets/{set_id}/responses",
        lambda: practice_service.answer(conn, learner, set_id, body.question_id, body.chosen, now, body.time_ms))


@router.post("/practice-sets/{set_id}/complete", response_model=AdaptationSummary,
             summary='Finish the set; returns what it changed ("Gia sư đang điều chỉnh")', **LEARNER)
def complete_practice_set(request: Request, set_id: int, conn=Conn, now=Now, learner=Learner):
    return mock_example(request, AdaptationSummary) or practice_service.complete(conn, learner, set_id, now)
