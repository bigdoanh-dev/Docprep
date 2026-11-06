"""FastAPI application factory and shared request dependencies."""

from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from yhdp.api.auth import jwt_secret
from yhdp.api.frontend import register_frontend_routes
from yhdp.api.routes.auth import LOGIN_MAX_FAILS, register_auth_routes
from yhdp.api.routes.chat import register_chat_routes
from yhdp.api.routes.files import register_file_routes
from yhdp.api.routes.learning import register_learning_routes
from yhdp.api.routes.review import register_review_routes
from yhdp.llm import Ollama
from yhdp.settings import settings

__all__ = ["LOGIN_MAX_FAILS", "create_app"]


def create_app(db_path: Path | None = None, web_dir: Path | None = None,
               secret: str | None = None, llm: Ollama | None = None,
               review_dir: Path | None = None,
               serve_frontends: bool | None = None) -> FastAPI:
    owns_llm = llm is None
    llm_client = llm if llm is not None else Ollama()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            if owns_llm:
                llm_client.close()

    app = FastAPI(title="YHDP", docs_url=None, redoc_url=None, openapi_url=None,
                  lifespan=lifespan)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )
    secret = secret or jwt_secret()
    app.state.db_path = db_path
    app.state.jwt_secret = secret
    web_dir = web_dir or settings.root / "web" / "dist"
    review_dir = review_dir or settings.root / "web-review" / "dist"
    if serve_frontends is None:
        serve_frontends = settings.serve_frontends
    failures: dict[str, deque] = defaultdict(deque)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    register_auth_routes(app, secret, failures)
    register_chat_routes(app, db_path, llm_client)
    register_learning_routes(app)
    register_review_routes(app)
    register_file_routes(app)
    if serve_frontends:
        register_frontend_routes(app, web_dir, review_dir)

    return app
