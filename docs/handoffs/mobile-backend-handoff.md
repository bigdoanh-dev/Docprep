# Bàn giao backend — ứng dụng DocPrep mobile

**Ngày lập:** 25/10/2026  
**Nguồn đối chiếu:** nhánh `main`, commit `77b14a2` của `Docprep_FE`  
**Mục đích:** tổng hợp các luồng mobile và hợp đồng API mà frontend hiện gọi để backend đối chiếu, triển khai và kiểm thử tích hợp.

> Tài liệu này được suy ra từ mã frontend, chủ yếu ở [`src/app/App.tsx`](../../src/app/App.tsx), [`src/lib/api.ts`](../../src/lib/api.ts), [`src/lib/session.ts`](../../src/lib/session.ts) và các màn hình `src/features/`. Đây là yêu cầu phía client, không khẳng định endpoint nào đã được triển khai hoặc đang chạy ổn định trên backend.

## 1. Phạm vi ứng dụng

App là SPA React/Vite, thiết kế ưu tiên mobile. Các luồng hiện có:

- **Người học:** đăng nhập/kích hoạt, đồng ý điều khoản, chọn học phần, học nội dung, luyện câu hỏi, ôn thẻ, thi thử, hỏi đáp AI, tiến độ, nhịp học, hồ sơ và quyền dữ liệu.
- **Cán bộ/quản trị:** đăng nhập riêng, dashboard báo cáo, xuất báo cáo và luồng nhập CSV cấp tài khoản.
- **Trải nghiệm demo:** chạy bằng dữ liệu seed lưu ở trình duyệt; không gửi yêu cầu đến API backend.

Các component trong `src/features/review/` có gọi API thẩm định nhưng hiện **không được nối vào route của `App.tsx`**. Không xem các endpoint thẩm định là luồng mobile đang phát hành nếu chưa có quyết định nối route riêng.

## 2. Kết nối API và xác thực

### Base URL và môi trường

- Frontend gọi API qua `/api/v1` (`BASE` trong `src/lib/api.ts`).
- Khi chạy Vite local, `vite.config.ts` proxy `/api/*` tới `BACKEND_URL`, mặc định `http://127.0.0.1:8000`, đồng thời bỏ tiền tố `/api`. Ví dụ request trình duyệt `/api/v1/me` được chuyển thành backend `/v1/me`.
- `.env.example` hiện chỉ khai báo `BACKEND_URL`; không có URL backend production trong bundle frontend.
- `vercel.json` hiện rewrite mọi đường dẫn `/(.*)` về `/index.html` cho SPA. **Cần xác nhận cấu hình production có route `/api/v1/*` tới backend trước catch-all này.** Nếu không có rewrite/function/API proxy riêng, app production sẽ gọi API cùng origin và có nguy cơ nhận HTML của `index.html` thay vì JSON/SSE.

### Luồng đăng nhập

| Endpoint backend            | Body                                               | Phản hồi client cần                                                                  |
| --------------------------- | -------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `POST /v1/auth/activate`    | `{ "code": "…", "device": { "platform": "web" } }` | `access_token`, `refresh_token`, `expires_in`, `role`, `consent_required`            |
| `POST /v1/auth/staff/login` | `{ "email": "…", "password": "…" }`                | Cùng `TokenPair`; role phải thuộc phạm vi app mobile: `admin` hoặc `ministry_viewer` |
| `POST /v1/auth/refresh`     | `{ "refresh_token": "…" }`                         | Token mới `{ "access_token": "…", "refresh_token": "…" }`                            |
| `POST /v1/auth/logout`      | JSON rỗng `{}`                                     | Client không dùng body phản hồi; luôn xóa token cục bộ sau khi gọi                   |

- Request có đăng nhập gửi `Authorization: Bearer <access_token>`.
- Learner và staff dùng hai kho token độc lập (`yhdp.session`, `yhdp.staff`). Client gửi refresh một lần khi server trả `401` với `error.code = "token_expired"`; refresh token xoay vòng và các tab được tuần tự hóa refresh.
- `401` khác hoặc refresh bị từ chối sẽ kết thúc phiên phía client. Lỗi mạng/server khi refresh không tự xóa token.
- Route yêu cầu đăng nhập đưa khách chưa đăng nhập tới `/dang-nhap`; khi đăng nhập xong, app quay lại URL người dùng đã yêu cầu. Quyền truy cập phải được backend kiểm tra theo token/role; `actor` trong localStorage chỉ là trạng thái giao diện.
- Role `reviewer` hiện bị màn đăng nhập mobile từ chối và hướng sang giao diện web. `lecturer` chưa có luồng đăng nhập mobile.

### Chuẩn phản hồi lỗi

Frontend đọc lỗi theo cấu trúc:

```json
{
  "error": {
    "code": "machine_readable_code",
    "message_vi": "Thông báo tiếng Việt cho người dùng"
  }
}
```

- `403` + `error.code = "consent_required"`: app mở màn đồng ý dịch vụ.
- `401` + `error.code = "token_expired"`: app thử refresh một lần.
- Một số luồng phân biệt `404`, `409`, `501` theo nghiệp vụ; cần giữ `code` ổn định, không chỉ trả message.
- Endpoint danh sách trả envelope `{ "items": [...] }`; phân trang hội thoại dùng thêm `next_cursor`.
- Trường dữ liệu chưa áp dụng/không được phép suy ra phải trả `null` nếu kiểu frontend định nghĩa nullable; tránh thay bằng `0` làm sai ý nghĩa “chưa có dữ liệu”.

## 3. Luồng màn hình và API

| Màn hình/luồng           | API chính                                                                                                        | Mục đích                                                                           |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| Đăng nhập/kích hoạt      | `/auth/activate`, `/auth/staff/login`, `/auth/refresh`, `/auth/logout`                                           | Tạo và duy trì phiên learner/staff                                                 |
| Đồng ý                   | `/consent/current`, `/consent`, `DELETE /consent`                                                                | Đồng ý dịch vụ bắt buộc, nghiên cứu tùy chọn; rút từng loại đồng ý                 |
| Trang chủ                | `/home`, `/session/today`                                                                                        | Thẻ đến hạn, đề thi tiếp theo, gợi ý AI, hoạt động gần đây và phiên học trong ngày |
| Chọn trọng tâm           | `/modules`, `/me`, `PATCH /me`                                                                                   | Chọn học phần ưu tiên và bỏ qua lời nhắc chẩn đoán sau khi đã chọn                 |
| Học tập/học phần         | `/modules`, `/modules/{id}`, `/units/{id}/next`, `/units/{id}/responses`, `/units/{id}/advance`                  | Danh mục, bài học, nội dung/câu hỏi và tiến độ từng unit                           |
| Luyện tập                | `/practice-sets`, `/practice-sets/{id}`, `…/responses`, `…/complete`                                             | Tạo bộ luyện, trả lời, nhận phản hồi và tổng kết điều chỉnh                        |
| Phiên học hôm nay        | `/session/today`, `/session/today/practice`, `/cards/due` và các API trên                                        | Kết hợp ôn thẻ, luyện điểm yếu, học tiếp; số bước có thể ít hơn ba                 |
| Bộ thẻ/ôn thẻ            | `/decks`, `/cards/due`, `/cards/{id}/reviews`, `PATCH /cards/{id}`                                               | Số thẻ mới/đang học/đến hạn, chấm mức nhớ, tạm dừng thẻ                            |
| Thi thử                  | `/exams`, `/exams/{id}/attempts`, `/attempts/{id}`, `…/answers/{question_id}`, `…/submit`, `…/results`           | Danh sách đề, tạo/tiếp tục lượt thi, lưu đáp án, nộp và xem lại                    |
| AI — Hỏi đáp             | `/chat/sessions`, `/chat/sessions/{id}/messages` (SSE), `/messages/{id}/rating`, `/chat/suggestions/{id}/accept` | Hội thoại có lưu lịch sử, trích dẫn, làm rõ câu hỏi, đánh giá và hành động gợi ý   |
| AI — trong câu hỏi       | `/items/{question_id}/explain` (SSE), `/items/{question_id}/hint`                                                | Giải thích sau khi trả lời và gợi ý trước khi trả lời                              |
| Nguồn trích dẫn          | `/passages/{passage_id}`                                                                                         | Mở đoạn nguồn, trang/chương/điều khoản và thông tin hiệu lực                       |
| Tiến độ năng lực         | `/progress/skills?scope=latest3` hoặc `?scope=all`                                                                | Tỷ lệ đúng, độ phủ học phần, ưu tiên ôn, lịch sử điểm và phân bố mức độ            |
| Tiến độ nhịp học/lịch ôn | `/progress/rhythm`                                                                                               | Thời gian học, heatmap 8 tuần, trí nhớ thẻ, đường cong và dự báo thẻ đến hạn       |
| Hồ sơ/quyền dữ liệu      | `/me`, `PATCH /me`, `/me/data`, `DELETE /me`, `/consent`                                                         | Cài đặt hồ sơ, xuất dữ liệu, yêu cầu xóa và quản lý consent                        |
| Báo lỗi nội dung         | `/reports`                                                                                                       | Gửi target, mã lý do, ghi chú và màn hình phát sinh                                |
| Dashboard cán bộ         | `/admin/dashboard/overview`, `/admin/dashboard/export`                                                           | Số liệu tổng hợp, lọc phạm vi, tải XLSX                                            |
| Nhập CSV                 | `/admin/users/import`, `/admin/users/import/{batch_id}/confirm`                                                  | Kiểm tra danh sách, xem lỗi, xác nhận và phát hành mã kích hoạt                    |

## 4. Hợp đồng endpoint chi tiết

### 4.1. Người dùng, hồ sơ và đồng ý

| Method + path                               | Request/response frontend dựa vào                                                                                                                                                                                                                                                                               |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /v1/me`                                | `pseudonym_id`, `display_name`, `audience` (`student`/`graduate`), `organisation`, `focus_module_ids`, `exam_date`, `target_retention`, `new_cards_per_day`, `max_reviews_per_day`, `diagnostic_prompt_dismissed`. Màn consent cũng đọc `consent.service_given_at`; hồ sơ đọc thêm `consent.research_given_at`. |
| `PATCH /v1/me`                              | Các field gửi từ giao diện: `display_name`, `target_retention`, `new_cards_per_day`, `max_reviews_per_day`, `focus_module_ids`, `diagnostic_prompt_dismissed`. Trả hồ sơ cập nhật (`Me`). `examPeriod` trên hồ sơ hiện lưu cục bộ, không gửi backend.                                                           |
| `GET /v1/me/data`                           | Dữ liệu cá nhân/học tập có thể xuất. Frontend không ràng buộc schema, tải về JSON cùng một số cài đặt cục bộ.                                                                                                                                                                                                   |
| `DELETE /v1/me`                             | Bắt đầu từ nút “Yêu cầu xóa tài khoản”; frontend hiện chờ endpoint hoàn tất rồi xóa workspace local và đăng xuất. Backend cần xác nhận đây là xóa ngay hay tạo yêu cầu xóa, cùng response/status.                                                                                                               |
| `GET /v1/consent/current`                   | `{ version, service_text_vi, research_text_vi }`.                                                                                                                                                                                                                                                               |
| `POST /v1/consent`                          | `{ version, service: true, research: boolean }`. `service` bắt buộc; research là lựa chọn riêng.                                                                                                                                                                                                                |
| `DELETE /v1/consent?kind=service` hoặc `?kind=research` | Rút một loại consent. Nếu rút service, app chuyển về màn đồng ý trước khi tiếp tục; research không tự xóa dữ liệu học. |

### 4.2. Học, luyện tập và phiên học

| Method + path                                                                                | Request/response frontend dựa vào                                                                                                                                                                                                                                         |
| -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /v1/home`                                                                               | `{ name, quick_review_count, quick_review_note_vi, due_cards, next_mock, tutor_suggestions, recent }`. `next_mock` nullable; `recent.kind` là `unit` hoặc `chat`.                                                                                                         |
| `GET /v1/session/today`                                                                      | `{ local_date, steps, total_minutes }`. Mỗi `step` có `kind` là cards, practice hoặc continue, cùng `count`, `minutes`, `reason_vi`, `done`, `practice_set_id`, `unit_id`. Step không có dữ liệu có thể không xuất hiện. |
| `GET /v1/modules`                                                                            | `{ items: Module[] }`. Module gồm `id`, `name`, `short_name`, `core_issue_group`, `coming_soon`, `units_total`, `units_done`, `topics_total`. Bộ lọc gửi query `status`, `group`, `core_issue`, `level`, `q`.                                                             |
| `GET /v1/modules/{module_id}`                                                                | `{ id, name, short_name, units: [{ id, topic, done }] }`.                                                                                                                                                                                                                 |
| `GET /v1/units/{unit_id}/next`                                                               | `UnitView`: `session_id`, `unit_id`, `topic`, `position`, `total`, `done`, `cards_created`, `item`. `item.kind` là `content`, `quiz` hoặc `remediation`; content/question/citations/feedback có thể null tùy loại.                                                        |
| `POST /v1/units/{unit_id}/responses`                                                         | `{ unit_item_id, chosen, time_ms }` + header `Idempotency-Key`. Trả `Feedback`: `correct`, `correct_key`, `explanation`, `rationales`, `citations`, `remediation_inserted`, `remediation_note`, `card_created`.                                                           |
| `POST /v1/units/{unit_id}/advance`                                                           | `{ unit_item_id }`, trả `UnitView` kế tiếp.                                                                                                                                                                                                                               |
| `POST /v1/practice-sets`                                                                     | `{ module_id: string hoặc null, count: number, random: boolean }`, trả `{ id }`.                                                                                                                                                                                          |
| `GET /v1/practice-sets/{set_id}` hoặc `GET /v1/session/today/practice`                       | `PracticeSetView`: `id`, `source`, `competency_code`, `topic`, `total`, `answered`, `completed`, `items`. Mỗi item có `question_id`, `n`, `stem`, `options`, `reason_vi`, `chosen`, `feedback`. `/session/today/practice` có thể trả `404` khi hôm nay không có bộ luyện. |
| `POST /v1/practice-sets/{set_id}/responses` hoặc `POST /v1/session/today/practice/responses` | `{ question_id, chosen, time_ms }` + `Idempotency-Key`. Trả `PracticeFeedback`: đáp án đúng, giải thích, rationales, citations, next, thẻ tạo và remediation.                                                                                                             |
| `POST /v1/practice-sets/{set_id}/complete` hoặc `POST /v1/session/today/practice/complete`   | Trả `AdaptationSummary`: `graded`, `mastery_updated`, `cards_created`, `tomorrow`. Các phần không áp dụng là `null`, không giả thành số 0. Hoàn tất có tính idempotent để app gọi lại sau reload.                                                                         |

### 4.3. Thẻ ôn tập

| Method + path                      | Request/response frontend dựa vào                                                                                                                                                                            |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `GET /v1/decks`                    | `{ items: [{ module_id, name, short_name, new, learning, due }] }`.                                                                                                                                          |
| `GET /v1/cards/due?limit={n}`      | `{ items: DueCard[], total_due }`. Card gồm `id`, `front`, `back`, `citation`, `source_passage_id`, `origin`, `module`, `preview` (mức 1–4). Không có `limit` thì app lấy danh sách đầy đủ trong một số màn. |
| `POST /v1/cards/{card_id}/reviews` | `{ rating: số nguyên từ 1 đến 4, time_ms }` cùng header `Idempotency-Key`; trả `{ card_id, due_at, remaining_due }`. Backend chịu trách nhiệm lịch nhắc lại/FSRS và hàng đợi đến hạn. |
| `PATCH /v1/cards/{card_id}`        | `{ suspended: boolean }`, dùng tạm dừng/bỏ tạm dừng thẻ.                                                                                                                                                     |

### 4.4. Thi thử và xem kết quả

| Method + path                                         | Request/response frontend dựa vào                                                                                                                                             |
| ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /v1/exams`                                       | `{ items: ExamForm[] }`. Form có `id`, `title`, `kind`, `n_questions`, `minutes`, `attempts_left`, `last`, `open_attempt_id`, `open_remaining_s`, `history`, `plan`.          |
| `POST /v1/exams/{form_id}/attempts`                   | Body `{ fresh: true }` khi người học chủ động làm đề mới; body `{}` khi bắt đầu/tiếp tục. Trả `AttemptView`; nếu có lượt đang làm thì server có thể trả lại lượt đó.          |
| `GET /v1/attempts/{attempt_id}`                       | `AttemptView`: `attempt_id`, `title`, `deadline_at`, `remaining_s`, `warning_s`, `submitted`, `questions`, `answers`. `answers` map `question_id` sang `{ chosen, flagged }`. |
| `PUT /v1/attempts/{attempt_id}/answers/{question_id}` | `{ chosen: string hoặc null, flagged: boolean }`. Client autosave, retry câu trả lời chưa xác nhận; cùng giá trị gửi lại không được làm hỏng lượt thi.                            |
| `POST /v1/attempts/{attempt_id}/submit`               | Nộp bài, trả `Results`. Hết giờ phải được backend tự khóa/nộp; `attempt_closed` được client nhận biết.                                                                        |
| `GET /v1/attempts/{attempt_id}/results`               | `Results`: điểm, số đúng/sai/bỏ trống, thời lượng, `auto_submitted`, ưu tiên ôn, danh sách status từng câu và dữ liệu phân tích chuyên khoa/mức độ.                           |
| `GET /v1/attempts/{attempt_id}/items/{question_id}`   | `ReviewItem`: câu hỏi, options có `is_correct`, chosen, explanation, rationales, citations.                                                                                   |

**Tính thời gian:** đồng hồ UI lấy `remaining_s`/`deadline_at` từ server và đồng bộ lại khoảng 30 giây. Mọi quyết định hết giờ/nộp tự động phải do server xác nhận, không tin đồng hồ client.

### 4.5. AI, hội thoại, nguồn trích dẫn

| Method + path                                                    | Request/response frontend dựa vào                                                                                                                 |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /v1/chat/sessions?limit=50&cursor=…`                        | `{ items: [{ id, title, updated_at }], next_cursor }`.                                                                                            |
| `POST /v1/chat/sessions`                                         | `{}` cho hội thoại thường hoặc `{ question_id }` khi hỏi từ một câu hỏi; trả `{ id }`.                                                            |
| `GET /v1/chat/sessions/{session_id}/messages?limit=100&cursor=…` | `{ items: StoredMessage[], next_cursor }`. Tin nhắn AI gồm text/state, citations, notice, trace, clarify options, nguồn đã tìm, gợi ý và helpful. |
| `POST /v1/chat/sessions/{session_id}/messages` (SSE)             | JSON `{ text, detail }`; khi chọn một câu hỏi làm rõ có thêm `clarifies_message_id`. Response là `text/event-stream`.                             |
| `POST /v1/items/{question_id}/explain` (SSE)                     | Body `{}`; AI giải thích câu sau khi người học trả lời.                                                                                           |
| `POST /v1/items/{question_id}/hint`                              | Body `{}`; trả `{ text, citations, generated }`; có thể trả `hint_unavailable`.                                                                   |
| `POST /v1/messages/{message_id}/rating`                          | `{ helpful: true }` trong client hiện tại.                                                                                                        |
| `POST /v1/chat/suggestions/{suggestion_id}/accept`               | Body `{}`; trả `kind` là practise hoặc add_to_tomorrow, cùng `practice_set_id`, `for_date`.                                                       |
| `GET /v1/passages/{passage_id}`                                  | `{ id, document, chapter, section, page, article, excerpt, demo_label, validity_note }`; metadata phần mục/trang có thể null.                     |

**SSE event được client hiểu:**

1. `status`: `{ status: "queued"|"working", position?: number|null }`.
2. `step`: `{ id, kind, label_vi, status: "running"|"done" }`.
3. `answer`: `{ text, citations, notice }`.
4. `final`: `{ state, message_id, trace_summary, clarify_options, searched, nearest_chapter, suggestions }`.

`state` thuộc `answered`, `insufficient_evidence`, `declined`, `needs_clarification`. `trace_summary` có `sources`, `claims_checked`, `claims_removed`. Mỗi citation cần `n`, `passage_id`, `document`, `chapter`, `section`, `page`, `article`. Kết thúc luồng phải có event `final`; nếu mất kết nối giữa chừng app báo câu trả lời chưa hoàn tất. Khi đang có lượt thi chưa nộp, app không mở tutor/hỏi đáp.

### 4.6. Tiến độ học

| Method + path                           | Dữ liệu frontend sử dụng                                                                                                                                                                                                              |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /v1/progress/skills?scope=latest3` | Scope mặc định là 3 đề gần nhất; lựa chọn còn lại `all`. Trả `days_to_exam`, `coverage` theo module, `priorities`, `mock_scores`, `levels` sáu mức và có thể có `specialties`, `bloom_by_specialty`. `group_grid` hiện chưa hiển thị. |
| `GET /v1/progress/rhythm`               | `days_to_exam`, `week`, `heatmap`, `memory`, `curve`, `recall_by_module`, `due_forecast`, `activity`. Heatmap trên app là 8 tuần; `date` dùng ngày địa phương `YYYY-MM-DD`.                                                           |

Chi tiết `ProgressRhythm`:

- `week`: `{ minutes, previous_minutes, study_days, days_elapsed }`.
- `heatmap`: `{ date, minutes }[]`.
- `memory`: `{ recall_rate, window_days, reviews, new, learning, mastered, due_today }`.
- `curve`: `{ date, recall, kind: review|decay|projected }[]`.
- `recall_by_module`: `{ module_id, short_name, now, in_7_days }[]`.
- `due_forecast`: `{ date, count }[]`; dùng cho lịch ôn và 7 ngày tới. Cần xác nhận horizon trả về đủ cho lịch tháng.
- `activity`: `{ kind: unit|practice|chat|cards|exam, title, occurred_at, minutes, result_vi }[]`.

## 5. Cán bộ/quản trị trên mobile

Staff dùng token store riêng nhưng endpoint vẫn nằm dưới `/v1`.

| Method + path                                                        | Request/response                                                                                                                                                                                                                                                   |
| -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `GET /v1/admin/dashboard/overview?period=&school=&audience=&region=` | `AdminOverview`: `period`, `computed_at`, `sample_data`, `suppressed`, `suppression_min`, `selected`, các `filters`, `kpis`, `weekly_active`, `alerts`, `accuracy_by_module`, `question_bank`, `ai_safety`, `schools`, `compliance`. Các nhóm dữ liệu có thể null. |
| `GET /v1/admin/dashboard/export?format=xlsx&…`                       | File nhị phân XLSX; trả `Content-Disposition: attachment; filename="…"` để app dùng tên file.                                                                                                                                                                      |
| `POST /v1/admin/users/import`                                        | `multipart/form-data`, field file tên `file`. Giao diện đọc `batch_id`, `rows_total`, `rows_valid`, `sample`, `errors[]` (row và message tiếng Việt).                                                                                                              |
| `POST /v1/admin/users/import/{batch_id}/confirm`                     | Body rỗng; giao diện đọc `codes[]` sau khi xác nhận.                                                                                                                                                                                                               |

Luồng nhập CSV hiện có thông báo rõ API thật có thể trả `501` trên R1.0. Khi API chưa sẵn sàng, không phát sinh mã tài khoản thật; demo mới tạo mã giả cục bộ.

Dashboard có các trường hợp bảo vệ riêng tư: nếu `suppressed=true` hoặc `kpis=null`, giao diện ẩn số liệu thay vì hiển thị số 0. Backend cần áp dụng ngưỡng ẩn nhóm và không trả số liệu có thể suy ngược nhóm nhỏ.

## 6. Các tính năng không lưu trên backend hiện tại

- Demo dùng `src/lib/demo/seed.json`, `examples.json` và store `yhdp.demo.v2` trong localStorage; reset demo xóa dữ liệu này. Demo không gọi AI thật hoặc ghi dữ liệu server.
- Cài đặt avatar, mascot, thông báo đã đọc, nhắc ôn, hoạt động hiển thị cục bộ và giai đoạn thi mục tiêu được lưu trong workspace trình duyệt (`yhdp.workspace.v1:*`). Backend không nên coi chúng là dữ liệu đồng bộ nếu chưa có API riêng.
- Thông báo hiện được dựng từ `/home` cộng workspace local; chưa có API notification/inbox riêng.
- “Đề xuất lịch học” hiện là demo/placeholder, chưa có API tạo hoặc lưu kế hoạch học thật.
- Frontend tự ghi một bản activity local sau một số thao tác thành công; dữ liệu tiến độ chính thức vẫn phải được backend ghi nhận độc lập để `/progress/rhythm` nhất quán giữa thiết bị.

## 7. Điểm cần backend xác nhận trước nghiệm thu

- [ ] Production Vercel có proxy `/api/v1/*` tới backend trước SPA fallback; xác nhận request JSON và SSE đi đúng dịch vụ.
- [ ] Thống nhất payload `GET /me` bao gồm trường consent; cập nhật chính sách patch cho `display_name`, `focus_module_ids`, `target_retention`, `new_cards_per_day`, `max_reviews_per_day`.
- [ ] Xác nhận ngày tính theo `Asia/Ho_Chi_Minh`; `local_date`/ngày heatmap dùng `YYYY-MM-DD`, timestamp sự kiện dùng ISO-8601 có múi giờ.
- [ ] Refresh token được xoay vòng; `token_expired` có code ổn định; logout/revoke token và xử lý đa tab rõ ràng.
- [ ] Các endpoint trả lời unit/practice và đánh giá thẻ hỗ trợ header `Idempotency-Key`; retry cùng key không tạo response/thẻ/lượt đánh giá trùng.
- [ ] Đề thi có `deadline_at`, `remaining_s`, tự đóng/nộp khi hết giờ; `PUT answer` và `submit` an toàn khi client retry/mất mạng.
- [ ] SSE trả `Content-Type: text/event-stream`, JSON ở mỗi `data:`, dùng block ngăn bằng dòng trống; phát đủ `final` kể cả nhánh từ chối/không đủ bằng chứng/làm rõ.
- [ ] Citation ID ổn định và `GET /passages/{id}` trả đúng phần nguồn; AI không gửi citation không thể mở.
- [ ] `/progress/skills` và `/progress/rhythm` dùng cùng nguồn dữ liệu chấm; thống nhất null/zero, phạm vi 3 đề gần nhất/toàn bộ, horizon due forecast và ý nghĩa recall.
- [ ] `DELETE /me`, `DELETE /consent` và `GET /me/data` có semantics, audit/retention và response đã thống nhất.
- [ ] Mở endpoint nhập CSV live (hiện UI đang chờ `501`) và xác nhận schema preview/confirm/codes; `POST /reports` cũng có thể đang chờ backend (UI có nhánh xử lý `501`).
- [ ] Dashboard áp dụng suppression ngưỡng trước khi tổng hợp/trả dữ liệu; export XLSX khớp cùng filter và quyền staff.

## 8. Hạng mục backend chưa nằm trong mobile scope hiện tại

Các component review riêng có gọi `GET /review/queue?limit=100`, `GET /review/items/{id}`, `POST /review/items/{id}/decisions`, `GET /review/reports?limit=100`, nhưng `ReviewWorkspace` chưa được import vào route của `App.tsx`. Cần thống nhất với sản phẩm trước khi backend coi đây là API bắt buộc cho mobile.

## 9. Tệp nguồn để đối chiếu

- API client, error shape, endpoints/types: [`src/lib/api.ts`](../../src/lib/api.ts)
- Refresh/session: [`src/lib/session.ts`](../../src/lib/session.ts), [`src/lib/client.ts`](../../src/lib/client.ts)
- Luồng login, route và consent gate: [`src/app/App.tsx`](../../src/app/App.tsx), [`src/features/auth/Login.tsx`](../../src/features/auth/Login.tsx), [`src/features/auth/Consent.tsx`](../../src/features/auth/Consent.tsx)
- Phiên học: [`src/lib/flow.ts`](../../src/lib/flow.ts), [`src/lib/adaptation.ts`](../../src/lib/adaptation.ts)
- AI/SSE payload: [`src/lib/chatTurn.ts`](../../src/lib/chatTurn.ts), [`src/lib/sse.ts`](../../src/lib/sse.ts), [`src/lib/sseRead.ts`](../../src/lib/sseRead.ts)
- Tiến độ cán bộ: [`src/lib/dashboard.ts`](../../src/lib/dashboard.ts)
- Proxy dev / Vercel SPA rewrite: [`vite.config.ts`](../../vite.config.ts), [`vercel.json`](../../vercel.json)
