"""Learner MCQ practice, exam, and revision deck routes."""

from fastapi import APIRouter, FastAPI, HTTPException

from yhdp.api.dependencies import DB, User
from yhdp.api.routes.mount import mount_api_router
from yhdp.api.schemas import CardReview, Flag, NewSet, PracticeAnswer, SetAnswers
from yhdp.mcq import bank, deck


def register_learning_routes(app: FastAPI) -> None:
    router = APIRouter()

    @router.get("/mcq/practice")
    def mcq_practice(u: User, con: DB, de_muc: int | None = None, van_de: int | None = None):
        return {"item": bank.next_practice(con, u["sub"], de_muc, van_de),
                "due": deck.due_count(con, u["sub"])}

    @router.post("/mcq/answer")
    def mcq_answer(body: PracticeAnswer, u: User, con: DB):
        try:
            return bank.answer(con, u["sub"], body.item_id, body.chosen, body.seconds,
                               confidence=body.confidence, card_id=body.card_id)
        except KeyError:
            raise HTTPException(404, "no such item") from None

    @router.get("/mcq/mastery")
    def mcq_mastery(u: User, con: DB):
        return bank.mastery_report(con, u["sub"])

    @router.get("/deck")
    def deck_list(u: User, con: DB):
        return deck.list_cards(con, u["sub"])

    @router.get("/deck/next")
    def deck_next(u: User, con: DB):
        return {"next": deck.next_card(con, u["sub"]), "due": deck.due_count(con, u["sub"])}

    @router.post("/deck/{card_id}/review")
    def deck_review(card_id: int, body: CardReview, u: User, con: DB):
        try:
            return deck.review(con, u["sub"], card_id, body.rating, body.item_id)
        except KeyError:
            raise HTTPException(404, "no such card") from None

    @router.delete("/deck/{card_id}")
    def deck_delete(card_id: int, u: User, con: DB):
        try:
            deck.delete(con, u["sub"], card_id)
        except KeyError:
            raise HTTPException(404, "no such card") from None
        return {"ok": True}

    @router.post("/mcq/sets")
    def mcq_new_set(body: NewSet, u: User, con: DB):
        if body.size not in (10, 30, 60):
            raise HTTPException(400, "set size must be 10, 30 or 60")
        return bank.create_set(con, u["sub"], body.size, body.timed)

    @router.get("/mcq/sets")
    def mcq_sets(u: User, con: DB):
        return {"sets": bank.list_sets(con, u["sub"])}

    @router.get("/mcq/sets/{set_id}")
    def mcq_set(set_id: int, u: User, con: DB):
        try:
            return bank.get_set(con, set_id, u["sub"])
        except KeyError:
            raise HTTPException(404, "no such set") from None

    @router.post("/mcq/sets/{set_id}/submit")
    def mcq_submit(set_id: int, body: SetAnswers, u: User, con: DB):
        try:
            return bank.submit_set(con, set_id, u["sub"], body.answers, body.seconds)
        except KeyError:
            raise HTTPException(404, "no such set") from None

    @router.post("/mcq/items/{item_id}/flag")
    def mcq_flag(item_id: int, body: Flag, u: User, con: DB):
        try:
            bank.flag(con, item_id, u["sub"], body.reason)
        except KeyError:
            raise HTTPException(404, "no such item") from None
        return {"ok": True}

    @router.get("/mcq/stats")
    def mcq_stats(_: User, con: DB):
        return bank.stats(con)
    mount_api_router(app, router)
