"""Ollama wire protocol adapted from YHDP c661586, with no prompt logs/replay/retries.

Transport failures after dispatch are deliberately different from acknowledged errors:
the server may still be generating after a local deadline or disconnected socket.
"""
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit

import httpx
from dotenv import dotenv_values
from app.config import BACKEND_DIR
from app.gateway import GatewayError, ModelResult
from app.privacy import clean, validate_prompt


class ModelCallUncertain(GatewayError):
    """A dispatched call has no trustworthy completion acknowledgement."""


def model_name(value):
    """Ollama's omitted tag is latest, including names with a registry port."""
    return value if ':' in value.rsplit('/', 1)[-1] else value + ':latest'


@dataclass(frozen=True)
class OllamaConfig:
    url: str
    generator: str
    embedding: str
    context: int
    timeout_s: float

    @classmethod
    def load(cls, path: Path | None = None):
        # Read only inside Chat. Never export model variables to the process environment.
        values = {**dotenv_values(path or BACKEND_DIR / '.env'), **os.environ}
        url = str(values.get('YHDP_OLLAMA_URL') or '').rstrip('/')
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:
            raise RuntimeError('YHDP_OLLAMA_URL must be an HTTP origin without credentials')
        models = [str(values.get(k) or '').strip() for k in ('YHDP_LLM_MODEL', 'YHDP_EMBED_MODEL')]
        if not all(models):
            raise RuntimeError('Set YHDP_LLM_MODEL and YHDP_EMBED_MODEL explicitly')
        context = int(values.get('YHDP_LLM_NUM_CTX', 16384))
        timeout = float(values.get('YHDP_OLLAMA_TIMEOUT_SECONDS', 300))
        if context < 1 or not 0 < timeout <= 300 or not math.isfinite(timeout):
            raise RuntimeError('Invalid Ollama context/timeout')
        return cls(url, *models, context, timeout)


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    model: str
    revision: str
    latency_ms: int


class OllamaGateway:
    resource = 'ollama:shared'  # Both selected models share this application's dev budget.

    def __init__(self, cfg: OllamaConfig, transport=None):
        self.cfg, self.transport = cfg, transport
        self._revisions, self._checked_at = {}, 0.0
        self._probe_lock = threading.Lock()

    async def _metadata(self):
        async with httpx.AsyncClient(base_url=self.cfg.url, transport=self.transport,
                                     timeout=2, trust_env=False) as client:
            async with asyncio.timeout(3):
                response = await client.get('/api/tags')
                response.raise_for_status()
                return response.json()

    def revisions(self, *, fresh=False):
        with self._probe_lock:
            if fresh or time.monotonic() - self._checked_at > 5:
                try:
                    data = asyncio.run(self._metadata())
                    rows = {model_name(m['name']): m['digest'] for m in data['models'] if m.get('digest')}
                    wanted = (self.cfg.generator, self.cfg.embedding)
                    if any(model_name(m) not in rows for m in wanted):
                        raise ValueError('model missing')
                    self._revisions = {m: rows[model_name(m)] for m in wanted}
                    self._checked_at = time.monotonic()
                except Exception:
                    raise GatewayError('ollama_not_ready') from None
            return dict(self._revisions)

    async def _request(self, path, body, budget):
        try:
            async with asyncio.timeout(budget):
                async with httpx.AsyncClient(base_url=self.cfg.url, transport=self.transport,
                                             trust_env=False, timeout=httpx.Timeout(budget, connect=min(3, budget))) as client:
                    response = await client.post(path, json=body)
                    if response.status_code in (400, 401, 403, 404, 405, 413, 422, 429):
                        raise GatewayError('ollama_request_rejected')
                    if not response.is_success:
                        raise ModelCallUncertain('ollama_completion_unknown')
                    try:
                        data = response.json()
                    except ValueError:
                        raise ModelCallUncertain('ollama_completion_unknown') from None
                    if not isinstance(data, dict):
                        raise ModelCallUncertain('ollama_completion_unknown')
                    if path == '/api/chat' and data.get('done') is not True:
                        raise ModelCallUncertain('ollama_completion_unknown')
                    if path == '/api/embed' and not isinstance(data.get('embeddings'), list):
                        raise ModelCallUncertain('ollama_completion_unknown')
                    return data
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise GatewayError('ollama_connection_unavailable') from None
        except (httpx.HTTPError, TimeoutError):
            raise ModelCallUncertain('ollama_completion_unknown') from None
        except GatewayError:
            raise
        except Exception:
            raise ModelCallUncertain('ollama_completion_unknown') from None

    def _call(self, path, body, deadline):
        budget = self.cfg.timeout_s
        if deadline is not None:
            budget = min(budget, (deadline - datetime.now(timezone.utc)).total_seconds())
        if budget <= 0:
            raise GatewayError('ai_timeout_before_dispatch')
        return asyncio.run(self._request(path, body, budget))

    def complete(self, task, system, messages, prompt_version, *, deadline=None):
        if task not in ('answer', 'tutor', 'hint', 'quiz_chat'):
            raise GatewayError('model_role_not_configured')
        validate_prompt(system, messages)
        revision = self.revisions(fresh=True)[self.cfg.generator]
        body = {'model': self.cfg.generator, 'stream': False, 'think': False,
                'messages': [{'role': 'system', 'content': system}, *messages],
                'format': 'json', 'options': {'temperature': .2, 'num_ctx': self.cfg.context}}
        started = time.monotonic()
        data = self._call('/api/chat', body, deadline)
        if data.get('model') is not None and model_name(str(data['model'])) != model_name(self.cfg.generator):
            raise GatewayError('ollama_response_model_mismatch')
        text = data.get('message', {}).get('content') if isinstance(data.get('message'), dict) else None
        if not isinstance(text, str):
            raise GatewayError('ollama_invalid_completed_response')
        def count(key):
            value = data.get(key)
            return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
        return ModelResult(text, f'{self.cfg.generator}@{revision}', prompt_version,
                           count('prompt_eval_count'), count('eval_count'),
                           int((time.monotonic() - started) * 1000), None, False)

    def embed(self, texts, *, deadline=None):
        if not texts or len(texts) > 32 or any(not isinstance(t, str) or not t.strip() or clean(t) != t for t in texts):
            raise GatewayError('embedding_payload_blocked')
        revision = self.revisions(fresh=True)[self.cfg.embedding]
        started = time.monotonic()
        data = self._call('/api/embed', {'model': self.cfg.embedding, 'input': texts, 'truncate': False}, deadline)
        if data.get('model') is not None and model_name(str(data['model'])) != model_name(self.cfg.embedding):
            raise GatewayError('ollama_response_model_mismatch')
        vectors = data['embeddings']
        if len(vectors) != len(texts):
            raise GatewayError('embedding_shape_invalid')
        normalised, dimension = [], None
        for vector in vectors:
            if not isinstance(vector, list) or not vector or any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in vector):
                raise GatewayError('embedding_shape_invalid')
            dimension = dimension or len(vector)
            norm = math.sqrt(sum(v * v for v in vector))
            if len(vector) != dimension or not norm or not math.isfinite(norm):
                raise GatewayError('embedding_shape_invalid')
            normalised.append([v / norm for v in vector])
        return EmbeddingResult(normalised, self.cfg.embedding, revision, int((time.monotonic() - started) * 1000))
