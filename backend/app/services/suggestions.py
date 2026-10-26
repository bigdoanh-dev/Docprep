"""Suggestions after a chat answer (handover/04, "Suggestions after an answer").

Rules make them from the learner's own record; the model has no part in it and never sees that
record. A suggestion is a proposal: the practice set, or the addition to tomorrow's session, is
written only when the learner taps it (`accept`), and a second tap changes nothing.
"""
from datetime import datetime, timedelta

from app.config import settings
from app.engine import suggestions as rule
from app.errors import ApiError
from app.repo import learners as learners_repo
from app.repo import practice as practice_repo
from app.repo import sessions as sessions_repo
from app.repo import suggestions as repo
from app.services import practice
from app.services.account import local_date
from app.services.responses import topic_names


def _shown(row: dict) -> dict:
    return {"id": row["id"], "kind": row["kind"], "label_vi": rule.label(row["kind"], row["n_items"]),
            "reason_vi": row["reason_vi"], "n_items": row["n_items"]}


def after_answer(conn, learner: dict, message_id: int, outcome, now: datetime) -> list[dict]:
    """The suggestions that follow this answer, stored with it. Only an answer has any, and only
    when its sources belong to a competency the learner has lately answered wrongly."""
    if outcome.state != "answered" or not outcome.cited_competencies:
        return []
    cfg = settings()["suggestions"]
    wrong = practice_repo.wrong_counts(conn, learner["id"], now - timedelta(days=cfg["window_days"]))
    available = {code: len(practice.eligible(conn, learner, code, now))
                 for code in outcome.cited_competencies if wrong.get(code)}
    tomorrow = local_date(now) + timedelta(days=1)
    offers = rule.propose(outcome.cited_competencies, wrong, available, topic_names(conn),
                          sessions_repo.addition(conn, learner["id"], tomorrow) is not None,
                          cfg["window_days"], cfg["max_items"])
    return [_shown(repo.insert(conn, learner["id"], message_id, o["kind"], o["competency_code"], o["n_items"],
                               o["reason_vi"], now)) for o in offers]


def of_messages(conn, message_ids: list[int]) -> dict[int, list[dict]]:
    return {mid: [_shown(row) for row in rows] for mid, rows in repo.of_messages(conn, message_ids).items()}


def accept(conn, learner: dict, suggestion_id: int, now: datetime) -> dict:
    """Do what the learner tapped. `practise` builds a practice set of approved questions on the
    competency; `add_to_tomorrow` puts the competency into the session of the day after the tap."""
    suggestion = repo.own(conn, learner["id"], suggestion_id)
    if suggestion is None:
        raise ApiError(404, "suggestion_not_found", "Không tìm thấy đề xuất.")
    code = suggestion["competency_code"]

    if suggestion["kind"] == "practise":
        if suggestion["accepted_at"] is not None:
            built = repo.practice_set_of(conn, learner["id"], code, suggestion["accepted_at"])
            if built:
                return {"kind": "practise", "practice_set_id": built["id"], "for_date": None}
        built = practice.build(conn, learner, "chat_suggestion", code, 0, True, now, limit=suggestion["n_items"])
        if built is None:
            raise ApiError(409, "nothing_to_practise", "Hiện chưa có câu hỏi đã duyệt cho chủ đề này.")
        repo.mark_accepted(conn, suggestion_id, now)
        return {"kind": "practise", "practice_set_id": built["id"], "for_date": None}

    added = repo.addition_of(conn, suggestion_id)
    if added is None:
        for_date = local_date(now) + timedelta(days=1)
        # The daily session takes one topic from chat. Held on the learner's row, so two taps on two
        # different offers are taken in turn and the second one is told, not silently overwritten.
        learners_repo.lock(conn, learner["id"])
        if sessions_repo.addition(conn, learner["id"], for_date) is not None:
            raise ApiError(409, "tomorrow_taken", "Phiên ngày mai đã có một chủ đề bạn thêm từ Hỏi đáp.")
        repo.add_to_day(conn, learner["id"], for_date, code, suggestion_id, now)
        repo.mark_accepted(conn, suggestion_id, now)
        added = {"for_date": for_date}
    return {"kind": "add_to_tomorrow", "practice_set_id": None, "for_date": added["for_date"]}
