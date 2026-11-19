"""Dev/test only: generation on the Anthropic API, embeddings still on local Ollama (bge-m3, CPU).

This is a stand-in until the project GPU serves the generator. It keeps the Ollama port's rules:
every call goes through the turn's reservation, the prompt is checked for identifiers first, there
is no transport retry, and a call whose outcome is unknown (timeout, dropped connection) is reported
as uncertain so the reservation stays quarantined. Learner text reaches a cloud model here, so the
provider is refused outside APP_ENV=dev/test (phase_config) and is meant for demo/synthetic learners.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import time

import anthropic
from dotenv import dotenv_values

from app.config import BACKEND_DIR
from app.gateway import GatewayError, ModelResult
from app.ollama_gateway import ModelCallUncertain, OllamaConfig, OllamaGateway, model_name
from app.privacy import validate_prompt

TASKS = ('answer', 'tutor', 'hint', 'quiz_chat', 'check', 'render')
EFFORTS = ('low', 'medium', 'high', 'xhigh', 'max')
# A policy decline is re-run on a model the API picks for that category, inside the same call.
FALLBACK_BETA = 'server-side-fallback-2026-07-01'


@dataclass(frozen=True)
class AnthropicConfig:
    model: str
    effort: str
    max_tokens: int
    timeout_s: float

    @classmethod
    def load(cls, path: Path | None = None):
        values = {**dotenv_values(path or BACKEND_DIR / '.env'), **os.environ}
        if not str(values.get('ANTHROPIC_API_KEY') or '').strip():
            raise RuntimeError('Set ANTHROPIC_API_KEY in backend/.env for the anthropic provider')
        model = str(values.get('YHDP_ANTHROPIC_MODEL') or 'claude-opus-5-5').strip()
        effort = str(values.get('YHDP_ANTHROPIC_EFFORT') or 'medium').strip()
        max_tokens = int(values.get('YHDP_ANTHROPIC_MAX_TOKENS', 16000))
        timeout = float(values.get('YHDP_ANTHROPIC_TIMEOUT_SECONDS', 120))
        if effort not in EFFORTS or not 1 <= max_tokens <= 64000 or not 0 < timeout <= 300 or not math.isfinite(timeout):
            raise RuntimeError('Invalid Anthropic effort/max_tokens/timeout')
        return cls(model, effort, max_tokens, timeout)


class HostedGateway(OllamaGateway):
    """complete() on the Anthropic API; embed(), revisions of the embedding model and index jobs
    are inherited from the Ollama port unchanged."""
    resource = 'hosted:shared'

    def __init__(self, cfg: OllamaConfig, hosted: AnthropicConfig, client=None, transport=None):
        super().__init__(cfg, transport=transport)
        self.hosted = hosted
        # max_retries=0: a retry could run the same generation twice. The key comes from the environment.
        self.client = client or anthropic.Anthropic(max_retries=0, timeout=hosted.timeout_s)

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
        budget = self._budget(deadline)
        started = time.monotonic()
        # Claude Haiku has no server-side fallback: a decline there stays a decline, so none is asked for.
        fallback = {} if self.hosted.model.startswith('claude-haiku') else {'betas': [FALLBACK_BETA], 'fallbacks': 'default'}
        try:
            response = self.client.with_options(timeout=budget).beta.messages.create(
                model=self.hosted.model, max_tokens=self.hosted.max_tokens, system=system, messages=messages,
                output_config={'effort': self.hosted.effort}, **fallback)
        except (anthropic.APITimeoutError, anthropic.APIConnectionError):
            # The request may have reached the API and still be generating.
            raise ModelCallUncertain('hosted_completion_unknown') from None
        except anthropic.APIStatusError:
            # The API answered with an error status: the call ended, nothing is still running.
            raise GatewayError('hosted_request_rejected') from None
        if response.stop_reason == 'refusal':
            raise GatewayError('hosted_refused')
        if response.stop_reason == 'max_tokens':
            raise GatewayError('hosted_output_truncated')
        text = ''.join(block.text for block in response.content if getattr(block, 'type', None) == 'text')
        if not text.strip():
            raise GatewayError('hosted_invalid_completed_response')
        usage = response.usage
        return ModelResult(text, f'{response.model}@hosted', prompt_version,
                           getattr(usage, 'input_tokens', None), getattr(usage, 'output_tokens', None),
                           int((time.monotonic() - started) * 1000), None, False)
