from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.chat.slots import ModelSlots
from app.config import app_mode, env, settings
from app.errors import (ApiError, api_error_handler, http_error_handler, unexpected_error_handler,
                        validation_error_handler)
from app.openapi import API_DESCRIPTION, extend_openapi

API_TITLE = "YHDP Exam Platform API"
API_VERSION = "1.0.0-draft.1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open the connection pool. Fail fast with a clear message when the database is unreachable or
    its schema is behind."""
    from app.config import settings
    from app.db import check_ready, open_pool

    cfg = settings()["db"]
    pool = open_pool(app.state.database_url, cfg["pool_min"], cfg["pool_max"])
    try:
        with pool.connection() as conn:
            check_ready(conn)
    except Exception:
        pool.close()
        raise
    app.state.pool = pool
    try:
        yield
    finally:
        pool.close()


def create_app(mode: str | None = None, database_url: str | None = None) -> FastAPI:
    """mode "real" needs the database (database_url, or DATABASE_URL); "mock" serves the contract's
    examples and needs nothing."""
    mode = app_mode(mode)
    from app.config import model_provider
    provider = model_provider()  # fail before starting if a scripted production config was supplied
    app = FastAPI(
        title=API_TITLE, version=API_VERSION, description=API_DESCRIPTION,
        lifespan=lifespan if mode == "real" else None,
        # The function name is the operation id, so generated clients get `list_exams`, not a path-derived name.
        generate_unique_id_function=lambda route: route.name)
    app.state.mode = mode
    # How many model calls run at once; a chat turn beyond that waits in line (app/chat/slots.py).
    app.state.model_slots = ModelSlots(settings()["gateway"]["max_concurrent"])
    if mode == "real":
        app.state.database_url = database_url or env("DATABASE_URL")
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)

    @app.get("/health", include_in_schema=False)
    def health():
        return {"ok": True, "mode": mode, "model_provider": provider,
                "demo_content": env("APP_ENV", "dev") in ("dev", "test")}

    from app.api import V1_ROUTERS
    for router in V1_ROUTERS:
        app.include_router(router, prefix="/v1")

    # /openapi.json and /docs serve the contract itself, not FastAPI's unextended schema.
    fastapi_openapi = app.openapi
    contract: dict = {}

    def openapi() -> dict:
        if not contract:
            contract.update(extend_openapi(fastapi_openapi()))
        return contract

    app.openapi = openapi
    return app


app = create_app()
