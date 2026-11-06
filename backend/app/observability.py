"""Metadata-only logs, process-local metrics and dependency readiness."""
import json
import logging
import time
import uuid
from fastapi import Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CollectorRegistry, Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from app.db import check_ready


class MetadataFormatter(logging.Formatter):
    def format(self, record):
        allowed = {"http_response", "turn_failed", "dispatch_unavailable", "turn_worker_exception", "suggestions_failed"}
        data = {"level": record.levelname, "event": record.msg if isinstance(record.msg, str) and record.msg in allowed else "runtime_event"}
        for key in ("request_id", "turn_id", "service", "instance", "method", "route", "status", "duration_s", "error_type"):
            if hasattr(record, key):
                data[key] = getattr(record, key)
        return json.dumps(data)


class ServiceContext(logging.Filter):
    def __init__(self, service, instance):
        super().__init__()
        self.service, self.instance = service, instance

    def filter(self, record):
        if not hasattr(record, 'service'):
            record.service = self.service
        if not hasattr(record, 'instance'):
            record.instance = self.instance
        return True


def instrument(app):
    service, instance = app.state.service, str(uuid.uuid4())
    app.state.draining = False
    registry = CollectorRegistry()
    requests = Counter("docprep_http_requests", "HTTP responses", ["service", "method", "route", "status"], registry=registry)
    latency = Histogram("docprep_http_headers_seconds", "Time to headers, not total SSE duration", ["service", "route"], registry=registry)
    queue = Gauge("docprep_ai_queued", "Durable queued turns", registry=registry)
    slots = Gauge("docprep_ai_model_reservations", "Open reservations including quarantine", registry=registry)
    quarantine = Gauge("docprep_ai_quarantined", "Unconfirmed model calls", registry=registry)
    pool_used = Gauge("docprep_db_pool_used", "Borrowed pool connections", registry=registry)
    terminals = Gauge("docprep_ai_turns", "Turn count by status", ["status"], registry=registry)
    app.state.queue_wait_metric = Histogram("docprep_ai_queue_wait_seconds", "Time until claim", registry=registry)
    app.state.reconnect_metric = Counter("docprep_ai_reconnects", "Event resume requests", registry=registry)
    handler = logging.StreamHandler()
    handler.setFormatter(MetadataFormatter())
    handler.addFilter(ServiceContext(service, instance))
    # Server/pool exceptions can contain raw SQL or connection details. Keep only
    # metadata for these loggers too; --no-access-log alone does not cover errors.
    for logger_name in ("app.phase", "app.chat.worker", "uvicorn", "uvicorn.error", "uvicorn.access", "psycopg.pool"):
        logger = logging.getLogger(logger_name)
        logger.handlers = [handler]
        logger.setLevel(logging.WARNING if logger_name == "psycopg.pool" else logging.INFO)
        logger.propagate = False
    log = logging.getLogger("app.phase")

    @app.middleware("http")
    async def observe(request: Request, call_next):
        if app.state.draining and request.url.path.startswith("/v1/"):
            from app.errors import error_response
            return error_response(503, "service_draining", "Dịch vụ đang cập nhật. Vui lòng thử lại.")
        rid, started = str(uuid.uuid4()), time.monotonic()
        response = await call_next(request)
        route = getattr(request.scope.get("route"), "path", "unmatched")
        elapsed = time.monotonic() - started
        requests.labels(service, request.method, route, str(response.status_code)).inc()
        latency.labels(service, route).observe(elapsed)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Service-Instance"] = service + ":" + instance
        response.headers["X-Content-Type-Options"] = "nosniff"
        log.info("http_response", extra={"request_id": rid, "service": service, "instance": instance,
                 "method": request.method, "route": route, "status": response.status_code, "duration_s": elapsed})
        return response

    @app.get("/readyz", include_in_schema=False)
    def ready():
        try:
            if app.state.draining:
                raise RuntimeError("draining")
            with app.state.pool.connection() as conn:
                check_ready(conn)
            if service == "chat":
                app.state.admission.require_ready()
                if not app.state.worker.healthy() or app.state.worker.draining:
                    raise RuntimeError("worker_unhealthy")
            return {"ready": True, "service": service, "generation": app.state.phase_config.provider != "disabled" if service == "chat" else False}
        except Exception:
            return JSONResponse({"ready": False, "service": service}, status_code=503)

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        stats = app.state.pool.get_stats()
        pool_used.set(stats.get("pool_size", 0) - stats.get("pool_available", 0))
        if service == "chat":
            with app.state.pool.connection() as conn:
                counts = {r["status"]: r["n"] for r in conn.execute("select status,count(*) n from ai_turn group by status")}
                for status in ("queued", "running", "completed", "failed", "cancelled", "interrupted"):
                    terminals.labels(status).set(counts.get(status, 0))
                queue.set(counts.get("queued", 0))
                slots.set(conn.execute("select count(*) n from ai_model_call where ended_at is null").fetchone()["n"])
                quarantine.set(conn.execute("select count(*) n from ai_model_call where ended_at is null and quarantined").fetchone()["n"])
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
