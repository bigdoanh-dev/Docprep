"""Trang chủ."""
from typing import Literal

from pydantic import Field

from app.schemas import _samples as s
from app.schemas.base import Schema, with_example


class NextMock(Schema):
    form_id: str
    title: str
    n_questions: int
    minutes: int
    open_attempt_id: int | None = Field(default=None, description="An attempt still running, to resume.")


class SuggestionAction(Schema):
    label_vi: str
    target: Literal["cards", "unit", "practice_set", "session"]
    id: str | None = None


class TutorSuggestion(Schema):
    """Something the rules did since the learner's last visit. Rule events only in R1.0, no model text."""
    kind: Literal["cards_created", "example_added", "practice_added"]
    text_vi: str
    action: SuggestionAction | None = None


class RecentItem(Schema):
    kind: Literal["unit", "chat"]
    id: str
    title: str
    subtitle_vi: str | None = None
    progress: float | None = Field(default=None, ge=0, le=1)


class HomeView(Schema):
    name: str
    quick_review_count: int = Field(description='"Ôn nhanh N câu": due cards plus today\'s practice items.')
    quick_review_note_vi: str | None = None
    due_cards: int
    next_mock: NextMock | None = None
    tutor_suggestions: list[TutorSuggestion] = Field(max_length=3)
    recent: list[RecentItem]

    model_config = with_example({
        "name": "Thu Hà",
        "quick_review_count": 14,
        "quick_review_note_vi": "2 thẻ mới từ câu bạn trả lời sai",
        "due_cards": 8,
        "next_mock": {"form_id": "mock-01", "title": "Đề thi thử số 1", "n_questions": 40, "minutes": 50,
                      "open_attempt_id": None},
        "tutor_suggestions": [
            {"kind": "cards_created", "text_vi": "Tạo 2 thẻ ôn từ câu bạn trả lời sai",
             "action": {"label_vi": "Xem thẻ", "target": "cards", "id": None}},
            {"kind": "example_added", "text_vi": "Thêm 1 ví dụ vào lộ trình vì câu bạn trả lời sai",
             "action": None},
            {"kind": "practice_added", "text_vi": "Bổ sung 6 câu luyện cho hôm nay",
             "action": {"label_vi": "Luyện", "target": "practice_set", "id": "31"}},
        ],
        "recent": [
            {"kind": "unit", "id": "u-dt-02", "title": "Đo lường kết hợp và sàng lọc",
             "subtitle_vi": f"{s.MODULES[0][2]} · chủ đề 2/2", "progress": 0.33},
            {"kind": "chat", "id": "12", "title": "Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?",
             "subtitle_vi": "Hỏi đáp", "progress": None},
        ],
    })
