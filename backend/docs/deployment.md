# Deployment

## Runtime shape

YHDP is a modular monolith on one server: FastAPI, Ollama, SQLite, source files and derived indexes stay together. The learner/reviewer web apps are built and deployed separately from the [Docprep frontend repository](https://github.com/bigdoanh-dev/Docprep) as static assets.

```text
Browser ── HTTPS ── static frontend hosting
   │
   └────── HTTPS API requests ── reverse proxy ── FastAPI ── SQLite / local files
                                                        └── Ollama (loopback only)
```

Ingestion and maintenance remain CLI jobs on the server and use the same domain code, database and settings as the API. Do not deploy the LLM, database, or source corpus to the static frontend host.

## Server configuration

1. Install the backend with Python 3.12+ and `uv`; install and start Ollama on the server.
2. Set `YHDP_SERVE_FRONTENDS=false` so the backend does not register SPA routes or depend on frontend build artifacts.
3. Set `YHDP_CORS_ORIGINS` to a JSON array containing only the deployed frontend origin(s), e.g. `["https://study.example.com"]`. Do not use `*` in production.
4. Keep FastAPI bound to loopback behind a TLS-terminating reverse proxy. Keep Ollama bound to loopback and do not proxy its port publicly.
5. Persist and back up `data/yhdp.db`, `data/.jwt_secret`, `data/derived/`, and any required source files. Back up SQLite using its online backup API or a SQLite-aware tool so WAL data is included.
6. Configure a service manager to restart FastAPI and Ollama after failures/reboots. Use `/healthz` for process liveness; it does not check SQLite, Ollama, or index readiness.
7. Create learner/reviewer accounts with `uv run yhdp user add ...` on the server.

The backend's CORS allowlist enables cross-origin browser requests; it does not configure the frontend API URL. Configure the frontend build with the public HTTPS API base URL, or route `/api` through the same public origin as the static site. API routes are versioned under `/api/v1`; existing `/api/...` routes remain compatibility aliases during migration.

## Local combined mode

For development, `YHDP_SERVE_FRONTENDS` defaults to `true`. Build the local apps with `make web`; FastAPI then serves the learner app at `/` and the reviewer app at `/review/`. Vite's development proxy remains a local-only convenience and is not the production routing layer.

## Internal module boundaries

Keep the backend a modular monolith. Existing feature modules (`ingest/`, `mcq/`, `store/`, and `api/`) remain in one Python package and deploy as one process. `api/app.py` assembles the application, `api/dependencies.py` owns shared request dependencies, and `api/routes/` groups HTTP endpoints by feature. Keep business workflows in reusable feature/application modules and database/model/filesystem details behind the existing infrastructure modules. CLI commands and HTTP handlers should call the same workflows rather than recreating them.

Avoid adding services, queues, or databases until measurements show the single-server design is a bottleneck. The API and frontend can be released independently without splitting the backend into network services.
