"""Thi thử: the diagnostic and mock forms, a timed attempt, results, answer review."""
from fastapi import APIRouter, Request

from app.api.access import IDEMPOTENCY, Learner, access, conflict
from app.api.deps import Conn, Now
from app.api.stub import mock_example
from app.schemas.common import Ok
from app.schemas.exams import AttemptItemView, AttemptView, ExamList, Results, SavedAnswer, StartAttempt
from app.services import exams as exams_service
from app.services.idempotency import run_once

router = APIRouter(tags=["exams"])
LEARNER = access("learner")
START = access("learner", responses=conflict(
    "`no_attempts_left`: the form allows no further attempt. "
    "`form_unavailable`: the form lists a question that has no approved version at the moment."))
AUTOSAVE = access("learner", responses=conflict(
    "`attempt_closed`: the attempt was already handed in, by the learner or at its deadline."))
AFTER_HAND_IN = access("learner", responses=conflict("`attempt_open`: the attempt has not been handed in yet."))


@router.get("/exams", response_model=ExamList, summary="Diagnostic and mock forms, with history", **LEARNER)
def list_exams(request: Request, conn=Conn, now=Now, learner=Learner):
    return mock_example(request, ExamList) or exams_service.list_forms(conn, learner, now)


@router.post("/exams/{form_id}/attempts", response_model=AttemptView,
             summary="Start an attempt, or resume the running one", **START)
def start_attempt(request: Request, form_id: str, body: StartAttempt, conn=Conn, now=Now, learner=Learner):
    return mock_example(request, AttemptView) or exams_service.start(conn, learner, form_id, body.fresh, now)


@router.get("/attempts/{attempt_id}", response_model=AttemptView, summary="Resume: answers and remaining time",
            **LEARNER)
def get_attempt(request: Request, attempt_id: int, conn=Conn, now=Now, learner=Learner):
    return mock_example(request, AttemptView) or exams_service.get_attempt(conn, learner, attempt_id, now)


@router.put("/attempts/{attempt_id}/answers/{question_id}", response_model=Ok, summary="Autosave one answer",
            **AUTOSAVE)
def save_answer(request: Request, attempt_id: int, question_id: str, body: SavedAnswer,
                idempotency_key: str | None = IDEMPOTENCY, conn=Conn, now=Now, learner=Learner):
    return mock_example(request, Ok) or run_once(
        conn, idempotency_key, learner["pseudonym_id"], f"PUT /v1/attempts/{attempt_id}/answers/{question_id}",
        lambda: exams_service.save_answer(conn, learner, attempt_id, question_id, body.chosen, body.flagged, now))


@router.post("/attempts/{attempt_id}/submit", response_model=Results,
             summary="Hand in the attempt; repeating it returns the stored results", **LEARNER)
def submit_attempt(request: Request, attempt_id: int, conn=Conn, now=Now, learner=Learner):
    return mock_example(request, Results) or exams_service.submit(conn, learner, attempt_id, now)


@router.get("/attempts/{attempt_id}/results", response_model=Results, summary="Score and what the attempt changed",
            **AFTER_HAND_IN)
def get_attempt_results(request: Request, attempt_id: int, conn=Conn, now=Now, learner=Learner):
    return mock_example(request, Results) or exams_service.results(conn, learner, attempt_id, now)


@router.get("/attempts/{attempt_id}/items/{question_id}", response_model=AttemptItemView,
            summary="Review one answered item", **AFTER_HAND_IN)
def get_attempt_item(request: Request, attempt_id: int, question_id: str, conn=Conn, now=Now, learner=Learner):
    return mock_example(request, AttemptItemView) or exams_service.review_item(
        conn, learner, attempt_id, question_id, now)
