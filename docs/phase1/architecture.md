# Kiến trúc Phase 1 — tách runtime và điều phối

Tài liệu này mô tả đợt nâng cấp hạ tầng từ Alpha, theo các lựa chọn đã thống nhất với người phụ trách dự án ngày 03/11/2026. Căn cứ định hướng là `AIRC_Kien_truc_backend_Alpha_V1_den_Phase_1.docx`. PDF gốc được Word dẫn bằng N1 chưa được cung cấp để đối chiếu. Kết quả thực thi nằm trong [verification.md](verification.md); thiết kế trong tài liệu không tự chứng minh đã nghiệm thu.

## Đơn vị triển khai

Frontend React → Caddy → Business API ×2 hoặc Chat Orchestrator ×2 → PostgreSQL.

Hai Chat instances cùng dùng Redis; mỗi instance có bộ worker hữu hạn do lifespan quản lý. Các bước retrieval/generate/postcheck vẫn là module nội bộ, không có thêm deployment cho từng bước. Business vẫn giữ transaction học/thi/ôn trong cùng ứng dụng. Một VPS/Redis/PostgreSQL vẫn là điểm lỗi đơn.

| Thành phần | Trách nhiệm |
|---|---|
| Business API | Auth, consent, hồ sơ, học, đáp án, thẻ, thi, tiến độ, dashboard, chấp nhận suggestion |
| Chat | Hội thoại, lịch sử, nguồn, rating, hint/explain, nhận turn, worker và SSE |
| Redis | FIFO dispatch, processing lease, learner lock, model reservations, event stream |
| PostgreSQL | Nghiệp vụ bền vững, turn/outbox, kết quả, ràng buộc chống lặp, model-call tombstone |
| Caddy | Static frontend, bỏ `/api`, routing, least connections, readiness và flush SSE |

Backend vẫn có entrypoint Alpha tại `app.main:app`; hai entrypoint mới là `app.main_business:app` và `app.main_chat:app`. Business không tạo gateway/worker/Redis client; Compose không chuyển model secrets cho Business.

## Quyền sở hữu API

| Đường dẫn backend | Chủ thể |
|---|---|
| `/v1/chat/suggestions/{id}/accept` | Business; rule này đứng trước rule Chat |
| Chat sessions/messages/turns, passages, message rating | Chat |
| `/v1/items/{id}/hint`, `/v1/items/{id}/explain` | Chat |
| `/v1/*` còn lại | Business |

Frontend tiếp tục gọi `/api/v1`; backend nhận `/v1`. Caddy đặt API trước SPA fallback. `/metrics`, `/readyz`, docs và OpenAPI không xuất qua proxy công khai. Mỗi app xuất hợp đồng của mình khi truy cập trong mạng nội bộ; `openapi.yaml` tại root là hợp đồng tổng hợp 59 operations. Alpha vẫn có 55 operations; bảy stub tiếp tục trả 501.

[Ma trận đầy đủ 59 operations](api-matrix.md) được tạo từ chính OpenAPI của hai ứng dụng. Đường dẫn sai dưới `/api`, kể cả thiếu `/v1`, luôn trả lỗi JSON thay vì trang SPA.

## Một turn đi qua hệ thống

1. Xác thực, kiểm tra consent/exam; làm sạch đầu vào trước ghi dữ liệu.
2. Khóa admission và learner trong PostgreSQL. Key đã dùng cùng payload gắn lại turn cũ; khác payload trả 409. Partial unique index bảo vệ một turn queued/running cho mỗi learner.
3. Lưu user message, turn và outbox trong cùng transaction. Gửi lại sau mất response không tạo message/turn mới.
4. Publisher đưa queued turns lên Redis theo `seq`. Lua claim lấy phần tử đầu FIFO và kiểm tra số turn đang chạy toàn cục.
5. Worker claim có owner/fencing token và heartbeat. Chuẩn bị nguồn bằng connection ngắn rồi nhả connection.
6. Mọi model call qua gateway wrapper: kiểm tra prompt, reserve slot Redis và lưu model-call record trước khi gọi provider. Hint cũng nhả connection trong lúc chờ.
7. Trước commit, kiểm tra lại tài khoản, consent, bài thi, deadline và fencing. Message, kết quả turn và trạng thái completed được commit trước event answer/final.
8. SSE subscriber đọc Redis Streams bằng async I/O; không giữ connection PostgreSQL hoặc thread pool trong lúc chờ event. Kết quả cuối có thể đọc lại từ DB nếu publish event thất bại.

FIFO áp dụng cho cấp lượt, không phải thứ tự xong. Các giới hạn 4 turn/4 scripted calls, 20 queued và 60 giây chờ trong template là cấu hình dev để tái lập; không phải thông số GPU hay năng lực đã đo.

## Hủy và phục hồi

`queued → running → completed / failed / cancelled / interrupted` là trạng thái xử lý. Bốn trạng thái nội dung AI hiện có chỉ áp dụng khi tạo kết quả nội dung thành công. Lỗi kỹ thuật không được đổi thành thiếu bằng chứng.

- Redis không AOF/RDB. Khi mất epoch, khóa phục hồi PostgreSQL chặn claim/admission trong lúc dựng lại dispatch, locks và model reservations. Outbox lặp an toàn.
- Worker chết trước durable invocation marker: có thể đưa lại queue nếu còn deadline. Khi đã có marker, kể cả khoảng hở ngay trước lời gọi thực tế, coi kết quả gọi là chưa chắc chắn: đánh dấu interrupted, không tự gọi lại.
- Model reservations không tự được trả chỉ vì lease hết hạn. Record `ai_model_call` tồn tại cả khi tài khoản/turn bị xóa; lời gọi chưa xác nhận dừng được cách ly. Chỉ giải phóng khi call thực sự trả về hoặc người vận hành xác nhận đã dừng.
- Bắt đầu thi, rút service consent, đóng/xóa learner hủy các turn liên quan trong transaction nghiệp vụ. Trigger và service dùng cùng thứ tự khóa learner. Quyền runtime không cho Chat sửa điểm/thẻ/bài thi.
- Ngắt SSE không hủy job. Có endpoint hủy rõ ràng. Hủy running turn ngăn công bố kết quả nhưng không giả định đã hủy lời gọi bên ngoài.
- Redis events có TTL và giới hạn độ dài; event hết hạn trả 410. Client đọc snapshot DB thay vì giả lập lại các bước đã mất.
- Khi worker cũ kết thúc, việc nhả dispatch lease cũng kiểm tra fence dưới khóa phục hồi; không xóa lease của worker đã nhận lại cùng turn.

## Contract SSE và frontend

POST chat/explain giữ `text/event-stream`; hint giữ JSON. Response bổ sung `X-Turn-ID`, request hỗ trợ `Idempotency-Key`. GET `/v1/chat/turns/active`, GET turn, GET turn/events và DELETE turn kiểm tra quyền sở hữu. Resume dùng bearer header và `Last-Event-ID`, không truyền token bằng URL.

SSE có `id:`, heartbeat, status/step/answer/final. `final` thêm turn_status và lỗi kỹ thuật; state/message_id có thể null khi không tạo answer. Frontend giữ key/cursor trong sessionStorage theo actor, retry hữu hạn, khôi phục turn sau reload, và thay cùng một answer view để chống hiển thị lặp.

## Dữ liệu và bảo mật

Giữ schema public và migrations cũ; thêm 0013/0014. Các role runtime không sở hữu bảng, không có CREATE schema/table. `phase_migrator` chạy DDL một lần theo release; `phase_owner` là tài khoản bootstrap/backup, không nằm trong môi trường API/Chat.

Chat được đọc các bảng cần cho xác thực, nguồn, kiểm tra trạng thái học/thi và suggestion; staff chỉ đọc id/role/active. Chat không đọc learner_identity, không ghi learning/exam/card. Business có quyền vòng đời nghiệp vụ nhưng không đọc/ghi ai_model_call. Trigger SECURITY DEFINER có search_path cố định và không cấp EXECUTE trực tiếp cho public.

Bộ lọc client/server che các mẫu email, điện thoại, số định danh, token, bí danh, IPv4 và UUID. Gateway kiểm tra lại prompt. Đây là giảm dữ liệu xác định theo mẫu, không phải bộ phát hiện mọi tên riêng/PII trong văn bản tự do. Chưa nghiệm thu chất lượng nội dung hoặc tính đúng đắn y khoa.

Logs chỉ chứa metadata và mã lỗi, không có body, prompt, token hoặc exception SQL/provider. Metrics không gắn nhãn learner/session/turn. PostgreSQL/Redis/backend/metrics không có host port trong Compose thường. Uvicorn chỉ tin IP Caddy được chỉ định; không dùng `*`.

## Ranh giới model và vận hành

Phase 1 chỉ chấp nhận provider disabled hoặc scripted trong dev/test. Không mặc định Anthropic, không external fallback, không dựng adapter HTTP khi chưa biết protocol. Mở GPU thật cần protocol, endpoint, model ID, chứng thực, timeout/cancel/health semantics, resource mapping và slot budget được Lead duyệt; sau đó phải kiểm thử lại.

Readiness khác liveness. Business kiểm tra DB/schema; Chat thêm Redis/worker. Generation disabled vẫn cho phép đọc lịch sử và trả lỗi rõ khi gọi AI. Metrics gồm HTTP headers latency, queue/deadline/state, pool và model reservations; không coi headers latency là toàn bộ thời gian SSE. Harness tải đo thời gian hoàn tất ở client.

Compose không tự rolling update. Script release drain một instance, chờ turn đang chạy, đợi proxy bỏ upstream rồi tạo lại container. Backup local mặc định mỗi 24 giờ trong profile operations, không tự xóa bản cũ; đây chưa phải RPO/RTO. Rollback chỉ dùng code tương thích schema; quay lại Alpha cũ cần restore DB riêng và kiểm tra trước khi đổi URL.

Tham chiếu cơ chế: [Caddy reverse_proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy), [Lua nguyên tử trong Redis](https://redis.io/docs/latest/develop/programmability/eval-intro/) và [quyền PostgreSQL 16](https://www.postgresql.org/docs/16/ddl-priv.html). Các lựa chọn cấu hình local phải được đo lại trước khi áp dụng cho hạ tầng thật.
