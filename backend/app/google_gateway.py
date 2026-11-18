"""Dev/test only: generation on the Gemini API (Gemma models), embeddings still on local Ollama (bge-m3).

Same rules as the other ports: the turn's reservation comes first, the prompt is checked for
identifiers, there is no transport retry, and a call whose outcome is unknown (read timeout, dropped
connection after sending) is reported as uncertain so the reservation stays quarantined. The key
goes in a header, never in the URL, so it cannot reach access logs. Learner text reaches a cloud model
here, and on the free tier Google may use it to improve its products: demo/synthetic learners only.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import time

import httpx
from dotenv import dotenv_values

from app.config import BACKEND_DIR
from app.gateway import GatewayError, ModelResult
from app.ollama_gateway import ModelCallUncertain, OllamaConfig, OllamaGateway, model_name
from app.privacy import validate_prompt

API = 'https://generativelanguage.googleapis.com/v1beta'
TASKS = ('answer', 'tutor', 'hint', 'quiz_chat')
# Finish reasons that mean the answer was withheld, not completed.
REFUSED = {'SAFETY', 'RECITATION', 'BLOCKLIST', 'PROHIBITED_CONTENT', 'SPII', 'IMAGE_SAFETY'}
# Overload and rate-limit answers mean nothing was generated, so a retry cannot duplicate an answer.
# Only these are retried; an uncertain outcome (timeout after sending) never is.
RETRY_STATUS = {429, 503}
RETRY_DELAYS = (2.0, 5.0)


@dataclass(frozen=True)
class GoogleConfig:
    model: str
    max_tokens: int
    timeout_s: float
    api_key: str

    def __repr__(self):  # never print the key
        return f'GoogleConfig(model={self.model!r}, max_tokens={self.max_tokens}, timeout_s={self.timeout_s})'

    @classmethod
    def load(cls, path: Path | None = None):
        values = {**dotenv_values(path or BACKEND_DIR / '.env'), **os.environ}
        key = str(values.get('GEMINI_API_KEY') or '').strip().strip('"\'')
        if not key:
            raise RuntimeError('Set GEMINI_API_KEY in backend/.env for the google provider')
        model = str(values.get('YHDP_GOOGLE_MODEL') or 'gemma-4-26b-a4b-it').strip()
        max_tokens = int(values.get('YHDP_GOOGLE_MAX_TOKENS', 8192))
        timeout = float(values.get('YHDP_GOOGLE_TIMEOUT_SECONDS', 120))
        if not model.replace('-', '').replace('.', '').isalnum() or not 1 <= max_tokens <= 32768 \
                or not 0 < timeout <= 300 or not math.isfinite(timeout):
            raise RuntimeError('Invalid Google model/max_tokens/timeout')
        return cls(model, max_tokens, timeout, key)


class GoogleGateway(OllamaGateway):
    """complete() on the Gemini API; embed(), embedding revisions and index jobs inherited from Ollama."""
    resource = 'hosted:shared'

    def __init__(self, cfg: OllamaConfig, hosted: GoogleConfig, transport=None, api_transport=None, sleep=time.sleep):
        super().__init__(cfg, transport=transport)
        self.hosted, self.api_transport, self.sleep = hosted, api_transport, sleep

    def revisions(self, *, fresh=False):
        """Only the embedding model must be present in Ollama; the generator is the hosted model id."""
        with self._probe_lock:
            if fresh or time.monotonic() - self._checked_at > 5:
                try:
                    import asyncio
                    data = asyncio.run(self._metadata())
                    rows = {model_name(m['name']): m['digest'] for m in data['models'] if m.get('digest')}
                    if model_name(self.cfg.embedding) not in rows:
                        raise ValueError('model missing')
                    self._revisions = {self.cfg.embedding: rows[model_name(self.cfg.embedding)]}
                    self._checked_at = time.monotonic()
                except Exception:
                    raise GatewayError('ollama_not_ready') from None
            return {**self._revisions, self.hosted.model: 'hosted'}

    def _budget(self, deadline):
        budget = self.hosted.timeout_s
        if deadline is not None:
            budget = min(budget, (deadline - datetime.now(timezone.utc)).total_seconds())
        if budget <= 0:
            raise GatewayError('ai_timeout_before_dispatch')
        return budget

    def complete(self, task, system, messages, prompt_version, *, deadline=None):
        if task not in TASKS:
            raise GatewayError('model_role_not_configured')
        validate_prompt(system, messages)
        body = {
            'systemInstruction': {'parts': [{'text': system}]},
            'contents': [{'role': 'model' if m['role'] == 'assistant' else 'user', 'parts': [{'text': m['content']}]}
                         for m in messages],
            # Every pipeline task asks for one JSON object.
            'generationConfig': {'responseMimeType': 'application/json', 'maxOutputTokens': self.hosted.max_tokens},
        }
        started = time.monotonic()
        for attempt in range(len(RETRY_DELAYS) + 1):
            budget = self._budget(deadline)
            try:
                with httpx.Client(transport=self.api_transport, trust_env=False,
                                  timeout=httpx.Timeout(budget, connect=min(5, budget))) as client:
                    response = client.post(f'{API}/models/{self.hosted.model}:generateContent', json=body,
                                           headers={'x-goog-api-key': self.hosted.api_key})
            except (httpx.ConnectError, httpx.ConnectTimeout):
                raise GatewayError('hosted_connection_unavailable') from None   # nothing was sent
            except httpx.HTTPError:
                raise ModelCallUncertain('hosted_completion_unknown') from None  # may still be generating
            if response.status_code not in RETRY_STATUS or attempt == len(RETRY_DELAYS):
                break
            delay = RETRY_DELAYS[attempt]
            if deadline is not None and (deadline - datetime.now(timezone.utc)).total_seconds() <= delay + 1:
                break
            self.sleep(delay)
        if not response.is_success:
            # The API answered with an error status (quota, overload, bad request): the call ended.
            raise GatewayError('hosted_request_rejected')
        try:
            data = response.json()
        except ValueError:
            raise GatewayError('hosted_invalid_completed_response') from None
        if (data.get('promptFeedback') or {}).get('blockReason'):
            raise GatewayError('hosted_refused')
        candidates = data.get('candidates') or []
        if not candidates:
            raise GatewayError('hosted_invalid_completed_response')
        first = candidates[0]
        reason = first.get('finishReason')
        if reason in REFUSED:
            raise GatewayError('hosted_refused')
        if reason == 'MAX_TOKENS':
            raise GatewayError('hosted_output_truncated')
        parts = (first.get('content') or {}).get('parts') or []
        # Thought parts are the model's reasoning, not the answer.
        text = ''.join(p.get('text', '') for p in parts if isinstance(p, dict) and not p.get('thought'))
        if not text.strip():
            raise GatewayError('hosted_invalid_completed_response')
        usage = data.get('usageMetadata') or {}

        def count(key):
            value = usage.get(key)
            return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
        served = str(data.get('modelVersion') or self.hosted.model)
        return ModelResult(text, f'{served}@hosted', prompt_version, count('promptTokenCount'),
                           count('candidatesTokenCount'), int((time.monotonic() - started) * 1000), None, False)
