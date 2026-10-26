"""Thẻ ôn: due queue, review, suspend, decks."""
from fastapi import APIRouter, Query, Request

from app.api.access import IDEMPOTENCY, Learner, access
from app.api.deps import Conn, Now
from app.api.stub import mock_example
from app.schemas.cards import CardPatch, CardReview, CardReviewResult, CardState, DeckList, DueCardList
from app.services import cards as cards_service
from app.services.idempotency import run_once

router = APIRouter(tags=["cards"])
LEARNER = access("learner")


@router.get("/cards/due", response_model=DueCardList, summary="Cards due now, overdue first", **LEARNER)
def list_due_cards(request: Request, limit: int = Query(50, ge=1, le=200), conn=Conn, now=Now, learner=Learner):
    return mock_example(request, DueCardList) or cards_service.due(conn, learner, limit, now)


@router.post("/cards/{card_id}/reviews", response_model=CardReviewResult, summary="Rate a card", **LEARNER)
def review_card(request: Request, card_id: int, body: CardReview, idempotency_key: str | None = IDEMPOTENCY,
                conn=Conn, now=Now, learner=Learner):
    return mock_example(request, CardReviewResult) or run_once(
        conn, idempotency_key, learner["pseudonym_id"], f"POST /v1/cards/{card_id}/reviews",
        lambda: cards_service.review(conn, learner, card_id, body.rating, now, body.time_ms))


@router.patch("/cards/{card_id}", response_model=CardState, summary="Suspend or unsuspend a card", **LEARNER)
def patch_card(request: Request, card_id: int, body: CardPatch, conn=Conn, learner=Learner):
    return mock_example(request, CardState) or cards_service.set_suspended(conn, learner, card_id, body.suspended)


@router.get("/decks", response_model=DeckList, summary="Decks by học phần with new, learning and due counts",
            **LEARNER)
def list_decks(request: Request, conn=Conn, now=Now, learner=Learner):
    return mock_example(request, DeckList) or cards_service.decks(conn, learner, now)
