"""Reviewer queue and decision routes."""

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel

from yhdp.api import review as review_service
from yhdp.api.dependencies import DB, Reviewer
from yhdp.api.routes.mount import mount_api_router
from yhdp.api.schemas import McqDecision
from yhdp.mcq import bank


class TagDecision(BaseModel):
    action: str
    edit: review_service.TagEdit | None = None


def register_review_routes(app: FastAPI) -> None:
    router = APIRouter()

    @router.post("/review/mcq/{item_id}")
    def review_mcq(item_id: int, body: McqDecision, u: Reviewer, con: DB):
        try:
            bank.review(con, item_id, body.action, u["sub"], body.note)
        except KeyError:
            raise HTTPException(404, "no such item") from None
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        return {"ok": True}

    @router.get("/review/stats")
    def review_stats(_: Reviewer, con: DB):
        return review_service.stats(con)

    @router.get("/review/next")
    def review_next(_: Reviewer, con: DB, kind: str = "tag", doc: str | None = None):
        if kind == "tag":
            return {"item": review_service.next_tag_item(con, doc)}
        if kind == "dictionary":
            return {"item": review_service.next_dictionary_item(con)}
        if kind == "mcq":
            return {"item": bank.next_review(con)}
        raise HTTPException(400, f"unknown kind {kind!r}")

    @router.post("/review/tag/{item_id}")
    def review_tag(item_id: int, body: TagDecision, u: Reviewer, con: DB):
        try:
            review_service.decide_tag(con, item_id, body.action, u["sub"], body.edit)
        except KeyError:
            raise HTTPException(404, "no such review item") from None
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        return {"ok": True}

    @router.post("/review/dictionary/{item_id}")
    def review_dictionary(item_id: int, body: review_service.DictionaryDecision,
                          u: Reviewer, con: DB):
        try:
            review_service.decide_dictionary(con, item_id, body, u["sub"])
        except KeyError as e:
            raise HTTPException(404, str(e)) from None
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        return {"ok": True}
    mount_api_router(app, router)
