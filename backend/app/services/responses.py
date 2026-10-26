"""The single path for a scored answer: the response row, Elo, the rule-built card, the activity log.

Unit quizzes, practice sets, the diagnostic and mock exams all record through `record_response`, so
mastery and cards cannot drift between them.
"""
from dataclasses import dataclass
from datetime import datetime

from app import events
from app.config import settings
from app.engine import elo
from app.engine.cards import card_text, citation_for
from app.engine.priority import TopicState, rank_topics
from app.engine.scheduler import new_state
from app.errors import ApiError
from app.repo import cards as cards_repo
from app.repo import content
from app.repo import responses as repo

# Answers in these contexts are logged one by one. An exam is logged once, when it is handed in.
_EVENT_KIND = {"unit": "unit_response", "practice": "practice_response"}


@dataclass(frozen=True)
class ResponseResult:
    correct: bool
    card_id: int | None


def require_question(conn, question_id: str) -> dict:
    """The approved version of a question, or 404."""
    question = content.approved_question(conn, question_id)
    if question is None:
        raise ApiError(404, "question_not_found", "Không tìm thấy câu hỏi.")
    return question


def record_response(conn, learner: dict, question: dict, chosen: str | None, context: str, now: datetime, *,
                    attempt_id: int | None = None, unit_session_id: int | None = None,
                    unit_item_id: str | None = None, practice_set_id: int | None = None,
                    time_ms: int | None = None) -> ResponseResult:
    correct = any(o["key"] == chosen and o["is_correct"] for o in question["options"])
    response_id = repo.insert(conn, learner["id"], question, context, chosen, correct, now, attempt_id=attempt_id,
                              unit_session_id=unit_session_id, unit_item_id=unit_item_id,
                              practice_set_id=practice_set_id, time_ms=time_ms)

    code = question["competency_code"]
    m = repo.mastery(conn, learner["id"], code)
    update = elo.update(m["theta"], question["difficulty_b"], correct, m["n_responses"], question["n_responses"],
                        settings()["elo"])
    repo.set_mastery(conn, learner["id"], code, update.theta, now)
    repo.set_difficulty(conn, question["id"], question["version"], update.b)

    if context in _EVENT_KIND:
        events.record(conn, learner["pseudonym_id"], _EVENT_KIND[context], now, duration_ms=time_ms,
                      ref_type="question", ref_id=question["id"])

    card_id = None if correct else _create_card(conn, learner, question, context, now)
    if card_id is not None:
        repo.link_card(conn, response_id, card_id)
        events.record(conn, learner["pseudonym_id"], "cards_created", now, ref_type="card", ref_id=card_id)
    return ResponseResult(correct=correct, card_id=card_id)


def _create_card(conn, learner: dict, question: dict, context: str, now: datetime) -> int | None:
    """The card rule: a wrong answer makes one card per learner and question, from the question's own text."""
    front, back = card_text(question)
    source = content.passage_source(conn, question["source_passage_ids"][0])
    return cards_repo.create(conn, learner["id"], question["id"], context, front, back,
                             citation_for(source, source["title"]), new_state(now), now)


def topic_states(conn, learner_id: int) -> list[TopicState]:
    """Every topic with the learner's mastery of it; None until enough answers make it meaningful."""
    rows = repo.mastery_rows(conn, learner_id)
    minimum = settings()["mastery"]["min_responses"]
    out = []
    for t in content.topics(conn):
        row = rows.get(t["code"])
        assessed = row is not None and elo.is_assessed(row["n_responses"], minimum)
        out.append(TopicState(t["code"], t["name"], t["weight"], t["module_id"],
                              elo.mastery_of(row["theta"]) if assessed else None))
    return out


def ranking(conn, learner: dict) -> list[str]:
    """Topic codes in the order the learner should work on them."""
    return rank_topics(topic_states(conn, learner["id"]), learner["focus_module_ids"],
                       settings()["priority"]["neutral_mastery"])


def topic_names(conn) -> dict[str, str]:
    return {t["code"]: t["name"] for t in content.topics(conn)}
