# YHDP backend API

This frontend is intended to connect to the YHDP backend running on the private application server. The backend API base path is `/api/v1`. The reviewer endpoints and learner endpoints are served by the same FastAPI application.

The current frontend uses relative `/api/v1` URLs. For a separate static host, either proxy that path to the backend under the frontend's origin or add/configure an API origin in the frontend during integration. Merely allowing CORS on the backend does not change where the browser sends relative URLs.

The backend currently disables generated OpenAPI docs. This page is the route inventory for the running API; confirm request/response details against the implementation when integrating a client.

## Connection and authentication

- Configure the frontend's API origin to the public HTTPS origin of the backend, or route `/api` from the frontend origin to that server.
- For cross-origin browser requests, the backend must allow the exact frontend origin in `YHDP_CORS_ORIGINS`.
- All `/api/v1` routes require `Authorization: Bearer <token>` except `POST /api/v1/auth/login`.
- Login returns `{ "token", "username", "role" }`. The bearer token is a 12-hour HS256 JWT.
- Reviewer routes require the `reviewer` role. Other authenticated routes are available to learners and reviewers.
- Figure requests use the token in the `t` query parameter because browser image elements cannot attach an authorization header. Avoid logging these URLs.
- The previous `/api/...` paths remain aliases for compatibility. New clients should use `/api/v1/...`.

## Routes

| Method | Path | Access | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/auth/login` | Public | Sign in with `{ "username", "password" }`. |
| `GET` | `/api/v1/me` | Authenticated | Return the signed-in username and role. |
| `GET` | `/api/v1/meta` | Authenticated | Blueprint, domains, Bloom levels, dictionary terms, populations, and indexed documents. |
| `POST` | `/api/v1/chat` | Authenticated | Cited tutor response as newline-delimited JSON (NDJSON); see streaming events below. |
| `GET` | `/api/v1/mcq/practice?de_muc={id}&van_de={id}` | Authenticated | Fetch the next eligible practice item and due-card count. Filters are optional. |
| `POST` | `/api/v1/mcq/answer` | Authenticated | Submit `{ "item_id", "chosen", "seconds?", "confidence?", "card_id?" }`. |
| `GET` | `/api/v1/mcq/mastery` | Authenticated | Learner mastery report. |
| `GET` | `/api/v1/mcq/stats` | Authenticated | MCQ-bank statistics. |
| `POST` | `/api/v1/mcq/sets` | Authenticated | Create a timed or untimed set: `{ "size": 10 \| 30 \| 60, "timed?": true }`. |
| `GET` | `/api/v1/mcq/sets` | Authenticated | List the signed-in user's sets. |
| `GET` | `/api/v1/mcq/sets/{set_id}` | Authenticated | Get a set and its items. |
| `POST` | `/api/v1/mcq/sets/{set_id}/submit` | Authenticated | Submit `{ "answers": { "<item_id>": "<option \| null>" }, "seconds?" }`. |
| `POST` | `/api/v1/mcq/items/{item_id}/flag` | Authenticated | Flag an item with `{ "reason" }`. |
| `GET` | `/api/v1/deck` | Authenticated | List the signed-in user's revision cards. |
| `GET` | `/api/v1/deck/next` | Authenticated | Get the next due card and due count. |
| `POST` | `/api/v1/deck/{card_id}/review` | Authenticated | Review a card with `{ "rating": "again" \| "hard" \| "good", "item_id?" }`. |
| `DELETE` | `/api/v1/deck/{card_id}` | Authenticated | Delete a revision card owned by the signed-in user. |
| `GET` | `/api/v1/review/stats` | Reviewer | Reviewer queue and review statistics. |
| `GET` | `/api/v1/review/next?kind=tag\|dictionary\|mcq&doc={doc_id}` | Reviewer | Fetch the next item of the requested queue. `kind` defaults to `tag`; `doc` filters tag items. |
| `POST` | `/api/v1/review/mcq/{item_id}` | Reviewer | Decide an MCQ with `{ "action": "approve" \| "reject", "note?": "" }`. |
| `POST` | `/api/v1/review/tag/{item_id}` | Reviewer | Decide a tag with `{ "action": "accept" \| "save" \| "skip", "edit?" }`. |
| `POST` | `/api/v1/review/dictionary/{item_id}` | Reviewer | Apply a dictionary decision (`new_term`, `add_alias`, `reject`, or `skip`). |
| `GET` | `/api/v1/files/{doc_id}/figures/{name}?t={token}` | Authenticated | Read an extracted figure using the query-token exception described above. |
| `GET` | `/healthz` | Public | Process liveness only; it does not check the database, Ollama, or index readiness. |

Most request validation errors use FastAPI's `422` response; missing records return `404`, unauthenticated requests `401`, and learner access to reviewer routes `403`. Login failures are rate-limited per client address and username.

## Chat stream

Send a JSON body containing `question` (1–2000 characters), and optionally `history`, `context` (up to 10 chunk IDs), `k` (1–10, default 6), and `mode`. The response content type is `application/x-ndjson`; consume one JSON object per line. Events include:

- `plan`: selected sections and retrieval aspect for synthesis/comparison.
- `sources`: evidence passages and citations.
- `delta`: streamed answer text.
- `tool`: result of an explicitly requested quiz/card action.
- `done`: citation validation and completion metadata.
- `suggestions`: optional follow-up questions.
- `error`: stream-time error details.

The frontend must handle streams that end after `done` without a `suggestions` event. Chat history and learner UI state are currently client-side.
