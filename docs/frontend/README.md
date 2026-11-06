# Frontend

The frontend is the React + TypeScript application at the repository root. This branch has one frontend app; it does not have separate `web/` or `web-review/` projects. The app is built as static assets with Vite and can be deployed independently of the Python backend.

## Structure

- `src/app/`: application shell, routing, and identity setup.
- `src/features/`: user-facing areas such as authentication, chat, learning, exams, progress, and management.
- `src/components/`: reusable UI components shared by features.
- `src/lib/`: API clients, session handling, live adapters, and shared utilities.
- `src/styles/`: global and feature styling.
- `public/`: static files copied into the production build.
- `tests/`: frontend unit and integration-oriented tests.
- `design-preview/`: standalone design preview; it is not the application entry point.

## Local development

Requirements: Node.js and npm. From the repository root:

```bash
npm ci
npm run dev
```

Vite serves the app at <http://127.0.0.1:5190>. API requests use relative `/api/v1` paths. During development, Vite proxies `/api` and `/review` to the backend, defaulting to `http://127.0.0.1:8000`.

To use another local backend address, set `BACKEND_URL` in the environment or create a root `.env.local`:

```dotenv
BACKEND_URL=http://127.0.0.1:8000
```

Start the backend separately; see [backend setup](../../backend/README.md). Do not put Ollama URLs, model configuration, or server secrets in frontend environment files. The browser must call FastAPI, and FastAPI calls Ollama.

## Scripts

Run from the repository root:

```bash
npm run dev       # Vite development server
npm test          # frontend tests
npm run lint      # lint src/
npm run build     # TypeScript project build and Vite production bundle
npm run preview   # preview the built bundle locally
```

`npm run build` writes the static bundle to `dist/`. Vite's development proxy is local-only; production hosting must provide a route from `/api/v1` to the backend or the app must be adapted to use a configured API origin.

## Backend integration

The frontend API uses `/api/v1`. See the [API route and stream inventory](../backend-api.md) for authentication, endpoints, and NDJSON chat events.

For production, choose one of these arrangements:

1. Host the frontend and backend API under one public origin, routing `/api/v1` to FastAPI through a TLS-terminating reverse proxy.
2. Host them on separate origins and configure the frontend API origin as part of the integration. Then allow the exact frontend origin in backend `YHDP_CORS_ORIGINS`.

Allowing CORS alone does not change the frontend's relative API URLs. The frontend should never connect directly to Ollama.
