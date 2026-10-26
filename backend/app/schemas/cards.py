"""Thẻ ôn: the due queue, a review, and decks by học phần. Scheduling runs on the server (FSRS)."""
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas import _samples as s
from app.schemas.base import RequestSchema, Schema, with_example


class DueCard(Schema):
    id: int
    front: str
    back: str
    citation: str
    source_passage_id: str
    origin: str = Field(description='"Từ quiz học phần", "Từ bài đánh giá" or "Từ đề thi thử".')
    module: str
    preview: dict[Literal["1", "2", "3", "4"], int] = Field(
        description="Seconds until the next review for each rating: 1 Học lại, 2 Khó, 3 Tốt, 4 Dễ.")


class DueCardList(Schema):
    items: list[DueCard]
    total_due: int

    model_config = with_example({
        "items": [{
            "id": 17, "front": s.Q1_STEM, "back": f"2,5%. {s.Q1_EXPLANATION}",
            "citation": "Dịch tễ học cơ bản, tr. 58", "source_passage_id": "dt-p01", "origin": "Từ quiz học phần",
            "module": s.MODULES[0][2], "preview": {"1": 60, "2": 360, "3": 600, "4": 691200},
        }],
        "total_due": 8,
    })


class CardReview(RequestSchema):
    rating: int = Field(ge=1, le=4, description="1 Học lại · 2 Khó · 3 Tốt · 4 Dễ")
    time_ms: int | None = Field(default=None, ge=0)

    model_config = with_example({"rating": 3, "time_ms": 9000})


class CardReviewResult(Schema):
    card_id: int
    due_at: datetime = Field(description="Never later than the learner's exam date.")
    remaining_due: int

    model_config = with_example({"card_id": 17, "due_at": "2026-10-10T02:20:00Z", "remaining_due": 7})


class CardPatch(RequestSchema):
    suspended: bool

    model_config = with_example({"suspended": True})


class CardState(Schema):
    id: int
    suspended: bool

    model_config = with_example({"id": 17, "suspended": True})


class Deck(Schema):
    module_id: str
    name: str
    short_name: str
    new: int
    learning: int
    due: int


class DeckList(Schema):
    """One deck per học phần."""
    items: list[Deck]

    model_config = with_example({"items": [
        {"module_id": s.MODULES[0][0], "name": s.MODULES[0][1], "short_name": s.MODULES[0][2],
         "new": 2, "learning": 5, "due": 8},
    ]})
