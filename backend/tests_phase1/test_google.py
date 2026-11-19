"""The hosted (Gemini API / Gemma) generator port, never contacting the real API or the model server."""
from datetime import datetime, timezone, timedelta
import json
import httpx
import pytest
from app.google_gateway import GoogleConfig, GoogleGateway
from app.gateway import GatewayError
from app.ollama_gateway import OllamaConfig, ModelCallUncertain
from app.phase_config import PhaseConfig

OLLAMA = OllamaConfig('http://model.invalid:11434', 'unused-generator', 'bge-m3', 16384, 2)
HOSTED = GoogleConfig('gemma-4-26b-a4b-it', 8192, 30, 'test-key')


def tags(request):
    return httpx.Response(200, json={'models': [{'name': 'bge-m3:latest', 'digest': 'embed-rev'}]})


def api(handler):
    calls = []

    def handle(request):
        calls.append(request)
        return handler(request)
    return httpx.MockTransport(handle), calls


def ok(parts=None, finish='STOP'):
    parts = parts or [{'text': 'reasoning', 'thought': True}, {'text': '{"insufficient":true}'}]
    return httpx.Response(200, json={'candidates': [{'content': {'parts': parts}, 'finishReason': finish}],
                                     'usageMetadata': {'promptTokenCount': 12, 'candidatesTokenCount': 5},
                                     'modelVersion': 'gemma-4-26b-a4b-it'})


def gateway(handler, slept=None):
    transport, calls = api(handler)
    return GoogleGateway(OLLAMA, HOSTED, transport=httpx.MockTransport(tags), api_transport=transport,
                         sleep=(slept.append if slept is not None else lambda s: None)), calls


def test_answer_goes_to_gemma_as_json_with_the_key_in_a_header():
    gw, calls = gateway(lambda r: ok())
    result = gw.complete('answer', 'system', [{'role': 'user', 'content': 'question'}], 'answer-v1')
    assert result.text == '{"insufficient":true}'           # the thought part is left out
    assert result.model == 'gemma-4-26b-a4b-it@hosted' and result.tokens_in == 12 and result.tokens_out == 5
    request = calls[0]
    assert request.url.path.endswith('/models/gemma-4-26b-a4b-it:generateContent')
    assert 'key' not in request.url.params and request.headers['x-goog-api-key'] == 'test-key'
    body = json.loads(request.content)
    assert body['systemInstruction'] == {'parts': [{'text': 'system'}]}
    assert body['contents'] == [{'role': 'user', 'parts': [{'text': 'question'}]}]
    assert body['generationConfig'] == {'responseMimeType': 'application/json', 'maxOutputTokens': 8192}


def test_identifiers_and_unknown_roles_never_reach_the_api():
    gw, calls = gateway(lambda r: ok())
    with pytest.raises(GatewayError):
        gw.complete('answer', 's', [{'role': 'user', 'content': 'gọi 0912 345 678'}], 'v1')
    with pytest.raises(GatewayError, match='role_not_configured'):
        gw.complete('embed', 's', [], 'v1')
    with pytest.raises(GatewayError, match='before_dispatch'):
        gw.complete('answer', 's', [{'role': 'user', 'content': 'q'}], 'v1',
                    deadline=datetime.now(timezone.utc) - timedelta(seconds=1))
    assert calls == []


@pytest.mark.parametrize('status', [400, 403, 500])
def test_an_error_status_is_an_acknowledged_rejection_and_not_retried(status):
    gw, calls = gateway(lambda r: httpx.Response(status, json={'error': {'code': status}}))
    with pytest.raises(GatewayError, match='hosted_request_rejected') as caught:
        gw.complete('answer', 's', [{'role': 'user', 'content': 'q'}], 'v1')
    assert not isinstance(caught.value, ModelCallUncertain) and len(calls) == 1


@pytest.mark.parametrize('status', [429, 503])
def test_overload_is_retried_twice_with_backoff_then_rejected(status):
    slept = []
    gw, calls = gateway(lambda r: httpx.Response(status, json={'error': {'code': status}}), slept)
    with pytest.raises(GatewayError, match='hosted_request_rejected'):
        gw.complete('answer', 's', [{'role': 'user', 'content': 'q'}], 'v1')
    assert len(calls) == 3 and slept == [2.0, 5.0]


def test_a_transient_overload_recovers():
    replies = iter([httpx.Response(503, json={}), ok()])
    gw, calls = gateway(lambda r: next(replies), [])
    assert gw.complete('answer', 's', [{'role': 'user', 'content': 'q'}], 'v1').text == '{"insufficient":true}'
    assert len(calls) == 2


def test_no_retry_when_the_deadline_has_no_room():
    gw, calls = gateway(lambda r: httpx.Response(503, json={}), [])
    with pytest.raises(GatewayError, match='hosted_request_rejected'):
        gw.complete('answer', 's', [{'role': 'user', 'content': 'q'}], 'v1',
                    deadline=datetime.now(timezone.utc) + timedelta(seconds=2))
    assert len(calls) == 1


def test_a_read_timeout_is_uncertain_but_a_refused_connection_is_not():
    def timeout(request):
        raise httpx.ReadTimeout('slow', request=request)

    def refused(request):
        raise httpx.ConnectError('refused', request=request)
    gw, _ = gateway(timeout)
    with pytest.raises(ModelCallUncertain):
        gw.complete('answer', 's', [{'role': 'user', 'content': 'q'}], 'v1')
    gw, _ = gateway(refused)
    with pytest.raises(GatewayError) as caught:
        gw.complete('answer', 's', [{'role': 'user', 'content': 'q'}], 'v1')
    assert not isinstance(caught.value, ModelCallUncertain)


@pytest.mark.parametrize('response,code', [
    (ok(finish='SAFETY'), 'hosted_refused'),
    (ok(finish='MAX_TOKENS'), 'hosted_output_truncated'),
    (httpx.Response(200, json={'promptFeedback': {'blockReason': 'OTHER'}}), 'hosted_refused'),
    (ok(parts=[{'text': 'only thinking', 'thought': True}]), 'hosted_invalid_completed_response'),
    (httpx.Response(200, json={'candidates': []}), 'hosted_invalid_completed_response'),
])
def test_a_withheld_or_empty_answer_is_not_used(response, code):
    gw, _ = gateway(lambda r: response)
    with pytest.raises(GatewayError, match=code):
        gw.complete('answer', 's', [{'role': 'user', 'content': 'q'}], 'v1')


def test_only_the_embedding_model_must_be_in_ollama():
    gw, _ = gateway(lambda r: ok())
    assert gw.revisions(fresh=True) == {'bge-m3': 'embed-rev', 'gemma-4-26b-a4b-it': 'hosted'}


def test_config_needs_a_key_and_never_prints_it(tmp_path, monkeypatch):
    env = tmp_path / '.env'
    env.write_text('', encoding='utf-8')
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    with pytest.raises(RuntimeError, match='GEMINI_API_KEY'):
        GoogleConfig.load(env)
    monkeypatch.setenv('GEMINI_API_KEY', '"secret-key"')
    cfg = GoogleConfig.load(env)
    assert cfg.api_key == 'secret-key' and cfg.model == 'gemma-4-26b-a4b-it'
    assert 'secret' not in repr(cfg)


def test_the_provider_is_refused_outside_dev_and_test(monkeypatch):
    monkeypatch.setenv('PHASE_MODEL_PROVIDER', 'google')
    monkeypatch.setenv('APP_ENV', 'dev')
    assert PhaseConfig.load().provider == 'google'
    monkeypatch.setenv('APP_ENV', 'production')
    with pytest.raises(RuntimeError):
        PhaseConfig.load()
