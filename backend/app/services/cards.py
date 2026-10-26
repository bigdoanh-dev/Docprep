"""Thẻ ôn: the due queue and FSRS reviews, scheduled on the server so every device agrees."""
from datetime import datetime

from app import events
from app.config import settings
from app.engine import memory, scheduler
from app.engine.cards import ORIGIN
from app.errors import ApiError
from app.repo import cards as repo
from app.repo import content
from app.repo import progress as progress_repo
from app.services.session_progress import step_completed


def due(conn, learner: dict, limit: int, now: datetime) -> dict:
    module_of = {t["code"]: t["module_id"] for t in content.topics(conn)}
    short_names = content.module_short_names(conn)
    items = []
    for row in repo.due(conn, learner["id"], now, limit):
        preview = scheduler.preview(row["fsrs_card"], now, learner["exam_date"], learner["target_retention"])
        items.append({"id": row["id"], "front": row["front"], "back": row["back"], "citation": row["citation"],
                      "source_passage_id": row["source_passage_id"], "origin": ORIGIN[row["source_context"]],
                      "module": short_names[module_of[row["competency_code"]]],
                      "preview": {str(rating): seconds for rating, seconds in preview.items()}})
    return {"items": items, "total_due": repo.count_due(conn, learner["id"], now)}


def review(conn, learner: dict, card_id: int, rating: int, now: datetime, time_ms: int | None = None) -> dict:
    card = repo.own_card(conn, learner["id"], card_id)
    if card is None:
        raise ApiError(404, "card_not_found", "Không tìm thấy thẻ ôn.")
    state, due_at, seconds = scheduler.review(card["fsrs_card"], rating, now, learner["exam_date"],
                                              learner["target_retention"])
    repo.apply_review(conn, card_id, state, due_at, rating, seconds, time_ms, now)
    events.record(conn, learner["pseudonym_id"], "card_review", now, duration_ms=time_ms, ref_type="card",
                  ref_id=card_id)
    step_completed(conn, learner, "cards", now)     # logs once, when this review was the last of the step's cards
    return {"card_id": card_id, "due_at": due_at, "remaining_due": repo.count_due(conn, learner["id"], now)}


def decks(conn, learner: dict, now: datetime) -> dict:
    """One deck per học phần in which the learner has a card that is not suspended."""
    module_of = {t["code"]: t["module_id"] for t in content.topics(conn)}
    mature_days = settings()["memory"]["mature_days"]
    by_module: dict[str, list[dict]] = {}
    for card in progress_repo.cards(conn, learner["id"]):
        by_module.setdefault(module_of[card["competency_code"]], []).append(card)
    items = []
    for module in content.modules(conn, learner["id"]):
        cards = by_module.get(module["id"])
        if not cards:
            continue
        stages = [memory.stage(c["fsrs_card"], c["reps"], mature_days) for c in cards]
        items.append({"module_id": module["id"], "name": module["name"], "short_name": module["short_name"],
                      "new": stages.count("new"), "learning": stages.count("learning"),
                      "due": sum(1 for c in cards if c["due_at"] <= now)})
    return {"items": items}


def set_suspended(conn, learner: dict, card_id: int, suspended: bool) -> dict:
    """Take a card out of every queue and count, or put it back with its schedule as it was."""
    if repo.own_card(conn, learner["id"], card_id) is None:
        raise ApiError(404, "card_not_found", "Không tìm thấy thẻ ôn.")
    return repo.set_suspended(conn, card_id, suspended)
