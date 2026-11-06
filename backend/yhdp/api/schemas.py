"""HTTP request models shared by the API feature routes."""

from typing import Literal

from pydantic import BaseModel


class Login(BaseModel):
    username: str
    password: str


class PracticeAnswer(BaseModel):
    item_id: int
    chosen: str | None
    seconds: float | None = None
    confidence: Literal["sure", "unsure", "guess"] | None = None
    card_id: int | None = None


class CardReview(BaseModel):
    rating: Literal["again", "hard", "good"]
    item_id: int | None = None


class NewSet(BaseModel):
    size: int
    timed: bool = True


class SetAnswers(BaseModel):
    answers: dict[str, str | None]
    seconds: float | None = None


class Flag(BaseModel):
    reason: str


class McqDecision(BaseModel):
    action: str
    note: str = ""
