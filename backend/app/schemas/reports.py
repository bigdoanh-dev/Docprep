"""Báo lỗi: a learner reports a wrong question, answer, card or content item."""
from datetime import datetime
from typing import Literal

from app.schemas import _samples as s
from app.schemas.base import RequestSchema, Schema, with_example

ReportTarget = Literal["question", "answer", "card", "content"]
ReportReason = Literal["wrong_content", "wrong_citation", "broken_item", "inappropriate", "other"]

_REPORT = {
    "target_type": "question", "target_id": s.Q1_ID, "reason": "broken_item",
    "note": "Phương án b và d hiển thị trùng nhau trên máy của tôi.",
    "context": {"screen": "unit", "unit_id": "u-dt-01"},
}


class ReportRequest(RequestSchema):
    target_type: ReportTarget
    target_id: str
    reason: ReportReason
    note: str | None = None
    context: dict | None = None

    model_config = with_example(_REPORT)


class ReportAccepted(Schema):
    id: int

    model_config = with_example({"id": 9})


class ReportView(Schema):
    id: int
    target_type: ReportTarget
    target_id: str
    reason: ReportReason
    note: str | None = None
    context: dict | None = None
    status: Literal["open", "resolved"]
    created_at: datetime


class ReportList(Schema):
    items: list[ReportView]
    next_cursor: str | None = None

    model_config = with_example({
        "items": [{"id": 9, **_REPORT, "status": "open", "created_at": "2026-10-09T12:31:00Z"}],
        "next_cursor": None,
    })
