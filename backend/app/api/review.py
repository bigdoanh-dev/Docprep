"""Bàn thẩm định: questions and learning-content items share the queue, the item view and the decision."""
from typing import Literal

from fastapi import APIRouter, Query, Request

from app.api.access import access
from app.api.stub import not_implemented
from app.schemas.reports import ReportList
from app.schemas.review import ReviewDecisionRequest, ReviewDecisionResult, ReviewItemView, ReviewQueue

router = APIRouter(tags=["review"])
STAFF = access("reviewer", "admin")


@router.get("/review/queue", response_model=ReviewQueue, summary="Items awaiting review", **STAFF)
def list_review_queue(request: Request, round: int | None = Query(None, ge=1, le=2), group: int | None = None,
                      flag: bool | None = None, type: Literal["question", "content"] | None = None,
                      cursor: str | None = None, limit: int = Query(20, ge=1, le=100)):
    return not_implemented(request, ReviewQueue)


@router.get("/review/items/{item_id}", response_model=ReviewItemView,
            summary="One item with its sources, decisions and status history", **STAFF)
def get_review_item(request: Request, item_id: str, version: int | None = None):
    return not_implemented(request, ReviewItemView)


@router.post("/review/items/{item_id}/decisions", response_model=ReviewDecisionResult,
             summary="Record a reviewer's decision: Đạt, Cần sửa or Loại", **STAFF)
def decide_review(request: Request, item_id: str, body: ReviewDecisionRequest):
    return not_implemented(request, ReviewDecisionResult)


@router.get("/review/reports", response_model=ReportList, summary="Learner error reports with their context",
            **STAFF)
def list_review_reports(request: Request, cursor: str | None = None, limit: int = Query(20, ge=1, le=100)):
    return not_implemented(request, ReportList)
