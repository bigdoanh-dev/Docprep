"""Scripted answer streams for mock mode: one event sequence per final state, chosen by X-Mock-State."""
import os
import time
from typing import Iterator

from fastapi import Request

from app.api.stub import not_implemented_error
from app.errors import ApiError
from app.schemas.base import Schema, example
from app.schemas.chat import AnswerEvent, FinalEvent, StatusEvent, StepEvent
from app.sse import EventStreamResponse, format_sse

EVENT_NAMES: dict[type[Schema], str] = {
    StatusEvent: "status", StepEvent: "step", AnswerEvent: "answer", FinalEvent: "final"}
MESSAGE_ID = 58
DEFAULT_DELAY_MS = 400
MAX_DELAY_MS = 5000


def _step(step_id: str, kind: str, running: str, done: str) -> list[StepEvent]:
    return [StepEvent(id=step_id, kind=kind, label_vi=running, status="running"),
            StepEvent(id=step_id, kind=kind, label_vi=done, status="done")]


_SEARCH = _step("s1", "search", "Đang tìm trong kho học liệu", "Đã tìm trong 3 tài liệu")
_ANSWERED: list[Schema] = [
    *_SEARCH,
    *_step("s2", "read", "Đang đọc", "Đã đọc: Lịch tiêm chủng mở rộng tr. 8"),
    StatusEvent(status="answering"),
    StatusEvent(status="checking_sources"),
    *_step("s3", "check", "Đang kiểm tra nhận định", "Đã kiểm tra 1 nhận định"),
    example(AnswerEvent),
    example(FinalEvent),
]

SCRIPTS: dict[str, list[Schema]] = {
    "answered": _ANSWERED,
    "insufficient_evidence": [
        *_SEARCH,
        AnswerEvent(text="Tài liệu hiện có chưa đủ nội dung để trả lời câu này. Mình không đoán."),
        FinalEvent(
            state="insufficient_evidence", message_id=MESSAGE_ID,
            searched=[{"document": "Dịch tễ học cơ bản", "range": "Chương 2–5"},
                      {"document": "Lịch tiêm chủng mở rộng", "range": "toàn bộ tài liệu"}],
            nearest_chapter={"passage_id": "dt-p01",
                             "label_vi": "Dịch tễ học cơ bản · Chương 2. Đo lường bệnh trạng"}),
    ],
    "declined": [
        AnswerEvent(text="Mình không tư vấn cho một ca bệnh cụ thể. Hãy liên hệ bác sĩ hoặc cơ sở y tế gần nhất."),
        FinalEvent(state="declined", message_id=MESSAGE_ID),
    ],
    "needs_clarification": [
        AnswerEvent(text="“Tỷ lệ mắc” có thể hiểu theo ba nghĩa. Bạn muốn hỏi về nghĩa nào?"),
        FinalEvent(
            state="needs_clarification", message_id=MESSAGE_ID,
            clarify_options=[
                {"term": "tỷ lệ hiện mắc", "label_vi": "Tỷ lệ hiện mắc", "query": "Tỷ lệ hiện mắc là gì?"},
                {"term": "tỷ lệ mới mắc", "label_vi": "Tỷ lệ mới mắc", "query": "Tỷ lệ mới mắc là gì?"},
                {"term": "mật độ mới mắc", "label_vi": "Mật độ mới mắc", "query": "Mật độ mới mắc là gì?"},
            ]),
    ],
    "queued": [StatusEvent(status="queued", position=2), StatusEvent(status="queued", position=1), *_ANSWERED],
}
MOCK_STATES = tuple(SCRIPTS)


def mock_stream(state: str, delay_ms: int) -> Iterator[str]:
    for i, event in enumerate(SCRIPTS[state]):
        if i and delay_ms:
            time.sleep(delay_ms / 1000)
        yield format_sse(EVENT_NAMES[type(event)], event.model_dump(mode="json"))


def mock_delay_ms() -> int:
    """Pause between events, from MOCK_STEP_DELAY_MS: 0–5000, and 400 when unset or not a number."""
    try:
        return max(0, min(int(os.environ.get("MOCK_STEP_DELAY_MS", DEFAULT_DELAY_MS)), MAX_DELAY_MS))
    except ValueError:
        return DEFAULT_DELAY_MS


def mock_sse_response(request: Request, x_mock_state: str | None) -> EventStreamResponse:
    """Body of a streaming contract stub: the scripted stream in mock mode, 501 otherwise."""
    if request.app.state.mode != "mock":
        raise not_implemented_error()
    state = x_mock_state or "answered"
    if state not in SCRIPTS:
        raise ApiError(422, "invalid_mock_state", "Giá trị X-Mock-State không hợp lệ.", {"allowed": list(MOCK_STATES)})
    return EventStreamResponse(mock_stream(state, mock_delay_ms()),
                               headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
