"""Báo lỗi."""
from fastapi import APIRouter, Request

from app.api.access import access
from app.api.stub import not_implemented
from app.schemas.reports import ReportAccepted, ReportRequest

router = APIRouter(tags=["reports"])


@router.post("/reports", response_model=ReportAccepted, summary="Report a wrong question, answer, card or content",
             **access("learner"))
def create_report(request: Request, body: ReportRequest):
    return not_implemented(request, ReportAccepted)
