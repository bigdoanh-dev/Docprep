"""Thi thử: forms, a timed attempt, results and answer review. No field predicts an exam outcome."""
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas import _samples as s
from app.schemas.base import RequestSchema, Schema, with_example
from app.schemas.common import Citation, Option

_QUESTIONS = [{"id": qid, "n": n, "stem": stem, "options": s.options(texts)}
              for n, (qid, stem, texts) in enumerate(s.PRACTICE_QUESTIONS, start=1)]
_HISTORY = [{"attempt_id": 5, "submitted_at": "2026-10-09T03:05:10Z", "duration_s": 310, "score": 4, "total": 6,
             "auto_submitted": False}]
_STATUSES = ["wrong", "ok", "ok", "ok", "blank", "ok"]
_TOPICS = [s.Q1_TOPIC] * 3 + ["Đo lường kết hợp"] * 2 + ["Sàng lọc"]
_RESULTS = {
    "attempt_id": 5, "title": "Bài đánh giá năng lực", "score": 4, "total": 6, "wrong": 1, "blank": 1,
    "submitted_at": "2026-10-09T03:05:10Z", "duration_s": 310, "auto_submitted": False, "new_cards": 1,
    "priority_top": [s.Q1_TOPIC, "Đo lường kết hợp", "Sàng lọc"],
    "priority_moved_up": [s.Q1_TOPIC],
    "items": [{"n": q["n"], "question_id": q["id"], "topic": topic, "status": status}
              for q, topic, status in zip(_QUESTIONS, _TOPICS, _STATUSES)],
}
_ATTEMPT = {
    "attempt_id": 6, "title": "Bài đánh giá năng lực", "deadline_at": "2026-10-10T02:36:00Z", "remaining_s": 330,
    "warning_s": 300, "submitted": False, "questions": _QUESTIONS,
    "answers": {"q-dt-01": {"chosen": "a", "flagged": False}, "q-dt-02": {"chosen": None, "flagged": True}},
}


class ExamHistoryEntry(Schema):
    attempt_id: int
    submitted_at: datetime
    duration_s: int
    score: int
    total: int
    auto_submitted: bool


class PlanComposition(Schema):
    new: int
    wrong: int
    review: int


class PlanTopic(Schema):
    name: str
    count: int


class ExamPlan(Schema):
    """Assembled forms only: what the next test will contain."""
    composition: PlanComposition
    topics: list[PlanTopic]


class LastAttempt(Schema):
    attempt_id: int
    score: int
    total: int


class ExamForm(Schema):
    id: str
    title: str
    kind: Literal["diagnostic", "mock", "demo_short", "assembled"]
    n_questions: int
    minutes: int
    attempts_left: int | None = Field(default=None, description="Null when attempts are unlimited.")
    last: LastAttempt | None = None
    open_attempt_id: int | None = Field(default=None, description="An attempt still running, to resume.")
    open_remaining_s: int | None = None
    history: list[ExamHistoryEntry] = Field(description="Finished attempts, newest first.")
    plan: ExamPlan | None = None


class ExamList(Schema):
    items: list[ExamForm]

    model_config = with_example({"items": [
        {"id": "diag-01", "title": "Bài đánh giá năng lực", "kind": "diagnostic", "n_questions": 6, "minutes": 6,
         "attempts_left": None, "last": {"attempt_id": 5, "score": 4, "total": 6}, "open_attempt_id": None,
         "open_remaining_s": None, "history": _HISTORY, "plan": None},
        {"id": "mock-01", "title": "Đề thi thử số 1", "kind": "mock", "n_questions": 40, "minutes": 50,
         "attempts_left": None, "last": None, "open_attempt_id": None, "open_remaining_s": None, "history": [],
         "plan": None},
    ]})


class StartAttempt(RequestSchema):
    fresh: bool = Field(default=False, description='"Làm bài mới": hand in a running attempt and open a new one.')

    model_config = with_example({"fresh": False})


class AttemptQuestion(Schema):
    id: str
    n: int
    stem: str
    options: list[Option]


class SavedAnswer(RequestSchema):
    chosen: str | None = None
    flagged: bool = False

    model_config = with_example({"chosen": "a", "flagged": False})


class SavedAnswerView(Schema):
    """A saved answer as the server returns it."""
    chosen: str | None = None
    flagged: bool = False


class AttemptView(Schema):
    attempt_id: int
    title: str
    deadline_at: datetime = Field(description="Set by the server; the attempt is submitted automatically after it.")
    remaining_s: int
    warning_s: int = Field(description="Show the time warning when this many seconds remain.")
    submitted: bool
    questions: list[AttemptQuestion] = Field(description="Shuffled for this attempt, options too.")
    answers: dict[str, SavedAnswerView] = Field(description="Saved answers by question id.")

    model_config = with_example(_ATTEMPT)


class ResultItem(Schema):
    n: int
    question_id: str
    topic: str
    status: Literal["ok", "wrong", "blank"]


class Results(Schema):
    attempt_id: int
    title: str
    score: int
    total: int
    wrong: int
    blank: int
    submitted_at: datetime
    duration_s: int
    auto_submitted: bool
    new_cards: int = Field(description='"Đã cập nhật ôn tập": cards created from wrong answers.')
    priority_top: list[str] = Field(description="Topics to prioritise now, in order.")
    priority_moved_up: list[str] = Field(description="Topics this attempt moved up.")
    items: list[ResultItem]

    model_config = with_example(_RESULTS)


class ReviewOption(Schema):
    key: str
    text: str
    is_correct: bool


class AttemptItemView(Schema):
    n: int
    total: int
    question_id: str
    stem: str
    options: list[ReviewOption]
    chosen: str | None = None
    explanation: str
    rationales: dict[str, str]
    citations: list[Citation]

    model_config = with_example({
        "n": 1, "total": 6, "question_id": s.Q1_ID, "stem": s.Q1_STEM,
        "options": [{**o, "is_correct": o["key"] == s.Q1_CORRECT} for o in s.Q1_OPTIONS],
        "chosen": "b", "explanation": s.Q1_EXPLANATION, "rationales": s.Q1_RATIONALES, "citations": [s.DT_CITATION],
    })
