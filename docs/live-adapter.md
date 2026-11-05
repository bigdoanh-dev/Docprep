# Live mode on this repo's backend

The screens were designed against the `/v1` contract in
[handoffs/mobile-backend-handoff.md](handoffs/mobile-backend-handoff.md). This backend
(`uv run yhdp serve`) has a smaller `/api` surface, so live mode goes through an adapter in
[`src/lib/live/`](../src/lib/live/): `api.ts` and `sse.ts` hand every learner call to it, as they
hand demo calls to `lib/demo/store.ts`. The screens are unchanged apart from the few noted below.

| File | Role |
| --- | --- |
| `backend.ts` | Authenticated `/api` calls; FastAPI errors → Vietnamese `LiveError` |
| `adapter.ts` | The `/v1` router: each path becomes one or more `/api` calls, reshaped |
| `chat.ts` | Hỏi đáp: local sessions; `/api/chat` NDJSON → `step`/`answer`/`final` events |
| `shapes.ts` | Items, feedback, citations, passages, times |
| `store.ts` | What is kept on the device, per learner (below) |

## How the two models meet

| Screen concept | Backend |
| --- | --- |
| Sign-in | `POST /api/auth/login`, username + password (`yhdp user add`). Any role studies as a learner; one 12 h token, no refresh |
| Học phần `g{n}` | Đề mục *n* of QĐ 51 (`/api/meta`); units are the vấn đề that have bank items |
| Chủ đề `vd{n}` | A run of 5 adaptive questions on vấn đề *n* (`/api/mcq/practice?van_de=`); done when mastery ≥ 0.6 over ≥ 3 answers |
| Bộ câu / today's practice | Distinct items from `/api/mcq/practice`, graded one at a time by `/api/mcq/answer` |
| Thẻ ôn | `/api/deck/next`, one card at a time. A concept card is answered as a fresh question (a one-item set, which reviews it); a flash/recall card takes a rating (1 → again, 2 → hard, 3–4 → good). "Tạm ẩn" deletes, since the deck has no suspended state |
| Thi thử | Mock sets of 10/30/60 (`/api/mcq/sets`), 1 minute per question; answers saved on the device until submit; an expired attempt is submitted when next seen |
| Tiến độ | `/api/mcq/mastery`, submitted set reports, `/api/deck`; study minutes from the device's activity log |
| Báo lỗi | Questions only: `/api/mcq/items/{id}/flag`; other targets answer 501 |
| Gia sư AI | `/api/chat` with a tutor move (`mode`: explain, compare, worked example, quiz me → grade, summarise; see `yhdp/api/tutor.py`). Chips under the latest answer pick a move; the reply to a quiz question is graded on that question's sources |

## Kept on the device, not the server

Unit runs, practice sets, exam answers before submission, chat sessions and messages, profile
settings (`PATCH /me`), source passages already seen (so citations reopen), and the activity log
behind the study-time charts. Answers, mastery, cards and submitted exams are on the server and
survive a cleared browser; the rest does not, and does not follow the learner to another device.

## Not available in live mode

Staff sign-in and everything under `/quan-ly`, `/quan-tri` (dashboard, CSV import); consent
records (the gate passes); account deletion (501); recall rate, memory curve and recall by module
(no review history endpoint). Demo mode still shows all of these with sample data.
