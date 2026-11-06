"""Thin Ollama client: chat (optionally JSON-schema constrained, validated by Pydantic),
streaming chat, and normalized embeddings. Every non-streamed call is logged to
data/derived/_llm_log/<date>.jsonl for debugging prompts.
"""

import hashlib
import json
import time
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import httpx
import numpy as np
from pydantic import BaseModel, ValidationError

from yhdp.settings import settings


class LLMError(RuntimeError):
    pass


class Ollama:
    def __init__(self, base_url: str | None = None, transport: httpx.BaseTransport | None = None,
                 log_dir: Path | None = None, timeout: float = 300):
        self.http = httpx.Client(base_url=base_url or settings.ollama_url, transport=transport,
                                 timeout=timeout)
        self.log_dir = log_dir if log_dir is not None else settings.derived_dir / "_llm_log"

    def close(self) -> None:
        self.http.close()

    def _post(self, path: str, body: dict) -> dict:
        try:
            r = self.http.post(path, json=body)
            r.raise_for_status()
            return r.json()
        except httpx.TimeoutException as e:
            raise LLMError(f"Ollama timed out on {path}") from e
        except httpx.HTTPError as e:
            raise LLMError(f"Ollama request failed on {path}: {e}. Is `ollama serve` running?") from e

    def _log(self, record: dict) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        with open(self.log_dir / f"{date.today()}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _chat_body(self, messages, model, temperature, think, stream, options=None) -> dict:
        return {"model": model or settings.llm_model, "messages": messages, "stream": stream,
                "think": think, "options": {"temperature": temperature,
                                            "num_ctx": settings.llm_num_ctx, **(options or {})}}

    def chat[T: BaseModel](self, messages: list[dict], schema: type[T] | None = None,
                           model: str | None = None, temperature: float = 0.2,
                           think: bool = False, retries: int = 2,
                           options: dict | None = None) -> T | str:
        """Return the reply text, or a validated `schema` instance. Invalid JSON is sent back
        to the model with the validation error, up to `retries` times."""
        messages = list(messages)
        for attempt in range(retries + 1):
            body = self._chat_body(messages, model, temperature, think, stream=False,
                                   options=options)
            if schema is not None:
                body["format"] = schema.model_json_schema()
            t0 = time.monotonic()
            content = self._post("/api/chat", body)["message"]["content"]
            self._log({"model": body["model"], "messages": _compact(messages), "schema": schema and
                       schema.__name__, "output": content, "seconds": round(time.monotonic() - t0, 2)})
            if schema is None:
                return content
            try:
                return schema.model_validate_json(content)
            except ValidationError as e:
                if attempt == retries:
                    raise LLMError(f"invalid {schema.__name__} after {retries + 1} tries: {e}") from e
                messages += [{"role": "assistant", "content": content},
                             {"role": "user", "content": f"Kết quả không hợp lệ: {e}\n"
                              "Trả lại JSON đúng schema."}]
        raise AssertionError("unreachable")

    def stream(self, messages: list[dict], model: str | None = None, temperature: float = 0.2,
               think: bool = False) -> Iterator[str]:
        for piece in self.stream_events(messages, model=model, temperature=temperature,
                                        think=think):
            if isinstance(piece, str):
                yield piece

    def stream_events(self, messages: list[dict], tools: list[dict] | None = None,
                      model: str | None = None, temperature: float = 0.2,
                      think: bool = False) -> Iterator[str | dict]:
        """Reply text as it arrives, and each tool call the model makes as
        {"name": ..., "arguments": {...}}."""
        body = self._chat_body(messages, model, temperature, think, stream=True)
        if tools:
            body["tools"] = tools
        try:
            with self.http.stream("POST", "/api/chat", json=body) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    message = json.loads(line)["message"]
                    if piece := message.get("content"):
                        yield piece
                    for call in message.get("tool_calls") or []:
                        fn = call["function"]
                        args = fn.get("arguments") or {}
                        yield {"name": fn["name"],
                               "arguments": json.loads(args) if isinstance(args, str) else args}
        except httpx.HTTPError as e:
            raise LLMError(f"Ollama stream failed: {e}. Is `ollama serve` running?") from e

    def embed(self, texts: list[str], model: str | None = None, batch: int = 32) -> np.ndarray:
        """L2-normalized float32 embeddings, shape (len(texts), dim)."""
        vecs = []
        for i in range(0, len(texts), batch):
            out = self._post("/api/embed", {"model": model or settings.embed_model,
                                             "input": texts[i:i + batch]})
            vecs.extend(out["embeddings"])
        arr = np.asarray(vecs, dtype=np.float32).reshape(len(texts), -1)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        return arr / np.where(norms == 0, 1, norms)


def _compact(messages: list[dict]) -> list[dict]:
    """Long system prompts (the tagger's ~6k-token rubric) are logged by hash only."""
    return [{**m, "content": "sha1:" + hashlib.sha1(m["content"].encode()).hexdigest()}
            if m["role"] == "system" and len(m["content"]) > 2000 else m for m in messages]
