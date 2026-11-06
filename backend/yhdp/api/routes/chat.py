"""Streaming tutor route."""

from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import StreamingResponse

from yhdp.api.chat import ChatRequest, chat_events
from yhdp.api.dependencies import User
from yhdp.api.routes.mount import mount_api_router
from yhdp.llm import Ollama
from yhdp.store.db import connect


def register_chat_routes(app: FastAPI, db_path: Path | None, llm: Ollama) -> None:
    router = APIRouter()

    @router.post("/chat")
    def chat(body: ChatRequest, u: User):
        # The stream outlives the request-scoped connection, so it opens its own.
        def events():
            con = connect(db_path, check_same_thread=False)
            try:
                yield from chat_events(con, llm, body, u["sub"])
            finally:
                con.close()

        return StreamingResponse(events(), media_type="application/x-ndjson",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    mount_api_router(app, router)
