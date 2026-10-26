"""A unit: one item at a time (content, quiz or remediation), and the tutor on a quiz item."""
from typing import Literal

from pydantic import Field

from app.schemas import _samples as s
from app.schemas.base import RequestSchema, Schema, with_example
from app.schemas.common import Citation, Option

_FEEDBACK = {
    "correct": False, "correct_key": s.Q1_CORRECT, "explanation": s.Q1_EXPLANATION, "rationales": s.Q1_RATIONALES,
    "citations": [s.DT_CITATION], "remediation_inserted": True,
    "remediation_note": "Đã thêm 1 ví dụ tính từng bước vì bạn chọn 5%.", "card_created": True,
}
_QUIZ_ITEM = {
    "unit_item_id": "u1-q1", "kind": "quiz", "title": None, "body": None, "citations": None, "reason": None,
    "question": {"id": s.Q1_ID, "stem": s.Q1_STEM, "options": s.Q1_OPTIONS}, "chosen": "b", "feedback": _FEEDBACK,
}
_UNIT_VIEW = {
    "session_id": 3, "unit_id": "u-dt-01", "topic": s.Q1_TOPIC, "position": 2, "total": 6, "done": False,
    "cards_created": 1, "item": _QUIZ_ITEM,
}


class Feedback(Schema):
    correct: bool
    correct_key: str
    explanation: str = Field(description="The expert explanation, always shown first.")
    rationales: dict[str, str] = Field(description="Why each option is right or wrong, by option key.")
    citations: list[Citation]
    remediation_inserted: bool
    remediation_note: str | None = Field(default=None, description="Why a remediation item was added.")
    card_created: bool

    model_config = with_example(_FEEDBACK)


class QuestionView(Schema):
    id: str
    stem: str
    options: list[Option]


class UnitItem(Schema):
    unit_item_id: str
    kind: Literal["content", "quiz", "remediation"]
    title: str | None = None
    body: str | None = Field(default=None, description="Markdown.")
    citations: list[Citation] | None = None
    reason: str | None = Field(default=None, description="For an inserted remediation item: why it is here.")
    question: QuestionView | None = None
    chosen: str | None = None
    feedback: Feedback | None = None


class UnitView(Schema):
    session_id: int
    unit_id: str
    topic: str
    position: int
    total: int
    done: bool
    cards_created: int
    item: UnitItem | None = Field(default=None, description="Null once the unit is done.")

    model_config = with_example(_UNIT_VIEW)


class UnitAnswer(RequestSchema):
    unit_item_id: str
    chosen: str
    time_ms: int | None = Field(default=None, ge=0)

    model_config = with_example({"unit_item_id": "u1-q1", "chosen": "b", "time_ms": 41000})


class UnitAdvance(RequestSchema):
    unit_item_id: str

    model_config = with_example({"unit_item_id": "u1-q1"})


class Hint(Schema):
    text: str = Field(description="Never reveals the correct option.")
    citations: list[Citation]
    generated: bool = Field(description="True when a model wrote the text; false when it is the pointer to the source "
                                        "written by code. The screen puts the AI mark on a generated hint only.")

    model_config = with_example({
        "text": "Hãy xác định mẫu số trước: đó là toàn bộ dân số của xã tại thời điểm khảo sát.",
        "citations": [s.DT_CITATION],
        "generated": True,
    })
