"""Practice sets: a few approved questions on one competency.

The daily session's step 2 builds one; an accepted chat suggestion and "Làm câu tương tự" will too.
All of them are served, graded and finished here, and every answer goes through `record_response`.
Whatever the learner reads here (why this question, the example, the summary) is true at the moment
it is shown, or it is left out.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from app import events
from app.config import settings
from app.engine.shuffle import option_order
from app.engine.adaptation import summarise
from app.engine.session import Seen, item_reason, pick_items, topic_reason, weak_spots
from app.errors import ApiError
from app.repo import content
from app.repo import practice as repo
from app.repo import sessions as sessions_repo
from app.services.account import local_date
from app.services.responses import record_response, topic_names
from app.services.session_progress import step_completed


@dataclass(frozen=True)
class Choice:
    """What a practice step would be about right now."""
    competency_code: str
    wrong: int               # the learner's wrong answers on it in the window
    added_from_chat: bool


def _eligible(conn, learner: dict, competency_code: str, now: datetime, without_set: int | None,
              limit: int | None = None) -> tuple[list[str], dict]:
    cfg = settings()["session"]
    candidates = repo.seen(conn, learner["id"], competency_code, without_set, synthetic=learner["is_synthetic"])
    question_ids = pick_items([Seen(c["question_id"], c["last_seen"]) for c in candidates], now,
                              cfg["seen_window_days"], limit or cfg["practice_items"])
    return question_ids, {c["question_id"]: c["version"] for c in candidates if c["question_id"] in question_ids}


def eligible(conn, learner: dict, competency_code: str, now: datetime) -> list[str]:
    """The approved questions of the competency that a set built now would ask."""
    return _eligible(conn, learner, competency_code, now, None)[0]


def choose_topic(conn, learner: dict, now: datetime, *, pinned: str | None = None,
                 without_set: int | None = None) -> Choice | None:
    """The topic to practise: the one the learner pinned from chat, else the weak spots from the
    worst down, taking the first that has a question the learner has not met lately. None when there
    is nothing to ask. `without_set` answers the question as if that set had never been answered."""
    cfg = settings()["session"]
    wrong_by_code = repo.wrong_counts(conn, learner["id"], now - timedelta(days=cfg["wrong_window_days"]), without_set)
    weights = {t["code"]: t["weight"] for t in content.topics(conn)}
    order = ([pinned] if pinned else []) + [code for code in weak_spots(wrong_by_code, weights) if code != pinned]
    for code in order:
        if _eligible(conn, learner, code, now, without_set)[0]:
            return Choice(code, wrong_by_code.get(code, 0), code == pinned)
    return None


def build(conn, learner: dict, source: str, competency_code: str, wrong: int, added_from_chat: bool,
          now: datetime, limit: int | None = None) -> dict | None:
    """Choose the questions and store the set with the version of each. None, and nothing stored,
    when the learner has met every question of the competency lately or there is none. `limit` is
    the most questions to take (the session's own size when not given)."""
    question_ids, versions = _eligible(conn, learner, competency_code, now, None, limit)
    if not question_ids:
        return None
    why = topic_reason(topic_names(conn)[competency_code], wrong, added_from_chat, settings()["session"])
    practice_set = repo.create(conn, learner["id"], source, competency_code, question_ids, versions,
                               {question_id: why for question_id in question_ids}, now)
    events.record(conn, learner["pseudonym_id"], "practice_set_built", now, ref_type="practice_set",
                  ref_id=practice_set["id"])
    return practice_set


def _own_set(conn, learner: dict, set_id: int, lock: bool = False) -> dict:
    practice_set = repo.own_set(conn, learner["id"], set_id, lock)
    if practice_set is None:
        raise ApiError(404, "set_not_found", "Không tìm thấy bài luyện.")
    return practice_set


def _question(conn, practice_set: dict, question_id: str) -> dict:
    """The question in the version the set was built with."""
    return content.question_as_served(conn, question_id, practice_set["question_versions"].get(question_id))


def _asked(conn, practice_set: dict, answered: dict[str, dict]) -> list[str]:
    """The questions the set still stands for: those already answered, and those not yet answered
    that are still in the bank. A set has no deadline, so a question withdrawn since (retired with no
    approved version) is not asked any more; one that was only edited is asked as it was built."""
    return [question_id for question_id in practice_set["question_ids"]
            if question_id in answered or content.approved_question(conn, question_id) is not None]


def _example(conn, practice_set: dict, question: dict, response: dict, answered: dict[str, dict]) -> dict | None:
    """The worked example after a wrong answer. The one written for this question is tied to the
    learner's choice. The topic's general example is offered once per set, after its first wrong
    answer, and says that it is general."""
    if response["correct"]:
        return None
    example = content.remediation_for(conn, question["id"], practice_set["competency_code"])
    if example is None:
        return None
    if example["specific"]:
        chosen_text = next((o["text"] for o in question["options"] if o["key"] == response["chosen"]), "")
        reason = f"Được thêm vì bạn chọn {chosen_text}"
    else:
        first_wrong = min(r["id"] for r in answered.values() if not r["correct"])
        if response["id"] != first_wrong:
            return None
        reason = "Ví dụ chung của chủ đề này"
    return {"title": example["title"], "body": example["body"],
            "citations": content.citations_for(conn, example["source_passage_ids"]), "reason": reason}


def _feedback(conn, practice_set: dict, question: dict, response: dict, answered: dict[str, dict], asked: list[str]) -> dict:
    """Built from the stored answers alone, so the first reply and any repeat of it are the same."""
    # "done" belongs to the answer that left nothing unanswered: the last one recorded, once all are in.
    is_last = len(answered) == len(asked) and response["id"] == max(r["id"] for r in answered.values())
    return {
        "correct": response["correct"],
        "correct_key": next(o["key"] for o in question["options"] if o["is_correct"]),
        "explanation": question["explanation"],
        "rationales": {o["key"]: o["rationale"] for o in question["options"]},
        "citations": content.citations_for(conn, question["source_passage_ids"]),
        "next": {"kind": "done" if is_last else "same_type"},
        "card_created": response["card_id"] is not None,
        "remediation": _example(conn, practice_set, question, response, answered),
    }


def view(conn, learner: dict, set_id: int) -> dict:
    practice_set = _own_set(conn, learner, set_id)
    answered = repo.responses(conn, set_id)
    asked = _asked(conn, practice_set, answered)
    # "you have not met this question lately" is said only while it is still true
    met_since = repo.answered_since(conn, learner["id"], asked, practice_set["created_at"])
    cfg = settings()["session"]
    items = []
    for n, question_id in enumerate(asked, start=1):
        question = _question(conn, practice_set, question_id)
        response = answered.get(question_id)
        text = {o["key"]: o["text"] for o in question["options"]}
        items.append({
            "question_id": question_id, "n": n, "stem": question["stem"],
            # shown in an order of this set's own, so that the authored first option is not the usual answer
            "options": [{"key": key, "text": text[key]} for key in option_order(list(text), f"{practice_set['id']}:{question_id}")],
            "reason_vi": item_reason(practice_set["reasons"].get(question_id, ""), question_id not in met_since, cfg),
            "chosen": response["chosen"] if response else None,
            "feedback": _feedback(conn, practice_set, question, response, answered, asked) if response else None,
        })
    return {
        "id": practice_set["id"], "source": practice_set["source"], "competency_code": practice_set["competency_code"],
        "topic": topic_names(conn)[practice_set["competency_code"]], "total": len(items), "answered": len(answered),
        "completed": practice_set["completed_at"] is not None, "items": items,
    }


def answer(conn, learner: dict, set_id: int, question_id: str, chosen: str, now: datetime,
           time_ms: int | None = None) -> dict:
    practice_set = _own_set(conn, learner, set_id, lock=True)
    answered = repo.responses(conn, set_id)
    asked = _asked(conn, practice_set, answered)
    if question_id not in asked:
        raise ApiError(404, "question_not_in_set", "Câu hỏi không thuộc bài luyện này.")
    question = _question(conn, practice_set, question_id)

    # A question is answered once: a second tap, or another choice, gets the stored result.
    if question_id in answered:
        return _feedback(conn, practice_set, question, answered[question_id], answered, asked)
    if practice_set["completed_at"] is not None:
        raise ApiError(409, "set_completed", "Bài luyện đã hoàn thành.")
    if chosen not in {o["key"] for o in question["options"]}:
        raise ApiError(422, "unknown_option", "Phương án không hợp lệ.")

    record_response(conn, learner, question, chosen, "practice", now, practice_set_id=set_id, time_ms=time_ms)
    answered = repo.responses(conn, set_id)
    return _feedback(conn, practice_set, question, answered[question_id], answered, asked)


def _tomorrows_topic(conn, learner: dict, now: datetime, without_set: int | None = None) -> str | None:
    choice = choose_topic(conn, learner, now, without_set=without_set)
    return choice.competency_code if choice else None


def complete(conn, learner: dict, set_id: int, now: datetime) -> dict:
    """Close the set and say what it changed. The learner may stop early: questions left unanswered
    count as not correct and nothing else is claimed for them. A closed set returns its stored summary."""
    practice_set = _own_set(conn, learner, set_id, lock=True)
    if practice_set["completed_at"] is not None:
        return practice_set["summary"]
    answered = repo.responses(conn, set_id)
    competencies = {_question(conn, practice_set, question_id)["competency_code"] for question_id in answered}

    # "Tomorrow": the topic of tomorrow's practice step with and without this set's answers. Nothing
    # is said when the learner has already pinned tomorrow's topic from chat: the set cannot change it.
    before = after = None
    if answered and sessions_repo.addition(conn, learner["id"], local_date(now) + timedelta(days=1)) is None:
        before = _tomorrows_topic(conn, learner, now, without_set=set_id)
        after = _tomorrows_topic(conn, learner, now)
    summary = summarise(
        total=len(_asked(conn, practice_set, answered)),
        correct=sum(r["correct"] for r in answered.values()),
        competencies_answered=len(competencies),
        cards_created=sum(r["card_id"] is not None for r in answered.values()),
        tomorrow_before=before, tomorrow_after=after, tomorrow_after_name=topic_names(conn).get(after))
    repo.complete(conn, set_id, summary, now)
    step_completed(conn, learner, "practice", now, practice_set_id=set_id)
    return summary
