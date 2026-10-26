"""The tutor's "Gợi ý": one hint before the learner answers, never one that gives the answer away.

One model call through the gateway, grounded in the question's own source passages. Code decides
whether the reply may be shown; otherwise the learner gets a pointer to the source, written by code.
The model sees the question and the passages, never who is asking.
"""
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from app import events
from app.chat.pipeline import parse_model_json
from app.chat.retrieval import get_passages
from app.config import settings
from app.engine.hint import pointer, usable
from app.errors import ApiError
from app.gateway import GatewayError
from app.repo import chat as chat_repo
from app.repo import content
from app.repo import exams as exams_repo
from app.repo import practice as practice_repo
from app.repo import units as units_repo
from app.services.responses import require_question

PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "hint_v1.txt"
USER_TEXT = "Gợi ý"


@lru_cache
def _system() -> str:
    return PROMPT.read_text(encoding="utf-8")


def _unavailable(message: str) -> ApiError:
    return ApiError(409, "hint_unavailable", message)


def _user_message(question: dict, passages: list) -> str:
    """The question as the learner sees it: stem and options, nothing that marks the answer."""
    options = "\n".join(f"{o['key']}. {o['text']}" for o in question["options"])
    sources = "\n\n".join(f"[{p.id}] ({p.document_title})\n{p.text}" for p in passages)
    return f"Câu hỏi: {question['stem']}\nCác phương án:\n{options}\n\nPassages:\n{sources}"


def hint(conn, gateway, learner: dict, question_id: str, now: datetime) -> dict:
    question = require_question(conn, question_id)
    if exams_repo.in_running_attempt(conn, learner["id"], question_id, now):
        raise _unavailable("Không có gợi ý trong khi làm bài thi.")
    if not (units_repo.awaiting_answer(conn, learner["id"], question_id)
            or practice_repo.awaiting_answer(conn, learner["id"], question_id)):
        raise _unavailable("Gợi ý chỉ có trước khi bạn trả lời câu hỏi.")

    citations = content.citations_for(conn, question["source_passage_ids"])
    by_id = get_passages(conn, question["source_passage_ids"])
    passages = [by_id[pid] for pid in question["source_passage_ids"] if pid in by_id]

    text, result = None, None
    if passages:
        try:
            result = gateway.complete("hint", _system(), [{"role": "user", "content": _user_message(question, passages)}],
                                      settings()["prompt_versions"]["hint"])
            reply = parse_model_json(result.text) or {}
            if usable(reply.get("hint"), question["options"], question["stem"]):
                text = reply["hint"].strip()
        except GatewayError:
            pass        # the model could not be reached: the pointer below is the answer
    from_model = text is not None
    if not from_model:
        text = pointer(citations[0]) if citations else "Hãy đọc lại kỹ câu hỏi và từng phương án."

    # Logged like the tutor's other turns: outside the chat list, with what produced it.
    title = f"Gia sư · {question_id}"
    session = chat_repo.tutor_session(conn, learner["pseudonym_id"], title)
    session_id = session["id"] if session else chat_repo.create_session(
        conn, learner["pseudonym_id"], now, title=title, kind="tutor", question_id=question_id)
    chat_repo.add_message(conn, session_id, "user", USER_TEXT, now)
    chat_repo.add_message(
        conn, session_id, "assistant", text, now, state="answered" if from_model else "insufficient_evidence",
        answer_format="text", citations=citations, retrieved_passage_ids=[p.id for p in passages],
        model_version=result.model if result else None, prompt_version=settings()["prompt_versions"]["hint"],
        corpus_version=settings()["corpus_version"], latency_ms=result.latency_ms if result else None,
        tokens_in=result.tokens_in if result else None, tokens_out=result.tokens_out if result else None,
        cost=result.cost if result else None)
    events.record(conn, learner["pseudonym_id"], "chat_turn", now, ref_type="tutor_session", ref_id=session_id)
    return {"text": text, "citations": citations, "generated": from_model}
