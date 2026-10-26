"""Hỏi đáp: sessions, the answer stream and its events, sources, suggestions."""
from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.base import RequestSchema, Schema, with_example
from app.schemas.common import Citation

ChatState = Literal["answered", "insufficient_evidence", "declined", "needs_clarification"]
# "table" and "calc" are reserved: R1.0 only ever sends "text".
AnswerFormat = Literal["text", "table", "calc"]

_CITATION = {
    "n": 1, "passage_id": "tc-p02", "document": "Lịch tiêm chủng mở rộng",
    "chapter": "Phần 2. Lịch tiêm chủng cho trẻ em", "section": "2.1 Vắc xin tiêm cho trẻ sơ sinh",
    "page": 8, "article": None,
}
_ANSWER_TEXT = "Vắc xin viêm gan B mũi sơ sinh được tiêm trong vòng 24 giờ đầu sau sinh. [1]"
_SUGGESTION_REASON = "Bạn từng trả lời sai một câu về lịch tiêm chủng trong Đề thi thử số 1."
_SUGGESTIONS = [
    {"id": 7, "kind": "practise", "label_vi": "Luyện 3 câu đã duyệt", "reason_vi": _SUGGESTION_REASON, "n_items": 3},
    {"id": 8, "kind": "add_to_tomorrow", "label_vi": "Thêm vào phiên ngày mai", "reason_vi": _SUGGESTION_REASON,
     "n_items": None},
]
_TRACE = {"sources": 1, "claims_checked": 1, "claims_removed": 0}


class NewChatSession(RequestSchema):
    title: str | None = None
    module_id: str | None = Field(default=None, description="Limit retrieval to one học phần.")
    question_id: str | None = Field(default=None, description="Open the chat from a quiz item.")

    model_config = with_example({"title": None, "module_id": None, "question_id": None})


class ChatSessionRef(Schema):
    id: int

    model_config = with_example({"id": 12})


class ChatSessionSummary(Schema):
    id: int
    title: str
    updated_at: datetime


class ChatSessionList(Schema):
    items: list[ChatSessionSummary]
    next_cursor: str | None = None

    model_config = with_example({
        "items": [{"id": 12, "title": "Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?",
                   "updated_at": "2026-10-09T08:12:00Z"}],
        "next_cursor": None,
    })


class NewChatMessage(RequestSchema):
    text: str
    detail: bool = Field(default=False, description='"Giải thích thêm": the same question, asked for more detail.')
    clarifies_message_id: int | None = Field(
        default=None, description="Set when this message answers a needs_clarification message.")

    model_config = with_example({
        "text": "Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?", "detail": False, "clarifies_message_id": None})

    @field_validator("text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be blank")
        return v.strip()


class TraceSummary(Schema):
    sources: int
    claims_checked: int
    claims_removed: int


class ClarifyOption(Schema):
    term: str
    label_vi: str
    query: str = Field(description="The clarified question to send when the learner taps this option.")


class SearchedSource(Schema):
    document: str
    range: str


class NearestChapter(Schema):
    passage_id: str
    label_vi: str


class ChatSuggestion(Schema):
    id: int
    kind: Literal["practise", "add_to_tomorrow"]
    label_vi: str
    reason_vi: str
    n_items: int | None = None


class StatusEvent(Schema):
    """SSE event `status`."""
    status: Literal["queued", "answering", "checking_sources"]
    position: int | None = Field(default=None, description="Place in the queue; only with status queued.")

    model_config = with_example({"status": "answering", "position": None})


class StepEvent(Schema):
    """SSE event `step`: one real pipeline stage. Sent once as running and once as done, with the same id."""
    id: str
    kind: Literal["search", "read", "lookup_table", "lookup_glossary", "get_item", "check"]
    label_vi: str
    status: Literal["running", "done"]

    model_config = with_example(
        {"id": "s2", "kind": "read", "label_vi": "Đã đọc: Lịch tiêm chủng mở rộng tr. 8", "status": "done"})


class AnswerEvent(Schema):
    """SSE event `answer`: the text, released only after the post-check."""
    text: str
    format: AnswerFormat = "text"
    citations: list[Citation] = []
    notice: str | None = None

    model_config = with_example({"text": _ANSWER_TEXT, "format": "text", "citations": [_CITATION], "notice": None})


class FinalEvent(Schema):
    """SSE event `final`: always the last event of the stream."""
    state: ChatState
    message_id: int
    format: AnswerFormat = "text"
    trace_summary: TraceSummary | None = None
    clarify_options: list[ClarifyOption] = []
    searched: list[SearchedSource] = []
    nearest_chapter: NearestChapter | None = None
    suggestions: list[ChatSuggestion] = []

    model_config = with_example({
        "state": "answered", "message_id": 58, "format": "text", "trace_summary": _TRACE, "clarify_options": [],
        "searched": [], "nearest_chapter": None, "suggestions": _SUGGESTIONS,
    })


class ChatMessage(Schema):
    id: int
    role: Literal["user", "assistant"]
    text: str
    created_at: datetime
    state: ChatState | None = None
    format: AnswerFormat | None = None
    citations: list[Citation] = []
    notice: str | None = None
    trace_summary: TraceSummary | None = None
    clarify_options: list[ClarifyOption] = []
    searched: list[SearchedSource] = []
    nearest_chapter: NearestChapter | None = None
    suggestions: list[ChatSuggestion] = []
    helpful: bool | None = None
    trace: list[StepEvent] = Field(default=[], description="The steps of an answer, as sent when it was made, in their done form.")


class ChatMessageList(Schema):
    items: list[ChatMessage]
    next_cursor: str | None = None

    model_config = with_example({
        "items": [
            {"id": 57, "role": "user", "text": "Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?",
             "created_at": "2026-10-09T08:11:40Z", "state": None, "format": None, "citations": [], "notice": None,
             "trace_summary": None, "clarify_options": [], "searched": [], "nearest_chapter": None,
             "suggestions": [], "helpful": None, "trace": []},
            {"id": 58, "role": "assistant", "text": _ANSWER_TEXT, "created_at": "2026-10-09T08:12:00Z",
             "state": "answered", "format": "text", "citations": [_CITATION], "notice": None,
             "trace_summary": _TRACE, "clarify_options": [], "searched": [], "nearest_chapter": None,
             "suggestions": _SUGGESTIONS, "helpful": True,
             "trace": [{"id": "s1", "kind": "search", "label_vi": "Đã tìm trong 9 tài liệu", "status": "done"},
                       {"id": "s2", "kind": "read", "label_vi": "Đã đọc: Lịch tiêm chủng mở rộng tr. 8", "status": "done"},
                       {"id": "s3", "kind": "check", "label_vi": "Đã kiểm tra 1 nhận định", "status": "done"}]},
        ],
        "next_cursor": None,
    })


class SuggestionAccepted(Schema):
    kind: Literal["practise", "add_to_tomorrow"]
    practice_set_id: int | None = Field(default=None, description="Set for kind practise.")
    for_date: date | None = Field(default=None, description="Set for kind add_to_tomorrow.")

    model_config = with_example({"kind": "practise", "practice_set_id": 31, "for_date": None})


class RatingRequest(RequestSchema):
    helpful: bool

    model_config = with_example({"helpful": True})


class PassageView(Schema):
    id: str
    document: str
    chapter: str | None = None
    section: str | None = None
    page: int | None = None
    article: str | None = None
    excerpt: str
    demo_label: str
    validity_note: str | None = None

    model_config = with_example({
        "id": "tc-p02", "document": "Lịch tiêm chủng mở rộng", "chapter": "Phần 2. Lịch tiêm chủng cho trẻ em",
        "section": "2.1 Vắc xin tiêm cho trẻ sơ sinh", "page": 8, "article": None,
        "excerpt": "Trẻ sơ sinh được tiêm hai loại vắc xin. Vắc xin viêm gan B mũi sơ sinh được tiêm trong vòng 24 "
                   "giờ đầu sau sinh.",
        "demo_label": "Tài liệu demo – chưa thẩm định", "validity_note": None,
    })
