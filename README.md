# Docprep / YHDP

Docprep is the repository for the YHDP study application. It contains a React frontend and a Python/FastAPI backend in one repository. The backend is a modular monolith; the browser frontend is a separately buildable static app.

The backend serves the `/api/v1` API and calls Ollama for model inference. The browser talks only to the backend API—not directly to Ollama. In production, the frontend can be hosted separately, while the API, database, source documents, and Ollama remain on private server infrastructure.

## Repository layout

```text
.
├── src/                 React + TypeScript frontend
│   ├── app/             App shell and identity
│   ├── components/      Shared UI components
│   ├── features/        Auth, chat, learning, exams, management, and other features
│   ├── lib/             API clients, sessions, and shared utilities
│   └── styles/          Global and feature styling
├── public/              Static frontend assets
├── tests/               Frontend tests
├── backend/
│   ├── yhdp/            Python application and FastAPI API
│   ├── tests/           Backend tests
│   ├── data/            Checked-in blueprints, source registry, and dictionary data
│   ├── docs/            Backend deployment guide
│   └── pyproject.toml   Python project and dependencies
├── docs/                API, integration, and handoff documentation
├── design-preview/      Standalone visual/design preview
└── package.json         Frontend scripts and dependencies
```

The frontend is at the repository root; there are no separate `web/` and `web-review/` apps on this branch. The backend's feature modules (API, ingestion, MCQs, and storage) run together as one application.

## Quick start

### Frontend

Requirements: Node.js and npm.

```bash
npm ci
npm run dev
```

Vite starts at <http://127.0.0.1:5190>. The development server proxies `/api` and `/review` to the backend. It defaults to `http://127.0.0.1:8000`; override that target with `BACKEND_URL` in the environment or the root `.env.local` file:

```dotenv
BACKEND_URL=http://127.0.0.1:8000
```

More frontend structure, workflows, and integration notes are in the [frontend README](docs/frontend/README.md).

### Backend

Requirements: Python 3.12+, [`uv`](https://docs.astral.sh/uv/), and Ollama. From the repository root:

```bash
cd backend
uv sync
cp .env.example .env
uv run yhdp serve --host 127.0.0.1 --port 8000
```

Provision authorized source documents privately before building the document index. Do not commit source files, the live database, generated indexes, or secrets. The complete setup, index-building, user-account, and LLM instructions are in the [backend README](backend/README.md).

For local development, set `YHDP_OLLAMA_URL` in `backend/.env` to the Ollama base URL reachable from the backend. If the backend and Ollama run on different machines, use Ollama's private network address and restrict port `11434` to the backend host. Never expose Ollama to the browser or public internet.

## Common checks

Run these from the repository root:

```bash
npm test
npm run lint
npm run build
```

Run backend checks from `backend/`:

```bash
uv run pytest -q
uv run ruff check yhdp tests
```

Backend tests do not require Ollama; tests that need the private source corpus are skipped until that corpus is provisioned.

## API and deployment

- [Backend API routes, authentication, and chat stream](docs/backend-api.md)
- [Backend deployment and modular-monolith boundaries](backend/docs/deployment.md)
- [Frontend developer and integration guide](docs/frontend/README.md)

The frontend uses same-origin `/api/v1` URLs. In production, route those requests to the backend through a same-origin reverse proxy, or configure an API origin when adapting the frontend for a separate API domain. For cross-origin requests, configure the backend's exact `YHDP_CORS_ORIGINS`; CORS does not redirect API requests.
