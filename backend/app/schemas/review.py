"""Bàn thẩm định: the queue, one item with its history, and the reviewer's decision.

Only a reviewer's decision moves an item towards `approved`; two passing rounds by different reviewers.
"""
from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.schemas import _samples as s
from app.schemas.base import RequestSchema, Schema, example, with_example
from app.schemas.chat import PassageView

ItemStatus = Literal["draft", "prescreen", "in_review_r1", "in_review_r2", "approved", "needs_revision",
                     "rejected", "retired"]
ItemType = Literal["question", "content"]
Decision = Literal["pass", "revise", "reject"]

_DEMO_COMMENT = "Dữ liệu demo – chưa thẩm định"
_QUEUED = s.PRACTICE_QUESTIONS[1]


class ReviewQueueItem(Schema):
    id: str
    type: ItemType
    version: int
    round: Literal[1, 2]
    status: ItemStatus
    group_id: int | None = Field(default=None, description="Core-issue group, when the item has a core issue.")
    title: str = Field(description="Start of the stem or of the content body.")
    flagged: bool
    ai_assisted: bool
    waiting_since: datetime


class ReviewQueue(Schema):
    items: list[ReviewQueueItem]
    next_cursor: str | None = None

    model_config = with_example({
        "items": [{"id": _QUEUED[0], "type": "question", "version": 1, "round": 1, "status": "in_review_r1",
                   "group_id": None, "title": _QUEUED[1], "flagged": False, "ai_assisted": False,
                   "waiting_since": "2026-10-08T02:00:00Z"}],
        "next_cursor": None,
    })


class ReviewOptionFull(Schema):
    key: str
    text: str
    is_correct: bool
    rationale: str


class DecisionView(Schema):
    round: Literal[1, 2]
    decision: Decision
    comment: str | None = None
    reviewer: str
    created_at: datetime


class TransitionView(Schema):
    from_status: ItemStatus | None = None
    to_status: ItemStatus
    actor: str
    at: datetime
    reason: str | None = None


class ReviewItemView(Schema):
    id: str
    type: ItemType
    version: int
    status: ItemStatus
    ai_assisted: bool
    stem: str | None = Field(default=None, description="Questions only.")
    options: list[ReviewOptionFull] = []
    explanation: str | None = None
    body: str | None = Field(default=None, description="Content items only. Markdown.")
    competency_code: str
    core_issue_id: int | None = None
    exam_competency_component_id: int | None = None
    bloom_level: Literal[1, 2, 3] | None = None
    difficulty_label: str | None = None
    passages: list[PassageView]
    decisions: list[DecisionView]
    transitions: list[TransitionView]

    model_config = with_example({
        "id": s.Q1_ID, "type": "question", "version": 1, "status": "approved", "ai_assisted": False,
        "stem": s.Q1_STEM,
        "options": [{**o, "is_correct": o["key"] == s.Q1_CORRECT, "rationale": s.Q1_RATIONALES[o["key"]]}
                    for o in s.Q1_OPTIONS],
        "explanation": s.Q1_EXPLANATION, "body": None, "competency_code": "FND", "core_issue_id": None,
        "exam_competency_component_id": 2, "bloom_level": 2, "difficulty_label": "trung_binh",
        "passages": [{
            "id": "dt-p01", "document": s.DT_CITATION["document"], "chapter": s.DT_CITATION["chapter"],
            "section": s.DT_CITATION["section"], "page": s.DT_CITATION["page"], "article": None,
            "excerpt": "Tỷ lệ hiện mắc (prevalence) cho biết có bao nhiêu người đang mắc bệnh trong quần thể tại "
                       "một thời điểm, bao gồm cả ca cũ lẫn ca mới.",
            "demo_label": example(PassageView).demo_label, "validity_note": None,
        }],
        "decisions": [
            {"round": 1, "decision": "pass", "comment": _DEMO_COMMENT, "reviewer": "Người thẩm định 1",
             "created_at": "2026-10-09T01:00:00Z"},
            {"round": 2, "decision": "pass", "comment": _DEMO_COMMENT, "reviewer": "Người thẩm định 2",
             "created_at": "2026-10-09T01:00:05Z"},
        ],
        "transitions": [
            {"from_status": None, "to_status": "draft", "actor": "Nạp dữ liệu", "at": "2026-10-09T00:59:50Z",
             "reason": None},
            {"from_status": "draft", "to_status": "prescreen", "actor": "Hệ thống", "at": "2026-10-09T00:59:51Z",
             "reason": None},
            {"from_status": "prescreen", "to_status": "in_review_r1", "actor": "Hệ thống",
             "at": "2026-10-09T00:59:52Z", "reason": None},
            {"from_status": "in_review_r1", "to_status": "in_review_r2", "actor": "Người thẩm định 1",
             "at": "2026-10-09T01:00:00Z", "reason": _DEMO_COMMENT},
            {"from_status": "in_review_r2", "to_status": "approved", "actor": "Người thẩm định 2",
             "at": "2026-10-09T01:00:05Z", "reason": _DEMO_COMMENT},
        ],
    })


class ReviewDecisionRequest(RequestSchema):
    version: int
    round: Literal[1, 2]
    decision: Decision = Field(description="pass = Đạt, revise = Cần sửa, reject = Loại.")
    comment: str | None = Field(default=None, description="Required unless the decision is pass.")

    model_config = with_example({"version": 1, "round": 1, "decision": "revise",
                                 "comment": "Phương án c và d quá giống nhau; cần viết lại phương án d."})

    @model_validator(mode="after")
    def comment_unless_pass(self):
        if self.decision != "pass" and not (self.comment or "").strip():
            raise ValueError("Cần ghi nhận xét khi chọn Cần sửa hoặc Loại.")
        return self


class ReviewDecisionResult(Schema):
    id: str
    version: int
    status: ItemStatus

    model_config = with_example({"id": _QUEUED[0], "version": 1, "status": "needs_revision"})
