# YHDP backend

This is the Python backend for YHDP, a Graph RAG study assistant. It is deployed as a modular monolith: FastAPI, SQLite, private source documents, derived indexes, and Ollama run on the application server. The separately hosted browser frontend calls FastAPI at `/api/v1`; it must never call Ollama directly.

- [API route inventory and request details](../docs/backend-api.md)
- [Deployment runbook](docs/deployment.md)

## Setup

Requirements: Python 3.12+, [`uv`](https://docs.astral.sh/uv/), and [Ollama](https://ollama.com/) installed on the server.

From the repository root:

```bash
cd backend
uv sync
cp .env.example .env
```

Edit `.env` for the deployment. For static frontend hosting, configure the exact frontend origin(s):

```dotenv
YHDP_SERVE_FRONTENDS=false
YHDP_CORS_ORIGINS=["https://your-frontend.example"]
```

Keep the source `.docx` files out of Git. Provision approved documents privately under `backend/sources/` on the server; filenames must match `file_match` in `data/sources.yaml`. To build or refresh the local index:

```bash
uv run yhdp sources
uv run yhdp ingest parse all
uv run yhdp ingest chunk all
uv run yhdp index
```

Run Ollama as a server service, then start FastAPI behind a TLS-terminating reverse proxy:

```bash
uv run yhdp serve --host 127.0.0.1 --port 8765
```

The proxy should pass `/api/v1` to FastAPI and expose `/healthz` for process liveness. Create accounts on the server:

```bash
uv run yhdp user add learner-name --role learner
uv run yhdp user add reviewer-name --role reviewer
```

## LLM configuration

Ollama runs on the same server as the backend, bound to loopback. Configure the backend-to-Ollama URL and models in `backend/.env`:

```dotenv
YHDP_OLLAMA_URL=http://127.0.0.1:11434
YHDP_LLM_MODEL=qwen3.5:9b-q4_K_M
YHDP_VLM_MODEL=qwen3.5:9b-q4_K_M
YHDP_EMBED_MODEL=bge-m3
YHDP_LLM_NUM_CTX=16384
```

Install the configured models in Ollama:

```bash
ollama pull qwen3.5:9b-q4_K_M
ollama pull bge-m3
```

`YHDP_LLM_MODEL` is used for generated answers and other text tasks; `YHDP_VLM_MODEL` handles image/vision work; `YHDP_EMBED_MODEL` creates retrieval embeddings. If you change the embedding model, rebuild the index with `uv run yhdp index`. Keep Ollama private; never publish port `11434` or set the browser's API origin to Ollama. If Ollama is on a different machine, use only its private, firewall-restricted address for `YHDP_OLLAMA_URL`.

### Calling the LLM through YHDP

The application chat endpoint retrieves indexed evidence and returns a cited answer as newline-delimited JSON (NDJSON). First authenticate:

```bash
API=https://api.your-domain.example
TOKEN=$(curl -fsS "$API/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"learner-name","password":"your-password"}' | jq -r .token)
```

Then send a question. `curl -N` leaves the response stream unbuffered:

```bash
curl -N "$API/api/v1/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Tóm tắt các dấu hiệu cảnh báo sốt xuất huyết"}'
```

Each response line is a JSON event, such as `plan`, `sources`, `delta`, `done`, or `suggestions`. The `suggestions` event may be absent. Chat accepts `question` (1–2000 characters), optional `history`, up to 10 previous-answer `context` chunk IDs, `k` (1–10, default 6), and `mode` (default `auto`). Send bearer authentication with API requests except login and `/healthz`; figure requests also accept the `t` query-token documented in the API inventory. Reviewer routes require a reviewer account.

### Calling Ollama directly for diagnostics

Direct model calls are for server-side diagnostics only; normal frontend chat must go through the authenticated YHDP API above. From the application server:

```bash
curl -fsS http://127.0.0.1:11434/api/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qwen3.5:9b-q4_K_M",
    "stream": false,
    "messages": [{"role": "user", "content": "Reply with a short greeting."}]
  }'
```

Ollama's response contains the generated text at `.message.content`. This raw endpoint does not perform YHDP retrieval, citations, or application authentication.

## API overview

The API base path is `/api/v1`; legacy `/api/...` aliases remain available for compatibility. All routes below require a bearer token except login. `/healthz` is public.

| Area | Routes |
|---|---|
| Auth and metadata | `POST /auth/login`, `GET /me`, `GET /meta` |
| Tutor | `POST /chat` (streaming NDJSON) |
| Learner practice | `GET /mcq/practice`, `POST /mcq/answer`, `GET /mcq/mastery`, `GET /mcq/stats`, `POST /mcq/sets`, `GET /mcq/sets`, `GET /mcq/sets/{set_id}`, `POST /mcq/sets/{set_id}/submit`, `POST /mcq/items/{item_id}/flag` |
| Revision cards | `GET /deck`, `GET /deck/next`, `POST /deck/{card_id}/review`, `DELETE /deck/{card_id}` |
| Reviewer (reviewer role) | `GET /review/stats`, `GET /review/next`, `POST /review/mcq/{item_id}`, `POST /review/tag/{item_id}`, `POST /review/dictionary/{item_id}` |
| Figures | `GET /files/{doc_id}/figures/{name}` |
| Liveness | `GET /healthz` |

Use the [API route inventory](../docs/backend-api.md) for request bodies, filters, permissions, and chat event details. Generated OpenAPI docs are disabled in this deployment.

## Tests and lint

```bash
uv run pytest -q
uv run ruff check yhdp tests
```

The test harness does not need Ollama. Tests requiring the real source corpus are skipped until it is provisioned. Never commit `.env`, JWT secrets, source documents, the live database, derived OCR/chunk data, or LLM logs.
