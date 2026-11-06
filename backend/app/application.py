from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

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

    ollama = None
    if app.state.service == 'chat' and app.state.phase_config.provider == 'ollama':
        from app.ollama_gateway import OllamaConfig, OllamaGateway
        if settings()['postcheck']['tier2_enabled']:
            raise RuntimeError('Examiner model is unconfirmed; keep tier2 disabled')
        ollama = OllamaGateway(OllamaConfig.load())
    cfg = settings()["db"] if app.state.service == "alpha" else {"pool_min": 1, "pool_max": app.state.phase_config.pool_max}
    pool = open_pool(app.state.database_url, cfg["pool_min"], cfg["pool_max"])
    try:
        with pool.connection() as conn:
            if app.state.service == "alpha":
                row = conn.execute("select version_num from alembic_version").fetchone()
                if not row or row["version_num"] not in ("0012", "0013"):
                    check_ready(conn)
            else:
                check_ready(conn)
    except Exception:
        pool.close()
        raise
    app.state.pool = pool
    if app.state.service != "alpha":
        import asyncio
        import signal
        import threading
        def drain():
            app.state.draining = True
            if app.state.service == "chat":
                app.state.worker.draining = True
        try:
            if threading.current_thread() is threading.main_thread():
                asyncio.get_running_loop().add_signal_handler(signal.SIGUSR1, drain)
        except (AttributeError, NotImplementedError):
            pass  # Windows uses tests/state; production operation runs inside Linux containers.
    if app.state.service == "chat":
        import asyncio
        from redis.asyncio import Redis
        from app.chat.admission import Admission
        from app.chat.worker import ChatWorker
        from app.api.deps import get_gateway
        app.state.admission = Admission(app.state.phase_config)
        app.state.redis_async = Redis.from_url(app.state.phase_config.redis_url, decode_responses=True,
                                               socket_connect_timeout=2, socket_timeout=3)
        app.state.model_gateway = ollama
        def gateway_factory():
            override = app.dependency_overrides.get(get_gateway)
            if override:
                return override()
            if ollama is not None:
                return ollama
            from app.scripted_gateway import ScriptedGateway
            if app.state.phase_config.provider != "scripted":
                raise RuntimeError("AI generation disabled")
            return ScriptedGateway()
        app.state.worker = ChatWorker(pool, app.state.admission, app.state.phase_config, gateway_factory)
        app.state.worker.queue_wait_metric = app.state.queue_wait_metric
        try:
            await asyncio.to_thread(app.state.worker.start)
        except Exception:
            app.state.worker.close()
            await app.state.redis_async.aclose()
            app.state.admission.close()
            pool.close()
            raise
    try:
        yield
    finally:
        if app.state.service == "chat":
            await asyncio.to_thread(app.state.worker.close)
            await app.state.redis_async.aclose()
            app.state.admission.close()
        pool.close()


def create_app(mode: str | None = None, database_url: str | None = None, *, service: str = "alpha") -> FastAPI:
    """mode "real" needs the database (database_url, or DATABASE_URL); "mock" serves the contract's
    examples and needs nothing."""
    mode = app_mode(mode)
    from app.config import model_provider
    from app.phase_config import PhaseConfig
    phase_cfg = PhaseConfig.load() if service != "alpha" else None
    provider = model_provider() if service == "alpha" else (phase_cfg.provider if service == "chat" else "none")
    app = FastAPI(
        title=API_TITLE, version=API_VERSION, description=API_DESCRIPTION,
        lifespan=lifespan if mode == "real" else None,
        # The function name is the operation id, so generated clients get `list_exams`, not a path-derived name.
        generate_unique_id_function=lambda route: route.name)
    app.state.mode = mode
    app.state.service = service
    app.state.phase_config = phase_cfg
    # How many model calls run at once; a chat turn beyond that waits in line (app/chat/slots.py).
    if service == "alpha":
        from app.chat.slots import ModelSlots
        app.state.model_slots = ModelSlots(settings()["gateway"]["max_concurrent"])
    if mode == "real":
        app.state.database_url = database_url or env("DATABASE_URL")
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)

    @app.get("/health", include_in_schema=False)
    def health():
        return {"ok": True, "mode": mode, "service": service, "model_provider": provider,
                "demo_content": env("APP_ENV", "dev") in ("dev", "test")}

    from app.api import V1_ROUTERS
    if service == "alpha":
        for router in V1_ROUTERS:
            app.include_router(router, prefix="/v1")
    else:
        from app.phase_routes import partition
        for router in partition(service):
            app.include_router(router, prefix="/v1")
        from app.observability import instrument
        instrument(app)

    # /openapi.json and /docs serve the contract itself, not FastAPI's unextended schema.
    fastapi_openapi = app.openapi
    contract: dict = {}

    def openapi() -> dict:
        if not contract:
            contract.update(extend_openapi(fastapi_openapi()))
        return contract

    app.openapi = openapi
    return app
