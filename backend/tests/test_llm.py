import json

import httpx
import numpy as np
import pytest
from pydantic import BaseModel

from yhdp.llm import LLMError, Ollama


class Answer(BaseModel):
    van_de: int
    confidence: float


def client(handler, tmp_path):
    return Ollama(base_url="http://ollama", transport=httpx.MockTransport(handler),
                  log_dir=tmp_path / "log")


def chat_reply(content: str) -> httpx.Response:
    return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})


def test_chat_returns_text_and_logs(tmp_path):
    llm = client(lambda req: chat_reply("Hà Nội"), tmp_path)
    assert llm.chat([{"role": "user", "content": "?"}]) == "Hà Nội"
    (log,) = (tmp_path / "log").iterdir()
    assert json.loads(log.read_text())["output"] == "Hà Nội"


def test_schema_retry_sends_error_back(tmp_path):
    seen = []

    def handler(req):
        body = json.loads(req.content)
        seen.append(body)
        return chat_reply('{"van_de": "x"}' if len(seen) == 1 else '{"van_de": 3, "confidence": 0.9}')

    out = client(handler, tmp_path).chat([{"role": "user", "content": "tag"}], schema=Answer)
    assert out == Answer(van_de=3, confidence=0.9)
    assert seen[0]["format"]["title"] == "Answer"
    assert seen[1]["messages"][-1]["role"] == "user" and "không hợp lệ" in seen[1]["messages"][-1]["content"]


def test_schema_gives_up_after_retries(tmp_path):
    calls = []

    def handler(req):
        calls.append(1)
        return chat_reply("not json")

    with pytest.raises(LLMError, match="after 3 tries"):
        client(handler, tmp_path).chat([{"role": "user", "content": "x"}], schema=Answer)
    assert len(calls) == 3


def test_timeout_is_llm_error(tmp_path):
    def handler(req):
        raise httpx.ReadTimeout("slow", request=req)

    with pytest.raises(LLMError, match="timed out"):
        client(handler, tmp_path).chat([{"role": "user", "content": "x"}])


def test_stream_yields_pieces(tmp_path):
    lines = [{"message": {"content": "Sốt "}}, {"message": {"content": "xuất huyết"}},
             {"message": {"content": ""}, "done": True}]
    body = "\n".join(json.dumps(x) for x in lines)
    llm = client(lambda req: httpx.Response(200, text=body), tmp_path)
    assert "".join(llm.stream([{"role": "user", "content": "x"}])) == "Sốt xuất huyết"


def test_embed_batches_and_normalizes(tmp_path):
    def handler(req):
        n = len(json.loads(req.content)["input"])
        return httpx.Response(200, json={"embeddings": [[3.0, 4.0]] * n})

    vecs = client(handler, tmp_path).embed(["a", "b", "c"], batch=2)
    assert vecs.shape == (3, 2)
    assert np.allclose(vecs[0], [0.6, 0.8])
