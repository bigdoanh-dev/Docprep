"""Thi thử: the diagnostic and mock forms, one server-side countdown, autosave, hand-in, results.

Scoring is deterministic; no model is involved. A new attempt is built from approved questions only.
Nothing here predicts a real exam outcome.
"""
import random
from datetime import datetime, timedelta

from app import events
from app.config import settings
from app.engine import assembly
from app.engine.elo import p_correct
from app.errors import ApiError
from app.repo import content
from app.repo import exams as repo
from app.repo import learners as learners_repo
from app.repo import responses as responses_repo
from app.services.responses import ranking, record_response, topic_names, topic_states


def _visible_kinds() -> list[str]:
    """Automatic assembly is scheduled for R1.1, so the assembled form shows only where it is switched on."""
    kinds = ["diagnostic", "mock", "demo_short"]
    return kinds + ["assembled"] if settings()["exam"].get("assembled_enabled", False) else kinds


def _form(conn, learner: dict, form_id: str) -> dict:
    form = repo.form(conn, form_id, learner["is_synthetic"])
    if form is None or form["kind"] not in _visible_kinds():
        raise ApiError(404, "form_not_found", "Không tìm thấy đề thi.")
    return form


def _size(form: dict) -> int:
    """Number of questions: the fixed list, or the configured size of an assembled form."""
    return form["n_questions"] or len(form["question_ids"])


def _attempts_left(conn, learner: dict, form: dict) -> int | None:
    if form["max_attempts"] is None:
        return None
    return max(0, form["max_attempts"] - repo.attempts_used(conn, learner["id"], form["id"]))


def _remaining(attempt: dict, now: datetime) -> int:
    return max(0, int((attempt["deadline_at"] - now).total_seconds()))


def _question(conn, attempt: dict, question_id: str) -> dict:
    """The question in the version this attempt serves, fixed when it started."""
    return content.question_as_served(conn, question_id, attempt["question_versions"].get(question_id))


# ---- handing in ---------------------------------------------------------------------------------

def _hand_in(conn, learner: dict, attempt: dict, auto: bool, now: datetime) -> dict:
    """Score the attempt, update mastery, build cards from wrong answers, recompute priority.
    Returns the attempt row as stored."""
    form = repo.form_of_attempt(conn, attempt["form_id"])
    context = "diagnostic" if form["kind"] == "diagnostic" else "mock"
    answers = repo.answers(conn, attempt["id"])
    content.lock_questions(conn, attempt["question_order"])
    names = topic_names(conn)
    before = ranking(conn, learner)
    items, score, new_cards = [], 0, 0
    for n, qid in enumerate(attempt["question_order"], start=1):
        question = _question(conn, attempt, qid)   # one retired since the start is still scored
        chosen = answers.get(qid, {}).get("chosen")
        if chosen is None:
            status = "blank"  # not answered: no response row, no mastery change, no card
        else:
            result = record_response(conn, learner, question, chosen, context, now, attempt_id=attempt["id"])
            status = "ok" if result.correct else "wrong"
            score += result.correct
            new_cards += result.card_id is not None
        items.append({"n": n, "question_id": qid, "topic": names[question["competency_code"]], "status": status})

    after = ranking(conn, learner)
    moved_up = [code for code in after if after.index(code) < before.index(code)]
    summary = {
        "attempt_id": attempt["id"], "title": form["title"], "score": score, "total": len(items),
        "wrong": sum(i["status"] == "wrong" for i in items), "blank": sum(i["status"] == "blank" for i in items),
        "duration_s": int((now - attempt["started_at"]).total_seconds()), "auto_submitted": auto,
        "new_cards": new_cards, "priority_top": [names[code] for code in after[:2]],
        "priority_moved_up": [names[code] for code in moved_up],
        "items": items,
    }
    events.record(conn, learner["pseudonym_id"], "exam_submitted", now,
                  duration_ms=int((now - attempt["started_at"]).total_seconds() * 1000), measured=True,
                  ref_type="attempt", ref_id=attempt["id"])
    return repo.close(conn, attempt["id"], now, auto, score, summary)


def close_expired(conn, learner: dict, now: datetime) -> None:
    """Hand in the attempts whose time ran out while the learner was away.

    The countdown is server-side and cannot be paused, so an attempt left past its deadline is over.
    Scoring it here puts it into the history instead of leaving it unscored and unlisted. It is
    stamped at its deadline: that is when the learner's time ended.
    """
    for attempt in repo.expired(conn, learner["id"], now):
        _hand_in(conn, learner, attempt, auto=True, now=attempt["deadline_at"])


def _attempt(conn, learner: dict, attempt_id: int, now: datetime) -> tuple[dict, bool]:
    """The learner's attempt, and whether this request just handed it in because its time was up.
    Someone else's attempt is not found."""
    attempt = repo.attempt(conn, learner["id"], attempt_id)
    if attempt is None:
        raise ApiError(404, "attempt_not_found", "Không tìm thấy lượt làm bài.")
    if attempt["submitted_at"] is None and now > attempt["deadline_at"]:
        return _hand_in(conn, learner, attempt, auto=True, now=attempt["deadline_at"]), True
    return attempt, False


def _results(attempt: dict) -> dict:
    return {**attempt["summary"], "submitted_at": attempt["submitted_at"]}


# ---- assembled forms ----------------------------------------------------------------------------

def _plan(conn, learner: dict, form: dict) -> assembly.Plan:
    """Choose this learner's questions for an assembled form. Deterministic for a given history."""
    cfg = settings()
    theta = {code: row["theta"] for code, row in responses_repo.mastery_rows(conn, learner["id"]).items()}
    candidates = [
        assembly.Candidate(
            id=r["id"], topic=r["competency_code"],
            bucket="new" if r["correct"] is None else ("review" if r["correct"] else "wrong"),
            p_correct=p_correct(theta.get(r["competency_code"], 0.0), r["difficulty_b"]), last_seen=r["created_at"])
        for r in repo.candidate_rows(conn, learner["id"], learner["is_synthetic"])]
    shares = assembly.topic_shares(topic_states(conn, learner["id"]), repo.completed_topics(conn, learner["id"]),
                                   cfg["priority"]["neutral_mastery"], cfg["assembly"]["unstudied_factor"])
    return assembly.assemble(candidates, form["n_questions"], shares, cfg["assembly"]["mix"],
                             cfg["assembly"]["target_p"])


def _describe(conn, plan: assembly.Plan) -> dict:
    """What the learner is told before starting: the mix and the topics, never the questions."""
    names = topic_names(conn)
    return {"composition": plan.composition,
            "topics": [{"name": names[code], "count": count} for code, count in plan.topics.items()]}


# ---- use cases ----------------------------------------------------------------------------------

def list_forms(conn, learner: dict, now: datetime) -> dict:
    """The forms with the learner's history (newest first) and any attempt still running."""
    close_expired(conn, learner, now)
    out = []
    for form in repo.forms(conn, _visible_kinds(), learner["is_synthetic"]):
        n = _size(form)
        history = [{"attempt_id": a["id"], "submitted_at": a["submitted_at"],
                    "duration_s": int((a["submitted_at"] - a["started_at"]).total_seconds()),
                    "score": a["score"], "total": n, "auto_submitted": a["auto_submitted"]}
                   for a in repo.finished(conn, learner["id"], form["id"])]
        running = repo.running(conn, learner["id"], form["id"])
        out.append({
            "id": form["id"], "title": form["title"], "kind": form["kind"], "n_questions": n,
            "minutes": n * form["seconds_per_question"] // 60,
            "attempts_left": _attempts_left(conn, learner, form),
            "last": {k: history[0][k] for k in ("attempt_id", "score", "total")} if history else None,
            "open_attempt_id": running["id"] if running else None,
            "open_remaining_s": _remaining(running, now) if running else None,
            "history": history,
            # An assembled form says beforehand how the next test will be put together.
            "plan": _describe(conn, _plan(conn, learner, form)) if form["kind"] == "assembled" else None,
        })
    return {"items": out}


def _view(conn, attempt: dict, now: datetime) -> dict:
    form = repo.form_of_attempt(conn, attempt["form_id"])
    questions = []
    for n, qid in enumerate(attempt["question_order"], start=1):
        question = _question(conn, attempt, qid)
        text = {o["key"]: o["text"] for o in question["options"]}
        questions.append({"id": qid, "n": n, "stem": question["stem"],
                          "options": [{"key": k, "text": text[k]} for k in attempt["option_orders"][qid]]})
    saved = {qid: {"chosen": a["chosen"], "flagged": a["flagged"]} for qid, a in repo.answers(conn, attempt["id"]).items()}
    return {
        "attempt_id": attempt["id"], "title": form["title"], "deadline_at": attempt["deadline_at"],
        "remaining_s": _remaining(attempt, now), "warning_s": settings()["exam"]["warning_seconds"],
        "submitted": attempt["submitted_at"] is not None, "questions": questions, "answers": saved,
    }


def start(conn, learner: dict, form_id: str, fresh: bool, now: datetime) -> dict:
    form = _form(conn, learner, form_id)
    # Two taps on "Bắt đầu" must not open two attempts: the second waits here and then resumes the first.
    learners_repo.lock(conn, learner["id"])
    close_expired(conn, learner, now)
    running = repo.running(conn, learner["id"], form_id, lock=True)
    if running and fresh:
        # The clock cannot be paused and nothing is discarded: the running attempt is handed in with
        # the answers given so far, and shows up in the history like any other.
        _hand_in(conn, learner, running, auto=False, now=now)
    elif running:
        # A second tap on "Bắt đầu" (or "Làm tiếp") resumes the running attempt.
        return _view(conn, running, now)
    if _attempts_left(conn, learner, form) == 0:
        raise ApiError(409, "no_attempts_left", "Bạn đã hết lượt làm đề này.")

    rng = random.Random()
    plan = None
    if form["kind"] == "assembled":
        plan = _plan(conn, learner, form)
        order = list(plan.question_ids)
    else:
        order = list(form["question_ids"])
    rng.shuffle(order)
    option_orders, versions = {}, {}
    for qid in order:
        question = content.approved_question(conn, qid)
        if question is None:
            # Only approved questions are served: a form holding a retired one waits for its new version.
            raise ApiError(409, "form_unavailable", "Đề thi này tạm thời chưa sẵn sàng.")
        keys = [o["key"] for o in question["options"]]
        rng.shuffle(keys)
        option_orders[qid] = keys
        versions[qid] = question["version"]
    deadline = now + timedelta(seconds=len(order) * form["seconds_per_question"])
    attempt = repo.create_attempt(conn, learner["id"], form_id, order, option_orders, versions, now, deadline,
                                  {"composition": plan.composition, "topics": plan.topics} if plan else None)
    events.record(conn, learner["pseudonym_id"], "exam_started", now, ref_type="attempt", ref_id=attempt["id"])
    return _view(conn, attempt, now)


def get_attempt(conn, learner: dict, attempt_id: int, now: datetime) -> dict:
    attempt, _ = _attempt(conn, learner, attempt_id, now)
    return _view(conn, attempt, now)


def save_answer(conn, learner: dict, attempt_id: int, question_id: str, chosen: str | None, flagged: bool,
                now: datetime) -> dict:
    attempt, just_closed = _attempt(conn, learner, attempt_id, now)
    if attempt["submitted_at"] is not None:
        if just_closed:
            # The request ends in an error, which would roll the hand-in back: keep it first.
            conn.commit()
        raise ApiError(409, "attempt_closed", "Bài làm đã được nộp.")
    if question_id not in attempt["option_orders"]:
        raise ApiError(404, "question_not_in_attempt", "Câu hỏi không thuộc đề này.")
    if chosen is not None and chosen not in attempt["option_orders"][question_id]:
        raise ApiError(422, "unknown_option", "Phương án không hợp lệ.")
    repo.save_answer(conn, attempt_id, question_id, chosen, flagged, now)
    return {"ok": True}


def submit(conn, learner: dict, attempt_id: int, now: datetime) -> dict:
    attempt, _ = _attempt(conn, learner, attempt_id, now)
    if attempt["submitted_at"] is None:
        attempt = _hand_in(conn, learner, attempt, auto=False, now=now)
    return _results(attempt)  # a repeated "Nộp bài" returns the stored results


def results(conn, learner: dict, attempt_id: int, now: datetime) -> dict:
    attempt, _ = _attempt(conn, learner, attempt_id, now)
    if attempt["submitted_at"] is None:
        raise ApiError(409, "attempt_open", "Bài làm chưa được nộp.")
    return _results(attempt)


def review_item(conn, learner: dict, attempt_id: int, question_id: str, now: datetime) -> dict:
    attempt, _ = _attempt(conn, learner, attempt_id, now)
    if attempt["submitted_at"] is None:
        raise ApiError(409, "attempt_open", "Bài làm chưa được nộp.")
    if question_id not in attempt["option_orders"]:
        raise ApiError(404, "question_not_in_attempt", "Câu hỏi không thuộc đề này.")
    question = _question(conn, attempt, question_id)
    by_key = {o["key"]: o for o in question["options"]}
    saved = repo.answers(conn, attempt_id).get(question_id)
    return {
        "n": attempt["question_order"].index(question_id) + 1, "total": len(attempt["question_order"]),
        "question_id": question_id, "stem": question["stem"],
        "options": [{"key": k, "text": by_key[k]["text"], "is_correct": by_key[k]["is_correct"]}
                    for k in attempt["option_orders"][question_id]],
        "chosen": saved["chosen"] if saved else None, "explanation": question["explanation"],
        "rationales": {k: o["rationale"] for k, o in by_key.items()},
        "citations": content.citations_for(conn, question["source_passage_ids"]),
    }
