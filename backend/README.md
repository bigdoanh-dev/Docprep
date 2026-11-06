# YHDP backend

This directory is the Python backend for the YHDP frontend. It runs on the application server with SQLite, the private source corpus, and Ollama. The frontend calls FastAPI at `/api/v1`; it must never connect to Ollama directly.

The backend API route inventory is in [`../docs/backend-api.md`](../docs/backend-api.md). The deployment runbook is in [`docs/deployment.md`](docs/deployment.md).

## LLM and embedding endpoint

Ollama runs on the same server as this backend. Keep it bound to loopback and use:

```dotenv
YHDP_OLLAMA_URL=http://127.0.0.1:11434
YHDP_LLM_MODEL=qwen3.5:9b-q4_K_M
YHDP_VLM_MODEL=qwen3.5:9b-q4_K_M
YHDP_EMBED_MODEL=bge-m3
```

`YHDP_OLLAMA_URL` is the backend-to-Ollama address. The browser only connects to the HTTPS FastAPI origin. If Ollama is deliberately hosted on a different private machine, set `YHDP_OLLAMA_URL` to that machine's private, firewall-restricted address; never expose the Ollama port to the public internet.

## Server setup

Requirements: Python 3.12+, `uv`, and Ollama installed on the server.

```bash
uv sync
cp .env.example .env
```

Edit `.env` and set the deployed frontend's exact origin(s):

```dotenv
YHDP_SERVE_FRONTENDS=false
YHDP_CORS_ORIGINS=["https://your-frontend.example"]
```

Start Ollama and pull the configured models:

```bash
ollama serve
ollama pull qwen3.5:9b-q4_K_M
ollama pull bge-m3
```

Provision the source documents privately under `sources/` on the server. They are intentionally not included in this repository. Then build the local index if it is not already provisioned:

```bash
uv run yhdp sources
uv run yhdp ingest parse all
uv run yhdp ingest chunk all
uv run yhdp index
```

Start FastAPI behind a TLS-terminating reverse proxy:

```bash
uv run yhdp serve --host 127.0.0.1 --port 8765
```

The proxy should pass `/api/v1` to FastAPI. Use `/healthz` for process liveness. Create accounts on the server with `uv run yhdp user add <name> --role learner` or `--role reviewer`.

## Test harness

The repository includes deterministic unit/API tests and Ruff checks:

```bash
uv run pytest -q
uv run ruff check yhdp tests
```

Tests that require the real source corpus are skipped when the corpus has not been provisioned. The test harness does not need Ollama. Do not copy the live database, `.env`, JWT secret, source documents, derived OCR/chunk data, or model logs into this repository.
