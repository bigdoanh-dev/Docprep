"""Model gateway: the ONLY module that calls a model.

Picks the model per task from config, carries the prompt version, applies the timeout,
records tokens/cost/latency, and keeps a replay cache of every reply. Switching provider or
model is a config change.

Replay modes (env DEMO_REPLAY):
  off / 0    always call the model
  1          call the model; if the call fails, serve the cached reply for the same prompt
  prefer     serve the cached reply when there is one, call the model only for a new prompt.
             Use this on stage: a rehearsed question gives exactly the rehearsed answer.
"""
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Protocol

import anthropic


@dataclass
class ModelResult:
    text: str
    model: str
    prompt_version: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cost: float | None
    from_cache: bool


class GatewayError(Exception):
    pass


def replay_mode(value: str | bool | None) -> str:
    """Normalise DEMO_REPLAY (or a bool) to "off", "fallback" or "prefer"."""
    if value is True or value == "1":
        return "fallback"
    if isinstance(value, str) and value.lower() == "prefer":
        return "prefer"
    return "off"


class Gateway(Protocol):
    def complete(self, task: str, system: str, messages: list[dict], prompt_version: str) -> ModelResult: ...


class AnthropicGateway:
    def __init__(self, cfg: dict, api_key: str | None, replay: bool | str, cache_dir: Path, client=None):
        self.cfg, self.replay, self.cache_dir = cfg, replay_mode(replay), Path(cache_dir)
        self.client = client or anthropic.Anthropic(
            api_key=api_key or None, timeout=float(cfg["timeout_s"]), max_retries=cfg.get("max_retries", 0))

    def _cache_file(self, model: str, prompt_version: str, system: str, messages: list[dict]) -> Path:
        key = json.dumps([model, prompt_version, system, messages], ensure_ascii=False, sort_keys=True)
        return self.cache_dir / (hashlib.sha256(key.encode("utf-8")).hexdigest() + ".json")

    @staticmethod
    def _read_cache(cache_file: Path) -> ModelResult | None:
        """The cached reply, or None when there is none or the file cannot be used."""
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            return ModelResult(**{**cached, "from_cache": True})
        except (OSError, ValueError, TypeError):
            return None

    def _cost(self, model: str, tokens_in: int, tokens_out: int) -> float | None:
        price = (self.cfg.get("price_per_mtok") or {}).get(model)
        if not price:
            return None
        return (tokens_in * price["in"] + tokens_out * price["out"]) / 1_000_000

    def complete(self, task: str, system: str, messages: list[dict], prompt_version: str) -> ModelResult:
        spec = self.cfg["models"][task]
        model = spec["id"]
        cache_file = self._cache_file(model, prompt_version, system, messages)
        params = {"model": model, "max_tokens": self.cfg["max_tokens"], "system": system, "messages": messages}
        if spec.get("effort"):
            params["output_config"] = {"effort": spec["effort"]}

        if self.replay == "prefer":
            cached = self._read_cache(cache_file)
            if cached:
                return cached

        started = time.monotonic()
        try:
            resp = self.client.messages.create(**params)
            if resp.stop_reason == "refusal":
                raise GatewayError("model declined the request")
            if resp.stop_reason == "max_tokens":
                raise GatewayError("model output was cut off at max_tokens")
        except GatewayError:
            raise
        except Exception as e:
            # Any failed call (HTTP status, timeout, dead network, missing credentials) is handled
            # the same way at this boundary: replay if allowed, otherwise one GatewayError.
            cached = self._read_cache(cache_file) if self.replay != "off" else None
            if cached:
                return cached
            raise GatewayError(f"model call failed: {type(e).__name__}") from e

        text = "".join(b.text for b in resp.content if b.type == "text")
        result = ModelResult(
            text=text, model=model, prompt_version=prompt_version,
            tokens_in=resp.usage.input_tokens, tokens_out=resp.usage.output_tokens,
            latency_ms=int((time.monotonic() - started) * 1000),
            cost=self._cost(model, resp.usage.input_tokens, resp.usage.output_tokens), from_cache=False)
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(asdict(result), ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass  # the cache is a convenience; failing to write it must not lose the answer
        return result


class FakeGateway:
    """Scripted gateway for tests: a list of texts, or a function (task, messages) -> text."""

    def __init__(self, responses: list[str] | Callable[[str, list[dict]], str]):
        self.responses = responses
        self.calls: list[dict] = []

    def complete(self, task: str, system: str, messages: list[dict], prompt_version: str) -> ModelResult:
        self.calls.append({"task": task, "system": system, "messages": messages, "prompt_version": prompt_version})
        text = self.responses(task, messages) if callable(self.responses) else self.responses[len(self.calls) - 1]
        return ModelResult(text=text, model="fake", prompt_version=prompt_version, tokens_in=0, tokens_out=0,
                           latency_ms=0, cost=None, from_cache=False)
