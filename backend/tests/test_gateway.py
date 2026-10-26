from pathlib import Path
from types import SimpleNamespace

import pytest

from app.gateway import AnthropicGateway, FakeGateway, GatewayError

CFG = {
    "timeout_s": 20, "max_retries": 0, "max_tokens": 8000,
    "models": {"answer": {"id": "claude-sonnet-5-5", "effort": "low"}, "check": {"id": "claude-haiku-4-5"}},
    "price_per_mtok": {"claude-sonnet-5-5": {"in": 2.0, "out": 10.0}},
}
MSG = [{"role": "user", "content": "q"}]


def response(text="ok", stop_reason="end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=2), stop_reason=stop_reason, model="claude-sonnet-5-5")


class OkClient:
    def __init__(self, resp=None):
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)
        self._resp = resp or response()

    def _create(self, **kw):
        self.calls.append(kw)
        return self._resp


class FailClient:
    def __init__(self):
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        raise ConnectionError("network down")


def test_success_returns_text_tokens_cost_and_writes_cache(tmp_path):
    gw = AnthropicGateway(CFG, "k", replay=False, cache_dir=tmp_path, client=OkClient())
    r = gw.complete("answer", "sys", MSG, "answer-v1")
    assert r.text == "ok" and r.tokens_in == 10 and r.tokens_out == 2 and not r.from_cache
    assert r.model == "claude-sonnet-5-5" and r.prompt_version == "answer-v1"
    assert r.cost == pytest.approx((10 * 2.0 + 2 * 10.0) / 1_000_000)
    assert len(list(tmp_path.iterdir())) == 1


def test_effort_sent_only_when_configured(tmp_path):
    client = OkClient()
    gw = AnthropicGateway(CFG, "k", False, tmp_path, client)
    gw.complete("answer", "s", MSG, "answer-v1")
    gw.complete("check", "s", MSG, "check-v1")
    assert client.calls[0]["output_config"] == {"effort": "low"} and client.calls[0]["system"] == "s"
    assert "output_config" not in client.calls[1] and client.calls[1]["model"] == "claude-haiku-4-5"
    assert "temperature" not in client.calls[0]


def test_failure_served_from_cache_when_replay(tmp_path):
    AnthropicGateway(CFG, "k", False, tmp_path, OkClient()).complete("answer", "s", MSG, "answer-v1")
    r = AnthropicGateway(CFG, "k", True, tmp_path, FailClient()).complete("answer", "s", MSG, "answer-v1")
    assert r.text == "ok" and r.from_cache


def test_failure_without_cache_raises(tmp_path):
    with pytest.raises(GatewayError):
        AnthropicGateway(CFG, "k", True, tmp_path, FailClient()).complete("answer", "s", MSG, "answer-v1")


def test_failure_without_replay_raises_even_if_cached(tmp_path):
    AnthropicGateway(CFG, "k", False, tmp_path, OkClient()).complete("answer", "s", MSG, "answer-v1")
    with pytest.raises(GatewayError):
        AnthropicGateway(CFG, "k", False, tmp_path, FailClient()).complete("answer", "s", MSG, "answer-v1")


def test_refusal_is_an_error_not_an_answer(tmp_path):
    client = OkClient(response(text="", stop_reason="refusal"))
    with pytest.raises(GatewayError):
        AnthropicGateway(CFG, "k", False, tmp_path, client).complete("answer", "s", MSG, "answer-v1")
    assert list(tmp_path.iterdir()) == []


def test_fake_gateway_scripts_responses_and_records_calls():
    gw = FakeGateway(["a", "b"])
    assert gw.complete("answer", "s", MSG, "v").text == "a" and gw.complete("answer", "s", MSG, "v").text == "b"
    assert len(gw.calls) == 2 and gw.calls[0]["task"] == "answer"


def test_only_gateway_imports_anthropic():
    app_dir = Path(__file__).resolve().parents[1] / "app"
    hits = [p.name for p in app_dir.rglob("*.py") if "import anthropic" in p.read_text(encoding="utf-8")]
    assert hits == ["gateway.py"]


class NoKeyClient:
    """The SDK raises TypeError at call time when no credential can be resolved."""

    def __init__(self):
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        raise TypeError("Could not resolve authentication method")


def test_missing_credentials_is_a_gateway_error(tmp_path):
    with pytest.raises(GatewayError):
        AnthropicGateway(CFG, None, False, tmp_path, NoKeyClient()).complete("answer", "s", MSG, "answer-v1")


# ---- final review: replay cache robustness and the "prefer" mode for the stage ----

def test_corrupt_cache_file_is_a_gateway_error_not_a_crash(tmp_path):
    AnthropicGateway(CFG, "k", False, tmp_path, OkClient()).complete("answer", "s", MSG, "answer-v1")
    next(tmp_path.iterdir()).write_text("{not json", encoding="utf-8")
    with pytest.raises(GatewayError):
        AnthropicGateway(CFG, "k", True, tmp_path, FailClient()).complete("answer", "s", MSG, "answer-v1")


def test_cache_that_cannot_be_written_does_not_lose_the_answer(tmp_path):
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x", encoding="utf-8")
    r = AnthropicGateway(CFG, "k", False, blocker, OkClient()).complete("answer", "s", MSG, "answer-v1")
    assert r.text == "ok"


def test_prefer_mode_serves_the_rehearsed_answer_without_calling_the_model(tmp_path):
    AnthropicGateway(CFG, "k", False, tmp_path, OkClient(response("rehearsed"))).complete("answer", "s", MSG, "answer-v1")
    live = OkClient(response("a fresh sample"))
    r = AnthropicGateway(CFG, "k", "prefer", tmp_path, live).complete("answer", "s", MSG, "answer-v1")
    assert r.text == "rehearsed" and r.from_cache and live.calls == []


def test_prefer_mode_calls_the_model_for_an_unrehearsed_prompt(tmp_path):
    live = OkClient(response("fresh"))
    r = AnthropicGateway(CFG, "k", "prefer", tmp_path, live).complete("answer", "s", MSG, "answer-v1")
    assert r.text == "fresh" and not r.from_cache and len(live.calls) == 1


def test_replay_mode_from_env_value():
    from app.gateway import replay_mode
    assert [replay_mode(v) for v in (None, "0", "1", "prefer", "PREFER", "x")] == ["off", "off", "fallback", "prefer", "prefer", "off"]
