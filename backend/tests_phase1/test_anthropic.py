"""The hosted (Anthropic) generator port, never contacting the real API or the model server."""
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import httpx
import pytest
import anthropic
from app.anthropic_gateway import AnthropicConfig, HostedGateway, FALLBACK_BETA
from app.gateway import GatewayError
from app.ollama_gateway import OllamaConfig, ModelCallUncertain
from app.phase_config import PhaseConfig
from app.repo import corpus

OLLAMA = OllamaConfig('http://model.invalid:11434', 'unused-generator', 'bge-m3', 16384, 2)
HOSTED = AnthropicConfig('claude-opus-5-5', 'medium', 16000, 30)


def tags(request):
    return httpx.Response(200, json={'models': [{'name': 'bge-m3:latest', 'digest': 'embed-rev'}]})


class FakeMessages:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.reply


class FakeClient:
    def __init__(self, messages):
        self.beta = SimpleNamespace(messages=messages)
        self.timeouts = []

    def with_options(self, timeout):
        self.timeouts.append(timeout)
        return self


def reply(text='{"insufficient":true}', stop='end_turn'):
    return SimpleNamespace(stop_reason=stop, model='claude-opus-5-5',
                           content=[SimpleNamespace(type='thinking', thinking=''), SimpleNamespace(type='text', text=text)],
                           usage=SimpleNamespace(input_tokens=11, output_tokens=7))


def gateway(messages):
    client = FakeClient(messages)
    return HostedGateway(OLLAMA, HOSTED, client=client, transport=httpx.MockTransport(tags)), client


def test_answer_goes_to_the_hosted_model_with_fallback_and_no_retry_owner():
    messages = FakeMessages(reply())
    gw, client = gateway(messages)
    result = gw.complete('answer', 'system', [{'role': 'user', 'content': 'question'}], 'answer-v1')
    assert result.text == '{"insufficient":true}' and result.model == 'claude-opus-5-5@hosted'
    assert result.tokens_in == 11 and result.tokens_out == 7 and result.cost is None and not result.from_cache
    sent = messages.calls[0]
    assert sent['model'] == 'claude-opus-5-5' and sent['system'] == 'system'
    assert sent['messages'] == [{'role': 'user', 'content': 'question'}]
    assert sent['output_config'] == {'effort': 'medium'} and sent['betas'] == [FALLBACK_BETA] and sent['fallbacks'] == 'default'
    assert 'thinking' not in sent and 'temperature' not in sent
    assert client.timeouts == [30]


def test_identifiers_and_unknown_roles_never_reach_the_api():
    messages = FakeMessages(reply())
    gw, _ = gateway(messages)
    with pytest.raises(GatewayError):
        gw.complete('answer', 's', [{'role': 'user', 'content': 'gọi 0912 345 678'}], 'v1')
    with pytest.raises(GatewayError, match='role_not_configured'):
        gw.complete('check', 's', [], 'check-v1')
    assert messages.calls == []


def test_the_deadline_bounds_the_call_and_an_expired_one_does_not_dispatch():
    messages = FakeMessages(reply())
    gw, client = gateway(messages)
    soon = datetime.now(timezone.utc) + timedelta(seconds=5)
    gw.complete('answer', 's', [{'role': 'user', 'content': 'q'}], 'v1', deadline=soon)
    assert 0 < client.timeouts[0] <= 5
    with pytest.raises(GatewayError, match='before_dispatch'):
        gw.complete('answer', 's', [{'role': 'user', 'content': 'q'}], 'v1',
                    deadline=datetime.now(timezone.utc) - timedelta(seconds=1))
    assert len(messages.calls) == 1


def request():
    return httpx.Request('POST', 'https://api.anthropic.com/v1/messages')


@pytest.mark.parametrize('error', [
    anthropic.APITimeoutError(request=request()),
    anthropic.APIConnectionError(request=request()),
])
def test_an_unacknowledged_call_is_uncertain(error):
    gw, _ = gateway(FakeMessages(error=error))
    with pytest.raises(ModelCallUncertain):
        gw.complete('answer', 's', [{'role': 'user', 'content': 'q'}], 'v1')


@pytest.mark.parametrize('status', [400, 401, 403, 404, 429, 500, 529])
def test_an_error_status_is_an_acknowledged_rejection(status):
    response = httpx.Response(status, request=request(), json={'type': 'error', 'error': {'type': 'x', 'message': 'm'}})
    error = anthropic.APIStatusError('m', response=response, body=None)
    gw, _ = gateway(FakeMessages(error=error))
    with pytest.raises(GatewayError, match='hosted_request_rejected') as caught:
        gw.complete('answer', 's', [{'role': 'user', 'content': 'q'}], 'v1')
    assert not isinstance(caught.value, ModelCallUncertain)


@pytest.mark.parametrize('stop,code', [('refusal', 'hosted_refused'), ('max_tokens', 'hosted_output_truncated')])
def test_a_refused_or_truncated_answer_is_not_used(stop, code):
    gw, _ = gateway(FakeMessages(reply(stop=stop)))
    with pytest.raises(GatewayError, match=code):
        gw.complete('answer', 's', [{'role': 'user', 'content': 'q'}], 'v1')


def test_only_the_embedding_model_must_be_in_ollama():
    gw, _ = gateway(FakeMessages(reply()))
    assert gw.revisions(fresh=True) == {'bge-m3': 'embed-rev', 'claude-opus-5-5': 'hosted'}
    missing = HostedGateway(OLLAMA, HOSTED, client=FakeClient(FakeMessages()),
                            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={'models': []})))
    with pytest.raises(GatewayError, match='ollama_not_ready'):
        missing.revisions(fresh=True)


def test_config_needs_a_key_and_valid_limits(tmp_path, monkeypatch):
    env = tmp_path / '.env'
    env.write_text('YHDP_ANTHROPIC_MODEL=claude-opus-5-5\n', encoding='utf-8')
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    with pytest.raises(RuntimeError, match='ANTHROPIC_API_KEY'):
        AnthropicConfig.load(env)
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-test')
    assert AnthropicConfig.load(env) == AnthropicConfig('claude-opus-5-5', 'medium', 16000, 120)
    monkeypatch.setenv('YHDP_ANTHROPIC_EFFORT', 'extreme')
    with pytest.raises(RuntimeError):
        AnthropicConfig.load(env)


def test_the_provider_is_refused_outside_dev_and_test(monkeypatch):
    monkeypatch.setenv('PHASE_MODEL_PROVIDER', 'anthropic')
    monkeypatch.setenv('APP_ENV', 'test')
    assert PhaseConfig.load().provider == 'anthropic'
    monkeypatch.setenv('APP_ENV', 'production')
    with pytest.raises(RuntimeError):
        PhaseConfig.load()


def test_an_unsigned_release_needs_the_explicit_dev_opt_in(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'test')
    monkeypatch.delenv('PHASE_ALLOW_UNVERIFIED_CORPUS', raising=False)
    assert not corpus.unverified_allowed()
    monkeypatch.setenv('PHASE_ALLOW_UNVERIFIED_CORPUS', '1')
    assert corpus.unverified_allowed()
    monkeypatch.setenv('APP_ENV', 'production')
    assert not corpus.unverified_allowed()
