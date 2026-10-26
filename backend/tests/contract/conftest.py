import pytest


@pytest.fixture(autouse=True)
def no_mock_stream_delay(monkeypatch):
    """The mock streams pause between events for the app engineer's benefit; tests do not wait."""
    monkeypatch.setenv("MOCK_STEP_DELAY_MS", "0")
