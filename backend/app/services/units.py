"""A unit, item by item: content cards, quiz items, and the remediation a wrong answer adds."""
from datetime import datetime

from app import events
from app.errors import ApiError
from app.repo import content
from app.repo import responses as responses_repo
from app.repo import units as repo
from app.services.responses import record_response, require_question
from app.services.session_progress import step_completed


def _unit(conn, unit_id: str) -> dict:
    unit = repo.get(conn, unit_id)
    if unit is None:
        raise ApiError(404, "unit_not_found", "Không tìm thấy chủ đề.")
    return unit


def _session(conn, learner: dict, unit_id: str, now: datetime) -> dict:
    """The learner's unfinished pass through this unit, created on first use in the authored order."""
    return (repo.open_session(conn, learner["id"], unit_id)
            or repo.create_session(conn, learner["id"], unit_id, repo.authored_item_ids(conn, unit_id), now))


def _option_text(question: dict, key: str | None) -> str:
    return next((o["text"] for o in question["options"] if o["key"] == key), "")


def _feedback(conn, session: dict, item: dict, question: dict, response: dict) -> dict:
    remediation = repo.remediation_after(conn, session["unit_id"], item["id"])
    inserted = bool(remediation) and remediation["id"] in session["queue"]
    note = None
    if inserted:
        note = (f"Đã thêm 1 ví dụ vào lộ trình vì bạn chọn {_option_text(question, response['chosen'])}"
                f" — {remediation['note']}.")
    return {
        "correct": response["correct"],
        "correct_key": next(o["key"] for o in question["options"] if o["is_correct"]),
        "explanation": question["explanation"],
        "rationales": {o["key"]: o["rationale"] for o in question["options"]},
        "citations": content.citations_for(conn, question["source_passage_ids"]),
        "remediation_inserted": inserted,
        "remediation_note": note,
        "card_created": response["card_id"] is not None,
    }


def _view(conn, session: dict, unit: dict) -> dict:
    view = {"session_id": session["id"], "unit_id": unit["id"], "topic": unit["topic"],
            "position": session["cursor"], "total": len(session["queue"]), "done": session["done"],
            "cards_created": session["cards_created"], "item": None}
    if session["done"]:
        return view
    item = repo.item(conn, session["queue"][session["cursor"]])
    out = {"unit_item_id": item["id"], "kind": item["kind"]}
    if item["kind"] == "quiz":
        question = require_question(conn, item["question_id"])
        out["question"] = {"id": question["id"], "stem": question["stem"],
                           "options": [{"key": o["key"], "text": o["text"]} for o in question["options"]]}
        response = responses_repo.find_unit_response(conn, session["id"], item["id"])
        out["chosen"] = response["chosen"] if response else None
        out["feedback"] = _feedback(conn, session, item, question, response) if response else None
    else:
        item_content = content.approved_content(conn, item["content_id"])
        if item_content is None:
            raise ApiError(404, "item_not_found", "Nội dung này hiện không khả dụng.")
        out.update(title=item_content["title"], body=item_content["body"],
                   citations=content.citations_for(conn, item_content["source_passage_ids"]))
        if item["kind"] == "remediation":
            previous = responses_repo.find_unit_response(conn, session["id"], item["after_item_id"])
            question = content.question_as_served(conn, previous["question_id"], previous["question_version"])
            out["reason"] = f"Được thêm vì bạn chọn {_option_text(question, previous['chosen'])} ở câu trước"
    view["item"] = out
    return view


def next_item(conn, learner: dict, unit_id: str, now: datetime) -> dict:
    unit = _unit(conn, unit_id)
    return _view(conn, _session(conn, learner, unit_id, now), unit)


def answer(conn, learner: dict, unit_id: str, unit_item_id: str, chosen: str, now: datetime,
           time_ms: int | None = None) -> dict:
    _unit(conn, unit_id)
    session = _session(conn, learner, unit_id, now)
    item = repo.quiz_item(conn, unit_id, unit_item_id)
    if item is None:
        raise ApiError(404, "item_not_found", "Không tìm thấy câu hỏi trong chủ đề này.")
    question = require_question(conn, item["question_id"])

    # A second "Kiểm tra" on the same item returns the stored result and writes nothing.
    existing = responses_repo.find_unit_response(conn, session["id"], item["id"])
    if existing:
        return _feedback(conn, session, item, question, existing)

    if session["queue"][session["cursor"]] != item["id"]:
        raise ApiError(409, "not_current_item", "Câu hỏi này không phải là bước hiện tại.")
    if chosen not in {o["key"] for o in question["options"]}:
        raise ApiError(422, "unknown_option", "Phương án không hợp lệ.")

    result = record_response(conn, learner, question, chosen, "unit", now, unit_session_id=session["id"],
                             unit_item_id=item["id"], time_ms=time_ms)
    queue = list(session["queue"])
    if not result.correct:
        remediation = repo.remediation_after(conn, unit_id, item["id"])
        if remediation and remediation["id"] not in queue:
            queue.insert(session["cursor"] + 1, remediation["id"])
            events.record(conn, learner["pseudonym_id"], "remediation_inserted", now, ref_type="unit_item",
                          ref_id=remediation["id"])
    session = repo.record_answer(conn, session["id"], queue, result.card_id is not None, now)
    return _feedback(conn, session, item, question, responses_repo.find_unit_response(conn, session["id"], item["id"]))


def advance(conn, learner: dict, unit_id: str, unit_item_id: str, now: datetime) -> dict:
    unit = _unit(conn, unit_id)
    session = _session(conn, learner, unit_id, now)
    # Only the current item can be left, so a repeated tap does not skip a step.
    if session["queue"][session["cursor"]] == unit_item_id:
        cursor = session["cursor"] + 1
        session = repo.move_to(conn, session["id"], cursor, cursor >= len(session["queue"]), now)
        if session["done"]:
            step_completed(conn, learner, "continue", now, unit_id=unit_id)
    return _view(conn, session, unit)
