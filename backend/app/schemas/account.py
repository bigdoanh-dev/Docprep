"""Consent, the learner's profile and their own data."""
from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import RequestSchema, Schema, with_example

_CONSENT = {
    "version": "2026-10",
    "service_given_at": "2026-10-10T02:05:00Z",
    "research_given_at": None,
}
_ME = {
    "pseudonym_id": "HV-000123",
    "display_name": "Thu Hà",
    "audience": "student",
    "organisation": "CSĐT A",
    "focus_module_ids": ["g1"],
    "exam_date": "2027-03-01",
    "target_retention": 0.9,
    "new_cards_per_day": 20,
    "max_reviews_per_day": 200,
    "diagnostic_prompt_dismissed": False,
    "consent": _CONSENT,
}


class ConsentText(Schema):
    version: str
    service_text_vi: str
    research_text_vi: str

    model_config = with_example({
        "version": "2026-10",
        "service_text_vi": "Văn bản mẫu: tôi đồng ý để ứng dụng lưu kết quả học tập của tôi nhằm cung cấp dịch vụ ôn thi.",
        "research_text_vi": "Văn bản mẫu: tôi đồng ý cho phép dùng nhật ký sử dụng đã ẩn danh của tôi cho nghiên cứu. "
                            "Tôi có thể rút lại bất cứ lúc nào.",
    })


class ConsentRequest(RequestSchema):
    version: str
    service: bool
    research: bool = False

    model_config = with_example({"version": "2026-10", "service": True, "research": False})


class ConsentStatus(Schema):
    version: str | None = None
    service_given_at: datetime | None = None
    research_given_at: datetime | None = None

    model_config = with_example(_CONSENT)


class Me(Schema):
    pseudonym_id: str
    display_name: str
    audience: Literal["student", "graduate"]
    organisation: str | None = None
    focus_module_ids: list[str]
    exam_date: date
    target_retention: Literal[0.85, 0.9, 0.95]
    new_cards_per_day: int
    max_reviews_per_day: int
    diagnostic_prompt_dismissed: bool
    consent: ConsentStatus

    model_config = with_example(_ME)


class MePatch(RequestSchema):
    display_name: str | None = None
    focus_module_ids: list[str] | None = None
    exam_date: date | None = None
    target_retention: Literal[0.85, 0.9, 0.95] | None = None
    new_cards_per_day: int | None = Field(default=None, ge=1, le=100)
    max_reviews_per_day: int | None = Field(default=None, ge=1, le=1000)
    diagnostic_prompt_dismissed: bool | None = None

    model_config = with_example({"focus_module_ids": ["g1", "g4"], "new_cards_per_day": 15})


class MyData(Schema):
    exported_at: datetime
    profile: Me
    responses: list[dict]
    attempts: list[dict]
    cards: list[dict]
    chat_sessions: list[dict]

    model_config = with_example({
        "exported_at": "2026-10-10T02:30:00Z",
        "profile": _ME,
        "responses": [{"question_id": "q-dt-01", "context": "unit", "chosen": "b", "correct": False,
                       "created_at": "2026-10-09T13:02:11Z"}],
        "attempts": [{"attempt_id": 4, "form_id": "mock-01", "submitted_at": "2026-10-06T03:48:00Z",
                      "score": 33, "total": 40}],
        "cards": [{"id": 17, "front": "Tỷ lệ hiện mắc khác tỷ lệ mới mắc ở điểm nào?", "due_at": "2026-10-11T00:00:00Z"}],
        "chat_sessions": [{"id": 12, "title": "Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?", "messages": 2}],
    })


class DeletionAccepted(Schema):
    requested_at: datetime

    model_config = with_example({"requested_at": "2026-10-10T02:40:00Z"})
