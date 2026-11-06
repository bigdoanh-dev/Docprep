# Nguồn và ma trận chuyển đổi YHDP

Nguồn cố định: `sync/yhdp-frontend-api-v1` → `c6615866028162b21c81ebc0a9939ab71e9ebed0`. Baseline Phase 1: checkpoint `1ee42fe`. Nhánh triển khai `feat/phase1-yhdp-integration`. Không merge nguyên nhánh nguồn vì backend, auth, database và streaming khác contract Phase 1.

## Khôi phục các sửa UI trong lịch sử nhánh nguồn

Đối chiếu lại remote ngày 06/11/2026: đầu nhánh nguồn là `e9e3af7` (chỉ thêm README sau `c661586`). Tuy nhiên **không thể suy ra đã giữ đủ sửa UI chỉ từ khoảng diff này**: snapshot `965d5b3` đã ghi đè một phần các sửa trước đó ở `aeef651` và `18ac4cf`.

Đã ghép lại các sửa trích dẫn/mobile từ hai commit này lên bản tích hợp sau `45b9565`: onboarding có tiến trình, hồ sơ gọn, ẩn navigation/launcher AI và khóa học phần chưa khả dụng; giải thích thu gọn, gom nguồn trùng, thông báo đánh giá/phản ánh; lịch theo ngày chọn, khôi phục kế hoạch và giới hạn thẻ trong demo. Giữ layout Home mới, activation/token/SSE, dữ liệu học/thi server và các thông báo tính năng chưa hỗ trợ của Phase 1. Không đưa workflow/bộ dữ liệu nghiệp vụ 54 vấn đề hoặc SQLite vào backend để phục vụ thay đổi UI.

Các giới hạn thẻ và kế hoạch chỉ lưu local được ghi rõ cho demo; UI live nói đúng lịch ôn do server tính. Backend/API/schema không thay đổi trong bản sửa UI này. Kiểm chứng mới nằm cuối [báo cáo](yhdp-verification.md).

## Mã tái sử dụng

| Nguồn YHDP | Đích Phase 1 | Thay đổi tại ranh giới |
|---|---|---|
| UI Home/chat/Answer/ChatTurn/cards và styles | `src/features`, `src/components`, `src/styles` | Giữ activation/access-refresh, server data, SSE/idempotency/resume/cancel; chủ đề từ `/home`, không gọi recommendations API không có |
| `backend/yhdp/llm` và settings | `backend/app/ollama_gateway.py` | HTTP non-streaming, không raw prompt/output log, không transport retry/cache/replay; lỗi không xác định giữ quarantine |
| `backend/yhdp/dictionary.py` | `app/content_tools/dictionary.py` | Chỉ normalization/alias matching/conflict checks; bỏ settings và reviewer file writes |
| `ingest/model.py`, `ingest/chunk.py` | `app/content_tools/model.py`, `chunk.py` | Versioned pure contract, giữ section/source/review flags; caller cung cấp token counter, không tự tải tokenizer/model; chưa nối importer |
| Ý tưởng hash/version embedding và RRF | `app/repo/embeddings.py`, worker, migration 0015 | PostgreSQL/pgvector thay SQLite/file; model digest/corpus/content SHA-256, index và query embedding qua global reservation |
| Bộ test frontend | `tests/*.test.ts` | Bổ sung vào bộ hiện có; giữ Playwright và acceptance Phase 1 |

Không mang corpus chuyên môn của nhánh nguồn sang làm corpus đã duyệt. Không tự map `de_muc/van_de` sang module/unit từ thứ tự/tên. Pure chunker giữ legacy hash cho artifact chuẩn bị; **không dùng hash đó như chữ ký an toàn**. Index đang phục vụ dùng SHA-256 trên passage text/context; corpus ký số là cổng triển khai riêng.

## Đối chiếu 23 operations chính của nguồn

Path dưới đây bỏ prefix nguồn `/api/v1`; alias `/api` của YHDP không trở thành API song song. Các đường đích luôn dưới `/v1`, frontend dùng `/api/v1`. Đây là mapping trách nhiệm/ngữ nghĩa, không phải đổi tên URL máy móc.

| Method/path nguồn | Hợp đồng đích hoặc giới hạn | Runtime/quyền và nơi lưu |
|---|---|---|
| POST `/auth/login` | `/auth/activate` learner; `/auth/staff/login` staff; refresh/logout giữ Phase 1 | Business; token/session PG, không dùng JWT learner/reviewer 12 giờ nguồn |
| GET `/me` | `/me` (GET/PATCH) | Business; principal/role, identity chỉ Business |
| GET `/meta` | `/modules`, nội dung unit hiện có | Business; mapping nội dung YHDP cần duyệt riêng |
| GET `/mcq/practice` | `/session/today/practice`, `/units/{id}/next`, bộ câu được server cấp | Business; learner+consent, PG |
| POST `/mcq/answer` | `/units/{id}/responses`, `/practice-sets/{id}/responses` | Business; transaction response/mastery/card/activity, idempotency |
| GET `/mcq/mastery` | `/progress/skills` | Business; mastery PG của learner |
| GET `/deck` | `/decks` | Business; số thẻ/lịch ôn PG |
| GET `/deck/next` | `/cards/due` | Business; due time server |
| POST `/deck/{card_id}/review` | `/cards/{card_id}/reviews` | Business; ownership, idempotency và FSRS server |
| DELETE `/deck/{card_id}` | Không chuyển delete; giữ PATCH `/cards/{id}` với suspended | Business; ngữ nghĩa Phase 1 là tạm ẩn, UI nói đúng hành vi |
| POST `/mcq/sets` | Không mở luyện tự chọn mới; dùng phiên học/bộ câu server cấp hoặc exam form | Business; UI live ghi chưa hỗ trợ |
| GET `/mcq/sets` | `/exams` cho form thi, `/session/today` cho phiên học | Business; không coi practice/exam là cùng nghiệp vụ |
| GET `/mcq/sets/{set_id}` | `/attempts/{id}` hoặc `/practice-sets/{id}` tùy nghiệp vụ | Business; quyền sở hữu, đáp án thi autosave PG |
| POST `/mcq/sets/{set_id}/submit` | `/attempts/{id}/submit` cho thi; complete bộ luyện theo contract hiện có | Business; deadline server, chấm một lần, không dùng browser để giữ bài trước submit |
| POST `/mcq/items/{item_id}/flag` | `/reports` | Business; giữ contract/giới hạn 501 hiện có |
| GET `/mcq/stats` | `/progress/skills`, `/admin/dashboard/*` theo role | Business; dashboard giữ ẩn nhóm nhỏ và nhãn synthetic |
| POST `/chat` | `/chat/sessions`, `/chat/sessions/{id}/messages`, turn snapshot/events/cancel | Chat; learner+consent+ownership+exam guard, PG turn/outbox/history, Redis events; SSE thay NDJSON |
| GET `/files/{doc_id}/figures/{name}` | Không mở file serving tùy ý; `/passages/{id}` cho citation hiện có | Chat; nguồn PG; corpus/file release riêng chưa triển khai |
| POST `/review/mcq/{item_id}` | Chưa chuyển UI reviewer hoặc map reviewer thành admin/viewer | Chờ role content-team/quy trình duyệt riêng |
| GET `/review/stats` | Chưa chuyển | Chờ content-team, không đọc learner theo reviewer nguồn |
| GET `/review/next` | Chưa chuyển | Chờ corpus/review pipeline |
| POST `/review/tag/{item_id}` | Chưa chuyển | Chờ duyệt nội dung và versioned release |
| POST `/review/dictionary/{item_id}` | Chưa chuyển file writes từ reviewer | Chỉ port pure dictionary, không mở publication bypass |

## Hợp đồng và dữ liệu đích

[Ma trận API Phase 1](api-matrix.md) liệt kê toàn bộ **59 operations** và runtime sở hữu. OpenAPI tổng hợp kiểm tra operation trùng/schema xung đột; mỗi app chỉ xuất phần mình phục vụ. Không thêm endpoint public cho index/corpus/model credentials.

- Business: auth/consent/học/ôn/thi/tiến độ/dashboard và accept suggestion. Không gateway, không model env; không được đọc/ghi ai_model_call hoặc embedding index.
- Chat: sessions/messages/citations/rating/chat/hint/explain/turns. Đọc tối thiểu auth/consent/exam/content; không đọc learner_identity hoặc ghi learning/card/exam. Được ghi bảng embedding dẫn xuất.
- Browser: UI, preferences, draft và cursor/idempotency reconnect. Đáp án/điểm/deadline/scheduling/progress/history/consent bền vững thuộc server.
- Model: chỉ nhận nội dung cần thiết và nguồn được phép sau privacy checks; không token/IP/bí danh/session ID. Bộ lọc theo mẫu không bảo đảm phát hiện mọi PII.

Thay đổi additive: Home có days_to_exam/resume/tutor_topics; DueCard có practice_set_id tùy chọn (runtime hiện không tự cấp kiểu thẻ này); NewChatMessage có mode mặc định auto; stored/final có mode; status thêm retrieving. Các mode tạo/chấm quiz mới bị chặn 501. Không nhận context/citations do browser tự cung cấp cho followup.
