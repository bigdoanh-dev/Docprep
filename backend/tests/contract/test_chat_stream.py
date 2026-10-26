"""The mock chat stream: one scripted event sequence per final state, every event a contract model."""
import pytest

from app.api.mock_chat import MOCK_STATES
from app.schemas.chat import AnswerEvent, FinalEvent, StatusEvent, StepEvent
from tests.conftest import sse_events

URL = "/v1/chat/sessions/1/messages"
BODY = {"text": "Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?"}
MODELS = {"status": StatusEvent, "step": StepEvent, "answer": AnswerEvent, "final": FinalEvent}


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    monkeypatch.setenv("MOCK_STEP_DELAY_MS", "0")


def _events(mock_client, state=None):
    headers = {"X-Mock-State": state} if state else {}
    r = mock_client.post(URL, json=BODY, headers=headers)
    assert r.status_code == 200, r.text
    return sse_events(r.text)


@pytest.mark.parametrize("state", MOCK_STATES)
def test_every_event_validates_and_the_stream_ends_with_answer_then_final(mock_client, state):
    events = _events(mock_client, state)
    for name, data in events:
        MODELS[name].model_validate(data)
    assert [name for name, _ in events][-2:] == ["answer", "final"]


def test_default_state_is_answered_with_a_citation(mock_client):
    events = _events(mock_client)
    answer = next(d for n, d in events if n == "answer")
    final = events[-1][1]
    assert final["state"] == "answered" and len(answer["citations"]) == 1
    assert final["trace_summary"] == {"sources": 1, "claims_checked": 1, "claims_removed": 0}


def test_each_step_runs_then_completes(mock_client):
    steps = [d for n, d in _events(mock_client) if n == "step"]
    by_id = {}
    for s in steps:
        by_id.setdefault(s["id"], []).append(s["status"])
    assert by_id and all(v == ["running", "done"] for v in by_id.values())


def test_declined_has_no_steps_and_no_citations(mock_client):
    events = _events(mock_client, "declined")
    assert [n for n, _ in events] == ["answer", "final"]
    assert events[0][1]["citations"] == []


def test_queued_reports_positions_before_answering(mock_client):
    statuses = [d for n, d in _events(mock_client, "queued") if n == "status"]
    assert [s.get("position") for s in statuses[:2]] == [2, 1]


def test_needs_clarification_offers_two_to_four_options(mock_client):
    final = _events(mock_client, "needs_clarification")[-1][1]
    assert final["state"] == "needs_clarification" and 2 <= len(final["clarify_options"]) <= 4


def test_unknown_mock_state_is_a_422_with_the_error_body(mock_client):
    r = mock_client.post(URL, json=BODY, headers={"X-Mock-State": "nonsense"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_mock_state"
    assert "answered" in r.json()["error"]["details"]["allowed"]


def test_event_schemas_are_in_the_contract():
    from app.main import create_app
    from app.openapi import build_openapi
    spec = build_openapi(create_app("mock"))
    schemas = spec["components"]["schemas"]
    assert {"StatusEvent", "StepEvent", "AnswerEvent", "FinalEvent"} <= set(schemas)
    op = spec["paths"]["/v1/chat/sessions/{session_id}/messages"]["post"]
    refs = op["responses"]["200"]["content"]["text/event-stream"]["schema"]["oneOf"]
    assert len(refs) == 4
