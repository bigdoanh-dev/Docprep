"""A practice set: a small list of approved questions on one competency.

The daily session's step 2, an accepted chat suggestion and "Làm câu tương tự" all produce one.
"""
from typing import Literal

from pydantic import Field

from app.schemas import _samples as s
from app.schemas.base import RequestSchema, Schema, with_example
from app.schemas.common import Citation, Option

_REASON = "Bạn sai 3 câu về Đo lường tần suất bệnh trong 7 ngày qua · bạn chưa gặp câu này trong 14 ngày."
_FEEDBACK = {
    "correct": False, "correct_key": s.Q1_CORRECT, "explanation": s.Q1_EXPLANATION, "rationales": s.Q1_RATIONALES,
    "citations": [s.DT_CITATION], "next": {"kind": "same_type"}, "card_created": True, "remediation": s.REMEDIATION,
}
_ITEMS = [
    {"question_id": qid, "n": n, "stem": stem, "options": s.options(texts), "reason_vi": _REASON,
     "chosen": "b" if n == 1 else None, "feedback": _FEEDBACK if n == 1 else None}
    for n, (qid, stem, texts) in enumerate(s.PRACTICE_QUESTIONS, start=1)
]


class PracticeNext(Schema):
    kind: Literal["same_type", "harder", "easier", "done"] = Field(
        description="What follows this answer. R1.0 sends only same_type and done; harder and easier are R1.1.")


class Remediation(Schema):
    title: str
    body: str = Field(description="Markdown.")
    citations: list[Citation]
    reason: str = Field(description="Why this item was added.")


class PracticeFeedback(Schema):
    correct: bool
    correct_key: str
    explanation: str = Field(description="The expert explanation, always shown first.")
    rationales: dict[str, str] = Field(description="Why each option is right or wrong, by option key.")
    citations: list[Citation]
    next: PracticeNext
    card_created: bool
    remediation: Remediation | None = Field(default=None, description="Inserted after a wrong answer when one exists.")

    model_config = with_example(_FEEDBACK)


class PracticeItem(Schema):
    question_id: str
    n: int
    stem: str
    options: list[Option]
    reason_vi: str = Field(description='"Vì sao câu này?", built from the rule that chose the item.')
    chosen: str | None = None
    feedback: PracticeFeedback | None = None


class PracticeSetView(Schema):
    id: int
    source: Literal["session", "chat_suggestion", "quiz_similar"]
    competency_code: str
    topic: str
    total: int
    answered: int
    completed: bool
    items: list[PracticeItem]

    model_config = with_example({
        "id": 31, "source": "session", "competency_code": "FND", "topic": s.Q1_TOPIC, "total": len(_ITEMS),
        "answered": 1, "completed": False, "items": _ITEMS,
    })


class PracticeAnswer(RequestSchema):
    question_id: str
    chosen: str
    time_ms: int | None = Field(default=None, ge=0)

    model_config = with_example({"question_id": s.Q1_ID, "chosen": "b", "time_ms": 52000})


class Graded(Schema):
    correct: int
    total: int


class MasteryUpdated(Schema):
    competencies: int


class CardsCreated(Schema):
    n: int


class Tomorrow(Schema):
    reordered: bool
    top_item: str


class AdaptationSummary(Schema):
    """What the set changed, from stored results. A line that does not apply is null, never a zero."""
    graded: Graded
    mastery_updated: MasteryUpdated | None = None
    cards_created: CardsCreated | None = None
    tomorrow: Tomorrow | None = None

    model_config = with_example({
        "graded": {"correct": 4, "total": 6},
        "mastery_updated": {"competencies": 1},
        "cards_created": {"n": 2},
        "tomorrow": {"reordered": True, "top_item": s.Q1_TOPIC},
    })
