"""Offline Alpha gateway. Only rehearsed questions receive a quoted, checked answer.

There is no network client here. Retrieval, pre-gates, post-checks, persistence and SSE
remain the real pipeline. The fixture cannot cite a passage absent from the prompt.
"""
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from app.config import require_dev_env
from app.gateway import ModelResult

SCENARIOS = Path(__file__).with_name("scripted_scenarios.json")


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFC", text).casefold()
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


@lru_cache
def scenarios() -> list[dict]:
    return json.loads(SCENARIOS.read_text(encoding="utf-8"))


class ScriptedGateway:
    def __init__(self):
        require_dev_env("ScriptedGateway")

    def complete(self, task: str, system: str, messages: list[dict], prompt_version: str) -> ModelResult:
        require_dev_env("ScriptedGateway")
        prompt = messages[-1]["content"]
        question = prompt.split("\n", 1)[0].removeprefix("Câu hỏi: ")
        if task == "quiz_chat":
            question = prompt.partition("Câu hỏi của học viên: ")[2].split("\n", 1)[0]
        sources = prompt.partition("Passages:\n")[2]
        payload = {"insufficient": True}
        if task == "hint":
            # No numbers or option text: the existing hint guard still makes the final decision.
            payload = {"hint": "Hãy xác định đối tượng và khoảng thời gian được nói đến trong câu hỏi, rồi đối chiếu với nguồn."}
        elif task in ("answer", "tutor", "quiz_chat"):
            for scenario in scenarios():
                matches = task == "tutor" or normalise(question) in {
                    normalise(q) for q in scenario["questions"]
                }
                pid, quote = scenario["passage_id"], scenario["quote"]
                block = re.search(r"(?:^|\n\n)\[" + re.escape(pid) + r"\] [^\n]*\n(.*?)(?=\n\n\[|\Z)", sources, re.S)
                if matches and block and " ".join(quote.split()) in " ".join(block[1].split()):
                    payload = {"evidence": [{"passage_id": pid, "quote": quote}],
                               "claims": [{"text": quote, "passage_ids": [pid]}]}
                    break
        return ModelResult(text=json.dumps(payload, ensure_ascii=False), model="scripted-alpha-v1",
                           prompt_version=prompt_version, tokens_in=0, tokens_out=0,
                           latency_ms=0, cost=0.0, from_cache=False)
