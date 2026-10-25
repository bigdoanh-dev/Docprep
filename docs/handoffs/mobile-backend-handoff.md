# Tài liệu bàn giao backend — DocPrep Mobile

**Ngày rà soát:** 25/10/2026
**Repository:** `bigdoanh-dev/Docprep_FE`, nhánh `main`
**Mục đích:** mô tả đầy đủ các luồng mobile đang được nối trong frontend, những request/response mà client sử dụng, quy tắc ghi dữ liệu, trường hợp lỗi và các phần chưa có API thật.

> Tài liệu được đối chiếu trực tiếp với mã frontend tại commit `82cbb75` và lần cập nhật này. Đây là hợp đồng mà client đang tiêu thụ, không phải xác nhận rằng backend hiện đã triển khai các API đó. Khi kiểu dữ liệu hoặc giao diện chưa xác định được semantics nghiệp vụ, phần đó được đánh dấu **Cần chốt** thay vì tự suy đoán.

## 1. Cách đọc tài liệu

- **Client gọi:** request mà ứng dụng hiện thực sự gửi.
- **Client cần:** các trường trong response mà giao diện đọc hoặc hiển thị. Có thể trả thêm trường nếu tương thích ngược.
- **Cần chốt:** nội dung chưa thể kết luận chỉ từ frontend; backend/product cần thống nhất trước nghiệm thu.
- Các đường dẫn bên dưới là đường dẫn backend bắt đầu từ `/v1`. Trình duyệt gọi qua `/api/v1`.
- Với danh sách, frontend thường đọc envelope `{ "items": [...] }`, không đọc trực tiếp một mảng JSON.

## 2. Phạm vi và màn hình mobile

Ứng dụng là SPA React/Vite được bố trí theo giao diện mobile. Các route learner được bảo vệ bằng đăng nhập, role và consent; staff dùng phiên đăng nhập riêng. `App.tsx` hiện không nối các component trong `src/features/review/` vào route.

| Vai trò | Route | Màn hình / chức năng | API chính |
| --- | --- | --- | --- |
| Người học | `/dang-nhap` | Kích hoạt tài khoản hoặc đăng nhập cán bộ; có lựa chọn demo | `POST /auth/activate`, `POST /auth/staff/login` |
| Người học | `/dong-y` | Đọc và lưu đồng ý dịch vụ/nghiên cứu | `/consent/current`, `POST /consent` |
| Người học | `/chon-hoc-phan` | Chọn hoặc đổi học phần ưu tiên | `/modules`, `/me`, `PATCH /me`, tùy luồng `/exams` và `/modules/{id}` |
| Người học | `/` | Trang chủ, phiên hôm nay, thẻ đến hạn, nội dung tiếp tục, gợi ý | `/home`, `/session/today` |
| Người học | `/luyen-tap` | Danh mục học phần, tìm kiếm/lọc, mở nội dung | `/modules`, `/modules/{id}` |
| Người học | `/luyen-tap/:unitId` | Học nội dung, trả lời quiz, xem giải thích và nguồn | `/units/{id}/next`, `/responses`, `/advance` |
| Người học | `/on-tap` | Tạo lượt luyện theo học phần hoặc tổng hợp | `/modules`, `/me`, `POST /practice-sets` |
| Người học | `/luyen-tap/bo-cau/:setId` | Làm bộ câu hỏi luyện tập | `/practice-sets/{id}`, `/responses`, `/complete` |
| Người học | `/phien` | Điều phối tới bước chưa hoàn tất trong phiên ngày | `/session/today` |
| Người học | `/phien/the` | Ôn thẻ của phiên ngày | `/session/today`, `/cards/due`, `/cards/{id}/reviews`, `/cards/{id}` |
| Người học | `/phien/luyen` | Luyện điểm yếu của phiên ngày | `/session/today`, `/session/today/practice/*` |
| Người học | `/phien/dieu-chinh` | Hiện tổng kết điều chỉnh sau bộ câu luyện | `/session/today/practice`, `/complete`, `/session/today` |
| Người học | `/luyen-tap/bo-the` | Tổng quan bộ thẻ theo học phần | `/decks` |
| Người học | `/luyen-tap/on-the` | Ôn toàn bộ hàng đợi thẻ đến hạn | `/cards/due`, `/cards/{id}/reviews`, `/cards/{id}` |
| Người học | `/luyen-tap/duyet-the` | Duyệt/tìm/tạm ẩn thẻ được API trả về | `/cards/due`, `PATCH /cards/{id}`, `/passages/{id}` |
| Người học | `/hoi-dap` | Gia sư AI, lịch sử hội thoại, phân trang | `/chat/sessions`, `/messages`, SSE |
| Người học | `/hoi-dap/tu-cau-hoi/:questionId` | Gia sư AI theo ngữ cảnh một câu hỏi | `/chat/sessions`, `/messages`, SSE |
| Người học | Popup gia sư AI | Có thể mở dạng thu gọn hoặc phóng to trong giao diện mobile | Cùng API với `/hoi-dap`; không có API kích thước cửa sổ |
| Người học | `/thi-thu` | Danh sách đề, trạng thái và lịch sử lượt thi | `/exams` |
| Người học | `/thi-thu/:formId/quy-dinh` | Xem đề cương/điều kiện và bắt đầu hoặc tiếp tục thi | `/exams`, `POST /exams/{id}/attempts` |
| Người học | `/thi-thu/lam-bai/:attemptId` | Làm bài có đồng hồ, đánh dấu và autosave | `/attempts/{id}`, `PUT /answers/{questionId}`, `/submit` |
| Người học | `/thi-thu/ket-qua/:attemptId` | Điểm, phân tích và từng câu | `/attempts/{id}/results` |
| Người học | `/thi-thu/ket-qua/:attemptId/:questionId` | Xem lại đáp án, giải thích, trích dẫn | `/attempts/{id}/items/{questionId}`, `/results` |
| Người học | `/tien-do` | Tiến độ năng lực, độ phủ, phần ưu tiên, phân tích | `/progress/skills` |
| Người học | `/tien-do/nhip-hoc` | Nhịp học, heatmap, trí nhớ, dự báo thẻ | `/progress/rhythm` |
| Người học | `/lich-on` | Lịch tháng và số thẻ đến hạn theo ngày | `/progress/rhythm` |
| Người học | `/lo-trinh` | Form phân bổ lịch học minh họa | Không có API backend hiện tại |
| Người học | `/thong-bao` | Nhắc thẻ và kết quả gần đây | `/home` + local workspace |
| Người học / staff | `/profile` | Hồ sơ và cài đặt; quyền dữ liệu cho learner | Learner: `/me`, `/me/data`, `/consent`; staff: hiện không gọi API hồ sơ |
| Cán bộ Bộ | `/quan-ly`, `/quan-ly/co-so`, `/quan-ly/ket-qua`, `/quan-ly/an-toan` | Dashboard lọc, số liệu cơ sở/học tập/an toàn và xuất XLSX | `/admin/dashboard/overview`, `/export` |
| Admin | `/quan-tri` | Trang vận hành và điều hướng cấp tài khoản | Hiện trang vận hành không gọi API riêng |
| Admin | `/quan-tri/tai-khoan` | Nhập CSV, xem preview, xác nhận phát hành mã | `/admin/users/import`, `/confirm` |

### Route không thuộc luồng mobile được nối

- `/giang-vien/*` component `Lecturer` hiện là demo/local, chưa được import vào `App.tsx`, chưa có API backend.
- `src/features/review/*` có các lời gọi `/review/*` nhưng `ReviewWorkspace` không được route trong `App.tsx`; không coi đây là endpoint bắt buộc của mobile ở bản hiện tại.
- Trang portal và route alias trong `App.tsx` không phải luồng learner/staff sau đăng nhập cần backend mobile triển khai riêng.

## 3. Luồng nghiệp vụ xuyên màn hình

### 3.1 Đăng nhập learner lần đầu

1. Client gửi mã kích hoạt qua `POST /v1/auth/activate`.
2. Server trả token pair, `role`, `expires_in` và `consent_required`.
3. Client chỉ nhận role mobile `learner`, `admin`, `ministry_viewer`. `reviewer` và role khác bị từ chối ở UI.
4. Nếu `consent_required=true`, điều hướng tới `/dong-y`; nếu không, vào route yêu cầu hoặc trang mặc định.
5. Learner gate gọi `GET /v1/me`; kiểm tra `consent.service_given_at`. Nếu chưa có đồng ý dịch vụ, điều hướng về consent. Nếu `diagnostic_prompt_dismissed=false`, ép người học đi qua chọn học phần.
6. Sau khi lưu học phần, client `PATCH /v1/me` với `focus_module_ids` và `diagnostic_prompt_dismissed=true`; sau đó mở bài học đầu tiên chưa hoàn thành, đề đánh giá nếu có hoặc trang chủ.

### 3.2 Trang chủ và phiên ngày

1. `/` tải đồng thời `GET /v1/home` và `GET /v1/session/today`.
2. Home hiển thị số thẻ đến hạn, gợi ý, hoạt động gần đây, unit đã học gần đây và các bước trong phiên.
3. Phiên có các loại `cards`, `practice`, `continue`; server có thể không trả một bước nếu không có dữ liệu cho bước đó.
4. `/phien` tìm bước đầu tiên chưa xong theo thứ tự server trả; sau từng bước, client tải lại session để tìm bước tiếp.
5. Trạng thái hoàn thành và thứ tự bước phải do server trả; client không tự tạo bước còn thiếu.

### 3.3 Học unit và trả lời quiz

1. Mở unit: `GET /v1/units/{unit_id}/next` trả mục hiện tại.
2. Nếu `item.kind=content` hoặc `remediation`, client hiển thị nội dung và citation; bấm tiếp thì gửi `POST /v1/units/{unit_id}/advance` với `unit_item_id`.
3. Nếu `item.kind=quiz`, client gửi `POST /v1/units/{unit_id}/responses` với câu chọn và thời gian xem câu.
4. Client gửi một `Idempotency-Key` mới cho mỗi ý định trả lời. Nếu mất phản hồi, lần retry phải dùng lại cùng key/cùng lựa chọn. UI khóa đổi đáp án sau khi đã gửi.
5. Server trả feedback, client hiển thị đúng/sai, giải thích, lý do từng phương án, citations và remediation. Sau đó client advance.
6. Nếu unit mở trong session (`?phien=1`), khi `done=true` quay về bộ điều phối `/phien`; nếu học độc lập thì hiện kết thúc unit.

### 3.4 Luyện tập

1. Luyện theo phiên ngày: `GET /v1/session/today/practice`; luyện tự chọn: tạo set bằng `POST /v1/practice-sets`, rồi mở `GET /v1/practice-sets/{set_id}`.
2. Client mở câu chưa có feedback đầu tiên; câu đã trả lời phải có thể khôi phục bằng `chosen` và `feedback` trong set.
3. Mỗi đáp án gửi `question_id`, `chosen`, `time_ms` cùng `Idempotency-Key`.
4. Sau câu cuối, client gửi `/complete` một lần. Nếu reload sau khi hoàn tất, frontend có thể gọi `/complete` lại để nhận summary đã lưu; endpoint phải idempotent.
5. Luồng luyện điểm yếu dẫn tới màn hình điều chỉnh rồi tải lại `/session/today`; bộ câu luyện độc lập hiển thị summary trực tiếp.

### 3.5 Ôn thẻ

1. Trang bộ thẻ tải `GET /v1/decks`.
2. Lượt phiên ngày tải session trước rồi lấy tối đa `step.count` thẻ qua `/cards/due?limit={count}`. Ôn độc lập tải `/cards/due` không có limit.
3. Người học lật thẻ rồi chọn rating 1–4: `1=Học lại`, `2=Khó`, `3=Tốt`, `4=Dễ`.
4. Gửi `POST /v1/cards/{card_id}/reviews` với thời gian từ lúc lật đến lúc chấm và một idempotency key cho thẻ hiện tại.
5. Server chịu trách nhiệm lịch lặp lại/FSRS, `due_at` và `remaining_due`; client không tính lịch ôn.
6. Tạm ẩn/mở lại: `PATCH /v1/cards/{card_id}` với `{ "suspended": true|false }`.

### 3.6 Thi thử

1. Danh sách đề và màn hình quy định đều gọi `GET /v1/exams`.
2. Bắt đầu hoặc tiếp tục: `POST /v1/exams/{form_id}/attempts` body `{}`. Nếu đang có lượt, server có thể trả lại attempt đang mở.
3. Bấm “làm bài mới” trong khi đang thi gửi `{ "fresh": true }`. Theo mô tả UI, attempt cũ được nộp với đáp án đã lưu rồi mới tạo attempt mới.
4. Vào màn thi tải `GET /v1/attempts/{attempt_id}`. Frontend khôi phục answer map, `remaining_s`, `deadline_at`, `warning_s`.
5. Mỗi lựa chọn hoặc đánh dấu gửi `PUT /v1/attempts/{attempt_id}/answers/{question_id}`; client giữ hàng đợi local, retry và chặn nộp nếu còn answer chưa được xác nhận lưu.
6. Đồng hồ lấy mốc từ server và resync mỗi ~30 giây. Server là nguồn quyết định hết giờ và tự nộp; client chỉ gọi đồng bộ/điều hướng.
7. Nộp bài gọi `POST /v1/attempts/{attempt_id}/submit`, sau đó trang kết quả tải `/results`. Xem lại từng câu tải `/items/{question_id}`.

### 3.7 Gia sư AI

1. Lịch sử hội thoại tải `GET /v1/chat/sessions?limit=50[&cursor=…]`.
2. Mở hội thoại tải `GET /v1/chat/sessions/{session_id}/messages?limit=100[&cursor=…]`.
3. Hội thoại mới tạo bằng `POST /v1/chat/sessions` body `{}`; nếu xuất phát từ câu hỏi thì `{ "question_id": "…" }`.
4. Trước khi gửi câu hỏi, hiện client gọi `/exams` và chặn gửi nếu còn attempt chưa nộp. Đây là kiểm tra UI; backend cần tự enforce quy tắc này nếu là chính sách sản phẩm.
5. Gửi câu hỏi bằng POST SSE tới `/v1/chat/sessions/{session_id}/messages`. Event `final` là tín hiệu kết thúc bắt buộc.
6. Chọn câu hỏi làm rõ gửi `clarifies_message_id`; yêu cầu “giải thích thêm” gửi `detail=true`.
7. Hữu ích gửi rating; chọn gợi ý gửi accept. Nếu gợi ý tạo set thì mở practice set; nếu thêm vào ngày sau thì backend trả `for_date`.
8. AI từ một quiz gọi `/items/{question_id}/hint` trước khi trả lời; sau khi trả lời gọi POST SSE `/items/{question_id}/explain`.
9. Chạm citation gọi `GET /v1/passages/{passage_id}` để mở nguyên văn đoạn nguồn.

## 4. Kết nối, phiên và quy ước chung

### 4.1 URL và triển khai

- Trong client, `BASE = "/api/v1"`.
- Khi phát triển bằng Vite, `vite.config.ts` chuyển `/api/*` tới `BACKEND_URL` (mặc định `http://127.0.0.1:8000`) và bỏ `/api`; ví dụ trình duyệt `/api/v1/me` thành backend `/v1/me`.
- `.env.example` chỉ có `BACKEND_URL`; không đóng cứng URL production vào bundle.
- `vercel.json` hiện rewrite catch-all `/(.*)` thành `/index.html`. Deployment phải cấu hình route/proxy `/api/v1/*` tới backend trước catch-all. Nếu thiếu, request API/SSE có thể nhận HTML SPA thay JSON hoặc event stream.
- Backend/proxy cần hỗ trợ POST SSE dạng fetch stream, không buffer toàn bộ câu trả lời tới khi hoàn tất. Nếu khác origin thì cấu hình CORS cho origin ứng dụng, `Authorization`, `Content-Type`, `Idempotency-Key`, và expose `Content-Disposition` khi tải file.

### 4.2 Token và refresh

- Learner login: `POST /v1/auth/activate` body `{ "code": string, "device": { "platform": "web" } }`.
- Staff login: `POST /v1/auth/staff/login` body `{ "email": string, "password": string }`.
- Hai endpoint login công khai, không gửi Bearer token.
- TokenPair client đọc: `{ access_token, refresh_token, expires_in, role, consent_required }`.
- Authenticated request: `Authorization: Bearer <access_token>`.
- Learner token lưu riêng dưới `yhdp.session`; staff token ở `yhdp.staff`. Đây chỉ là hai kho token frontend, không thay thế phân quyền server.
- Khi response là `401` với `error.code="token_expired"`, client gửi `POST /v1/auth/refresh` body `{ "refresh_token": "…" }`, lưu cặp token mới rồi retry request gốc tối đa một lần.
- Refresh được serialize giữa các request/tab vì server được giả định rotate refresh token và từ chối token đã dùng. Refresh bị từ chối kết thúc phiên. Network/5xx trong lúc refresh hiện không xóa token ngay.
- `POST /v1/auth/logout` body `{}`; client vẫn xóa token cục bộ kể cả khi gọi logout thất bại.
- Role mobile chấp nhận: `learner`, `admin`, `ministry_viewer`. Backend phải authorize trên token cho từng endpoint; không dựa vào `actor` phía client.

### 4.3 Error envelope và status client phụ thuộc

Lỗi JSON được đọc theo dạng:

```json
{
  "error": {
    "code": "machine_readable_code",
    "message_vi": "Thông báo tiếng Việt"
  }
}
```

| HTTP / code | Cách client xử lý |
| --- | --- |
| `401 token_expired` | Refresh token một lần rồi retry request gốc |
| `401` code khác hoặc refresh bị từ chối | Xóa phiên và về màn đăng nhập |
| `403 consent_required` | Chuyển learner tới `/dong-y` |
| `404` trên `/session/today/practice` | Có thể hiểu là hôm nay không có bộ luyện |
| `404` trên flow có `missingTo` | Điều hướng về trang phiên |
| `409` trên `POST /consent` | Văn bản consent đã đổi; tải lại và yêu cầu đọc/chọn đồng ý lại |
| `409 attempt_closed` | Xóa đáp án thi chưa lưu, đánh dấu đã hết giờ và chờ server auto-submit |
| `501` trên `/reports` | UI báo backend chưa hỗ trợ nhận phản ánh |
| `501` trên import CSV live | UI báo API chưa sẵn sàng; không phát mã giả ở live mode |
| Network / response không phải JSON | Hiện lỗi kết nối hoặc lỗi chung tiếng Việt |

Giữ `error.code` ổn định và có thể xử lý máy; frontend không dựa duy nhất vào câu `message_vi` để quyết định nghiệp vụ.

### 4.4 Retry và thời gian

- Unit response, practice response và card review gửi header `Idempotency-Key`. Một key tương ứng một ý định gửi; retry cùng key phải trả lại kết quả cũ, không chấm/trừ/tạo thẻ hai lần.
- Auto-save câu thi hiện **không** gửi idempotency header; `PUT` phải là upsert idempotent cho cùng attempt/question và payload.
- `local_date` và ngày của heatmap dùng `YYYY-MM-DD`, theo `Asia/Ho_Chi_Minh`. Event timestamp nên là ISO-8601 có timezone.
- `time_ms` là số mili giây client đo thời gian ở câu hỏi/thẻ. Dùng làm telemetry/tối ưu, không dùng để quyết định chấm hoặc xác thực thời lượng thi.
- Không trả `0` để thay trường chưa có/không được phép hiển thị nếu type cho phép `null`; `0` là giá trị thật (ví dụ 0 câu đúng).

## 5. Hợp đồng API chi tiết

### 5.1 Đăng nhập, consent, hồ sơ và quyền dữ liệu

#### `POST /v1/auth/activate`

Request:

```json
{ "code": "ACTIVATION-CODE", "device": { "platform": "web" } }
```

Response client cần: `access_token`, `refresh_token`, `expires_in` (giây), `role`, `consent_required`.

#### `POST /v1/auth/staff/login`

Request `{ "email": "…", "password": "…" }`. Response cùng TokenPair. Nếu role trả về không thuộc ba role mobile chấp nhận thì UI từ chối phiên đó.

#### `POST /v1/auth/refresh` và `POST /v1/auth/logout`

- Refresh request `{ "refresh_token": "…" }`; response phải có `access_token` và `refresh_token` mới. Refresh token cũ không được tái sử dụng nếu hệ thống rotate.
- Logout request `{}`; client không đọc body response. Server vẫn nên revoke token/session nếu hỗ trợ.

#### `GET /v1/me`

Client đọc hồ sơ `Me`:

```json
{
  "pseudonym_id": "string",
  "display_name": "string",
  "audience": "student",
  "organisation": "string hoặc null",
  "focus_module_ids": ["g1"],
  "exam_date": "YYYY-MM-DD",
  "target_retention": 0.85,
  "new_cards_per_day": 10,
  "max_reviews_per_day": 100,
  "diagnostic_prompt_dismissed": false,
  "consent": {
    "service_given_at": "ISO-8601 hoặc null",
    "research_given_at": "ISO-8601 hoặc null"
  }
}
```

`consent` không nằm trong type `Me` nhưng được gate và trang hồ sơ đọc từ response của `/me`; cần thống nhất shape này hoặc cung cấp API tương đương. `audience` client biết `student | graduate`.

#### `PATCH /v1/me`

Chỉ gửi các field thay đổi; response là `Me` cập nhật:

```json
{
  "display_name": "Tên hiển thị",
  "target_retention": 0.85,
  "new_cards_per_day": 10,
  "max_reviews_per_day": 100,
  "focus_module_ids": ["g1"],
  "diagnostic_prompt_dismissed": true
}
```

Validation UI hiện có: display name bắt buộc, tối đa 80 ký tự; mục tiêu nhớ chọn 0.85/0.90/0.95; thẻ mới 1–100/ngày; lượt ôn 1–1000/ngày; phải chọn ít nhất một học phần. Frontend có cảnh báo rằng giới hạn thẻ mới/lượt ôn có thể chưa được dịch vụ áp dụng.

#### Consent

- `GET /v1/consent/current` → `{ version, service_text_vi, research_text_vi }`.
- `POST /v1/consent` body `{ version, service: true, research: boolean }`; `service` bắt buộc, research là lựa chọn độc lập.
- `POST /consent` có thể trả `409` nếu version đổi trong lúc người dùng đang đọc. Client tải lại text, bỏ hai lựa chọn cũ và yêu cầu chọn lại.
- `DELETE /v1/consent?kind=service` hoặc `?kind=research`; research rút riêng, service rút xong thì app bắt người dùng quay lại consent.
- **Cần chốt:** thời điểm và version phải được lưu/audit thế nào; rút service có giữ quyền truy cập dữ liệu xuất hay không. UI chỉ nói việc rút consent không tự xóa dữ liệu.

#### Quyền dữ liệu

- `GET /v1/me/data`: client tải JSON và gộp cùng workspace trình duyệt để tạo file xuất. Frontend hiện không đọc schema của response.
- `DELETE /v1/me`: client gọi sau khi người dùng gõ `XÓA`; khi response thành công sẽ xóa workspace cục bộ và đăng xuất.
- **Cần chốt:** `DELETE /me` xóa ngay hay tạo deletion request; status/body, thời hạn xử lý, retention/audit và cách user theo dõi yêu cầu. Endpoint name hiện là DELETE nhưng UI text gọi “Yêu cầu xóa”.

### 5.2 Trang chủ, học phần và nội dung bài học

#### `GET /v1/home`

Response client đọc:

```json
{
  "name": "Tên người học",
  "quick_review_count": 0,
  "quick_review_note_vi": null,
  "due_cards": 0,
  "next_mock": null,
  "tutor_suggestions": [],
  "recent": []
}
```

- `next_mock`: null hoặc `{ form_id, title, n_questions, minutes, open_attempt_id }`; `open_attempt_id` nullable.
- `tutor_suggestions[]`: `{ kind, text_vi, action }`; action nullable. Nếu có action: `{ label_vi, target, id }`, target là `cards | unit | practice_set | session`.
- `recent[]`: `{ kind: "unit"|"chat", id, title, subtitle_vi, progress }`; subtitle/progress nullable, progress tỷ lệ 0–1.
- Trang thông báo cũng tải `/home` nhưng tự dựng thông báo từ due count và local activity; endpoint này chưa phải inbox API.

#### `GET /v1/session/today`

```json
{
  "local_date": "YYYY-MM-DD",
  "steps": [
    {
      "kind": "cards",
      "count": 10,
      "minutes": 5,
      "reason_vi": "string",
      "done": false,
      "practice_set_id": null,
      "unit_id": null
    }
  ],
  "total_minutes": 20
}
```

- `kind`: `cards`, `practice`, `continue`.
- `practice_set_id`/`unit_id` nullable theo loại step; `steps` có thể chứa 0–3 bước.
- Ngày session phải theo múi giờ Việt Nam và duy trì cùng ngày xuyên suốt các API home/cards/progress.

#### `GET /v1/modules` và `GET /v1/modules/{module_id}`

- Danh sách `{ items: Module[] }`; mỗi module: `id`, `name`, `short_name`, `core_issue_group` nullable, `coming_soon`, `units_total`, `units_done`, `topics_total`.
- Query lọc có thể gồm `status` (`not_started`, `in_progress`, `done`), `group`, `core_issue`, `level` (`1`, `2`, `3`), `q`.
- UI có thêm tìm kiếm/filter cục bộ; server nhận query khi người dùng bấm áp dụng bộ lọc.
- Detail `{ id, name, short_name, units: [{ id, topic, done }] }`.
- Học phần `coming_soon` hoặc không có unit không được tạo số liệu học giả.

#### `GET /v1/units/{unit_id}/next`

`UnitView` gồm:

```json
{
  "session_id": 123,
  "unit_id": "unit-id",
  "topic": "Tên chủ đề",
  "position": 0,
  "total": 5,
  "done": false,
  "cards_created": 0,
  "item": {
    "unit_item_id": "item-id",
    "kind": "quiz",
    "title": null,
    "body": null,
    "citations": [],
    "reason": null,
    "question": {
      "id": "question-id",
      "stem": "Câu hỏi",
      "options": [{ "key": "A", "text": "Phương án" }]
    },
    "chosen": null,
    "feedback": null
  }
}
```

- `item.kind`: `content | quiz | remediation`; các trường content/question/citation/feedback được phép null theo loại.
- Options là `{ key, text }`; không gửi cờ `is_correct` trong câu hỏi đang làm.
- `item=null` khi không còn item là trạng thái hợp lệ; đồng thời `done` phải phản ánh đã hoàn tất.

#### Trả lời và chuyển mục unit

- `POST /v1/units/{unit_id}/responses` request `{ unit_item_id, chosen, time_ms }` + `Idempotency-Key`.
- Response Feedback: `{ correct, correct_key, explanation, rationales: Record<optionKey,string>, citations: Citation[], remediation_inserted, remediation_note, card_created }`.
- `POST /v1/units/{unit_id}/advance` request `{ unit_item_id }`; response là `UnitView` kế tiếp hoặc trạng thái kết thúc phù hợp với type (client hiện khai báo `UnitView`).
- **Cần chốt:** quy tắc answer/advance khi request lặp, khi item đã hết hạn, và response cuối cùng sau `done`.

### 5.3 Practice set và phiên luyện

#### Tạo bộ câu

`POST /v1/practice-sets` body:

```json
{ "module_id": "g1", "count": 10, "random": false }
```

`module_id` null khi random tổng hợp. Client hiện chọn count `10`, `20`, `30`, `60`; response `{ "id": 123 }`.

**Trạng thái UI:** component PracticeHub gọi create API nhưng nút “Bắt đầu ôn tập” đang disabled trong live mode (`actor.mode !== "demo"`). Vì vậy create API hiện chỉ được đi tới trong demo, chưa phải flow live dùng được.

#### Lấy bộ câu

- `GET /v1/practice-sets/{set_id}` hoặc `GET /v1/session/today/practice`.
- Response `PracticeSetView`: `id`, `source` (`session | chat_suggestion | quiz_similar`), `competency_code`, `topic`, `total`, `answered`, `completed`, `items[]`.
- Mỗi item: `question_id`, `n`, `stem`, `options: {key,text}[]`, `reason_vi`, `chosen: string|null`, `feedback: PracticeFeedback|null`.
- `GET /session/today/practice` trả `404` nếu không có set hôm nay; client điều hướng về `/phien`.
- Khi quay lại set đang mở, phải trả lại các câu và feedback đã ghi, thứ tự ổn định; khi `completed=true`, trả summary có thể lấy lại bằng `POST /complete`.

#### Gửi đáp án và hoàn tất

- `POST /v1/practice-sets/{id}/responses` hoặc `/v1/session/today/practice/responses` body `{ question_id, chosen, time_ms }` + `Idempotency-Key`.
- Response PracticeFeedback: `correct`, `correct_key`, `explanation`, `rationales`, `citations`, `next: { kind }`, `card_created`, `remediation`.
- `next.kind`: `same_type | harder | easier | done`; bản UI hiện dùng `done` để kết thúc câu cuối, các giá trị còn lại hiển thị câu tiếp. UI R1.0 không chọn câu kế theo độ khó.
- `remediation`: null hoặc `{ title, body, citations, reason }`.
- `POST /v1/practice-sets/{id}/complete` hoặc `/v1/session/today/practice/complete` trả `AdaptationSummary`:

```json
{
  "graded": { "correct": 7, "total": 10 },
  "mastery_updated": { "competencies": 2 },
  "cards_created": { "n": 3 },
  "tomorrow": { "reordered": true, "top_item": "string" }
}
```

- Ba trường sau `graded` có thể null nếu không áp dụng; không biến null thành zero.
- `complete` cần idempotent, trả cùng summary khi client retry sau reload; không chấm lại hoặc tạo thẻ lần nữa.

### 5.4 Thẻ ôn và lịch lặp lại

#### `GET /v1/decks`

`{ "items": [{ "module_id", "name", "short_name", "new", "learning", "due" }] }`; mọi số đếm là số nguyên không âm. `due` được dùng cộng tổng ở màn bộ thẻ.

#### `GET /v1/cards/due?limit={n}`

`{ "items": DueCard[], "total_due": number }`, mỗi DueCard hiện khai báo:

```json
{
  "id": 12,
  "front": "Mặt trước",
  "back": "Mặt sau",
  "citation": "Tên nguồn",
  "source_passage_id": "passage-id",
  "origin": "Nguồn tạo thẻ",
  "module": "Học phần",
  "preview": { "1": 1, "2": 2, "3": 5, "4": 9 }
}
```

- `preview` là thời lượng/lịch dự kiến để hiển thị cho từng rating theo data type hiện tại; **Cần chốt đơn vị** trước khi backend dùng.
- Không limit: client dùng cho ôn thẻ và thư viện thẻ. Tuy nhiên UI đang hiện cảnh báo live rằng backend mới cung cấp danh sách đến hạn, chưa có toàn bộ thư viện.
- `CardBrowser` còn đọc `due_at` và `suspended` khi lọc/hiển thị nhưng hai field chưa có trong TypeScript `DueCard`. Muốn hỗ trợ đầy đủ filter “Đến hạn/Tạm ẩn”, cần trả hai field ổn định và cập nhật type hoặc cung cấp endpoint thư viện riêng.
- Chỉ trả thẻ chưa suspended trong hàng đợi ôn; nếu thư viện cần hiện thẻ ẩn thì endpoint hiện tại chưa đủ.

#### Gửi rating và trạng thái thẻ

- `POST /v1/cards/{card_id}/reviews` body `{ rating: 1|2|3|4, time_ms }`, header `Idempotency-Key`.
- Ý nghĩa rating UI: 1 Học lại, 2 Khó, 3 Tốt, 4 Dễ. Không thay mapping mà không cập nhật UI.
- Response `{ card_id, due_at, remaining_due }`; `due_at` timestamp có timezone.
- `PATCH /v1/cards/{card_id}` body `{ suspended: boolean }`; response body không được client đọc. Tạm ẩn card phải loại khỏi queue sau khi thành công.

### 5.5 Thi thử, trả lời, nộp và xem lại

#### `GET /v1/exams`

`{ "items": ExamForm[] }`. Form fields:

- `id`, `title`, `kind` (`diagnostic | mock | demo_short | assembled`), `n_questions`, `minutes`.
- `attempts_left: number|null`, `last: { attempt_id, score, total }|null`.
- `open_attempt_id: number|null`, `open_remaining_s: number|null`.
- `history[]`: `{ attempt_id, submitted_at, duration_s, score, total, auto_submitted }`, mới nhất trước.
- `plan`: null hoặc `{ composition: { new, wrong, review }, topics: [{ name, count }] }`.

`open_attempt_id` là lượt đang làm; client hiển thị “Làm tiếp”. Khi `attempts_left===0`, UI khóa nút “Làm bài mới” trong lúc đang thi.

#### `POST /v1/exams/{form_id}/attempts`

- Body `{}`: bắt đầu hoặc tiếp tục; server có thể trả attempt đang mở.
- Body `{ "fresh": true }`: người dùng xác nhận nộp lượt đang dở và bắt đầu lượt mới.
- Response `AttemptView` như bên dưới.

#### `GET /v1/attempts/{attempt_id}`

```json
{
  "attempt_id": 123,
  "title": "Tên đề",
  "deadline_at": "ISO-8601",
  "remaining_s": 900,
  "warning_s": 120,
  "submitted": false,
  "questions": [{
    "id": "q1", "n": 1, "stem": "Câu hỏi",
    "options": [{ "key": "A", "text": "Phương án" }]
  }],
  "answers": { "q1": { "chosen": "A", "flagged": false } }
}
```

- `questions[].id` là question ID dạng string. `answers` map question ID sang `{ chosen: string|null, flagged: boolean }`.
- Không gửi `is_correct`, explanation hay đáp án đúng trước khi attempt nộp.
- `remaining_s` và `deadline_at` là nguồn đồng hồ server; reload phải tiếp tục cùng attempt.

#### `PUT /v1/attempts/{attempt_id}/answers/{question_id}`

Body `{ "chosen": "A"|null, "flagged": false }`. Client tự gọi khi thay answer hoặc flag, retry dữ liệu chưa lưu, flush tất cả trước submit. Backend nên idempotent/upsert theo attempt + question. Lượt đã đóng cần trả `409` với `error.code="attempt_closed"`.

#### `POST /v1/attempts/{attempt_id}/submit`

Client chờ autosave flush thành công rồi gọi. Trả Results. Nộp lặp không được chấm/ghi lịch sử hai lần; nếu đã nộp nên trả lại cùng kết quả hoặc status đã đóng nhất quán.

#### `GET /v1/attempts/{attempt_id}/results`

Fields Results:

- `attempt_id`, `title`, `score`, `total`, `wrong`, `blank`, `submitted_at`, `duration_s`, `auto_submitted`.
- `new_cards`, `priority_top[]`, `priority_moved_up[]`.
- `items[]`: `{ n, question_id, topic, status: "ok"|"wrong"|"blank" }`.
- `specialties?`: `{ name, correct, total }[]`.
- `levels?`: `{ level, label_vi, correct, total }[]`, sáu mức từ Ghi nhớ tới Sáng tạo.
- `bloom_by_specialty?`: `{ module_id, name, levels: [{ level, label_vi, correct, total }] }[]`.
- Tỷ lệ tính từ `correct / total`; `total=0` là không có dữ liệu, không được hiểu là 0%.

#### `GET /v1/attempts/{attempt_id}/items/{question_id}`

`ReviewItem`: `n`, `total`, `question_id`, `stem`, `options[]` (`key`, `text`, `is_correct`), `chosen`, `explanation`, `rationales`, `citations`.

### 5.6 AI, citations và SSE

#### Danh sách và lịch sử hội thoại

- `GET /v1/chat/sessions?limit=50&cursor=…` → `{ items: [{ id, title, updated_at }], next_cursor }`.
- `POST /v1/chat/sessions` → body `{}` hoặc `{ question_id }`; response `{ id }`.
- `GET /v1/chat/sessions/{session_id}/messages?limit=100&cursor=…` → `{ items: StoredMessage[], next_cursor }`.
- StoredMessage: `id`, `role` (`user|assistant`), `text`, `created_at`, `state`, `format`, `citations[]`, `notice`, `trace_summary`, `clarify_options[]`, `searched[]`, `nearest_chapter`, `suggestions[]`, `helpful`, `trace[]`.
- Pagination cursor null khi hết dữ liệu. UI tải trang cũ theo cursor.

#### Gửi tin nhắn SSE

`POST /v1/chat/sessions/{session_id}/messages` JSON request:

```json
{
  "text": "Câu hỏi của người học",
  "detail": false,
  "clarifies_message_id": 456
}
```

`clarifies_message_id` chỉ thêm nếu người học chọn một hướng làm rõ. Response `Content-Type: text/event-stream`.

#### Event stream

Client hiểu event blocks phân cách bằng dòng trống. `data:` phải chứa một JSON object hợp lệ trên cùng dòng; client parser hiện không hỗ trợ nhiều dòng JSON data.

1. `status`: `{ "status": "queued"|"working", "position": number|null }`. Vị trí chỉ dùng khi đang xếp hàng.
2. `step`: `{ "id", "kind", "label_vi", "status": "running"|"done" }`. ID ổn định để cập nhật đúng bước đã gửi trước đó.
3. `answer`: `{ "text", "citations": Citation[], "notice": string|null }`.
4. `final`: `{ "state", "message_id", "trace_summary", "clarify_options", "searched", "nearest_chapter", "suggestions" }`.

`state`: `answered | insufficient_evidence | declined | needs_clarification`. `trace_summary`: `{ sources, claims_checked, claims_removed }`. `final` bắt buộc cả nhánh từ chối/thiếu bằng chứng/làm rõ; nếu stream đóng mà chưa nhận `final`, UI hiện lỗi mất câu trả lời.

Citation có `{ n, passage_id, document, chapter, section, page, article }`; `chapter`, `section`, `page`, `article` có thể null. Citation marker trong text là `[n]` và phải khớp `citations[].n`.

Các trường bổ trợ:

- `clarify_options[]`: `{ term, label_vi, query }`.
- `searched[]`: `{ document, range }`.
- `nearest_chapter`: null hoặc `{ passage_id, label_vi }`.
- `suggestions[]`: `{ id, kind: "practise"|"add_to_tomorrow", label_vi, reason_vi, n_items }`.
- `trace[]`: `{ id, kind, label_vi, status }`; trace phục vụ UI minh bạch trạng thái xử lý, không thay câu trả lời.

#### AI trong quiz và hành động phụ

- `POST /v1/items/{question_id}/hint` body `{}`; response `{ text, citations, generated }`. Lỗi `hint_unavailable` là trường hợp nghiệp vụ hiển thị lời từ chối, không nên retry tự động.
- `POST /v1/items/{question_id}/explain` SSE body `{}`. Client cần event `answer` có text/citations/notice và `final` có state; nếu không nhận câu trả lời sẽ báo lỗi.
- `POST /v1/messages/{message_id}/rating` body `{ "helpful": true }`; client hiện chỉ gửi true, không gửi false.
- `POST /v1/chat/suggestions/{suggestion_id}/accept` body `{}`; response `{ kind: "practise"|"add_to_tomorrow", practice_set_id: number|null, for_date: string|null }`.
- Client kiểm tra `/exams` trước khi gửi AI nếu đang làm đề; backend cần enforce nếu đây là yêu cầu bảo mật/nghiệp vụ.

#### `GET /v1/passages/{passage_id}`

Response: `{ id, document, chapter, section, page, article, excerpt, demo_label, validity_note }`. `chapter`, `section`, `page`, `article`, `validity_note` có thể null. Passage ID phải ổn định và mở được cho mọi citation được trả về; `validity_note` dùng cảnh báo hiệu lực nguồn.

### 5.7 Tiến độ năng lực và nhịp học

#### `GET /v1/progress/skills?scope=latest3|all`

Mặc định UI gửi `scope=latest3`; lựa chọn còn lại `all`.

```json
{
  "days_to_exam": 30,
  "scope": "latest3",
  "coverage": {
    "assessed_topics": 12,
    "total_topics": 54,
    "modules": [{
      "module_id": "g1", "short_name": "Học phần",
      "topics_assessed": 2, "topics_total": 8
    }]
  },
  "priorities": [{
    "rank": 1, "competency_code": "CI-1", "name": "string",
    "module_id": "g1", "correct": 2, "total": 5, "weakest_vi": null
  }],
  "mock_scores": [{
    "attempt_id": 1, "title": "string", "submitted_at": "ISO-8601",
    "score": 20, "total": 40
  }],
  "specialties": [], "bloom_by_specialty": [],
  "group_grid": null,
  "levels": [{ "level": 1, "label_vi": "Ghi nhớ", "correct": 1, "total": 2 }]
}
```

- `coverage.modules[]`: `module_id`, `short_name`, `topics_assessed`, `topics_total`.
- `priorities[]`: `rank`, `competency_code`, `name`, `module_id`, `correct`, `total`, `weakest_vi` nullable.
- `mock_scores[]`: attempt đã nộp, mới nhất phù hợp scope.
- `specialties[]` (nếu gửi): `{ name, correct, total }`.
- `bloom_by_specialty[]`: module id/name và sáu mức `{ level, label_vi, correct, total }`.
- `group_grid` hiện chưa hiển thị, type cho phép null.
- Không gửi dự đoán điểm thi/đậu; UI chủ ý không trình bày chỉ số này.
- Màn phân tích dùng specialties/levels/Bloom counts để vẽ duy nhất biểu đồ radar theo góc nhìn đang chọn và bảng/bar chi tiết. Nếu nhóm chưa được đánh giá, gửi total 0 để UI thể hiện “chưa có dữ liệu”, không giả 0%.

#### `GET /v1/progress/rhythm`

```json
{
  "days_to_exam": 30,
  "week": { "minutes": 100, "previous_minutes": 80, "study_days": 4, "days_elapsed": 6 },
  "heatmap": [{ "date": "YYYY-MM-DD", "minutes": 20 }],
  "memory": {
    "recall_rate": 0.82, "window_days": 30, "reviews": 40,
    "new": 5, "learning": 8, "mastered": 12, "due_today": 4
  },
  "curve": [{ "date": "YYYY-MM-DD", "recall": 0.9, "kind": "review" }],
  "recall_by_module": [{ "module_id": "g1", "short_name": "Học phần", "now": 0.93, "in_7_days": 0.85 }],
  "due_forecast": [{ "date": "YYYY-MM-DD", "count": 4 }],
  "activity": [{
    "kind": "unit", "title": "string", "occurred_at": "ISO-8601",
    "minutes": 10, "result_vi": null
  }]
}
```

- `week`: phút tuần này, phút tuần trước, ngày đã học, tổng ngày đã qua trong tuần.
- `heatmap[]`: `{ date, minutes }`; UI dựng 8 tuần (56 ngày) theo tuần bắt đầu thứ Hai, và cho chạm từng ngày xem chi tiết. Để các ô không bị lệch hoặc biến thành khoảng trống, nên trả đủ mọi ngày trong khoảng 56 ngày, kể cả ngày 0 phút.
- `memory.recall_rate` nullable; khi null UI hiển thị dấu chưa có dữ liệu. `window_days`, `reviews`, `new`, `learning`, `mastered`, `due_today` dùng để trình bày kết quả ôn.
- `curve[]`: `{ date, recall, kind: "review"|"decay"|"projected" }`. `recall` là tỷ lệ 0–1; client dùng các điểm thực tới hôm nay và nét đứt cho `projected`. UI gọi đây là độ nhớ của một thẻ được ôn nhiều nhất.
- `recall_by_module[]`: `{ module_id, short_name, now, in_7_days }`, tỷ lệ 0–1. Màn hình so sánh hiện tại với dự kiến sau 7 ngày nếu không ôn.
- `due_forecast[]`: `{ date, count }`; trang nhịp học dùng 7 ngày từ hôm nay. Trang `/lich-on` lại vẽ cả tháng đang xem nhưng vẫn dùng đúng endpoint này; ngày không có trong response bị coi là 0 ở UI. **Cần chốt:** mở rộng horizon/query theo tháng hoặc ghi rõ đây chỉ là lịch dự báo có giới hạn.
- `activity[]`: `{ kind: unit|practice|chat|cards|exam, title, occurred_at, minutes, result_vi }`; `minutes`/`result_vi` nullable.
- Backend phải tính `week`, heatmap, memory, curve, due forecast và activity từ nguồn dữ liệu nhất quán giữa thiết bị; không dựa vào localStorage của client.

### 5.8 Báo lỗi nội dung

`POST /v1/reports` body:

```json
{
  "target_type": "question",
  "target_id": "id",
  "reason": "wrong_content",
  "note": null,
  "context": { "screen": "/luyen-tap/unit-id" }
}
```

- `target_type`: `question | answer | card | content`.
- `reason`: `wrong_content | wrong_citation | broken_item | inappropriate | other`.
- `note` null hoặc text tối đa 2.000 ký tự; UI nhắc không đưa thông tin người bệnh.
- Response client cần `{ id: number }` để hiện mã tiếp nhận.
- `501` hiện được xử lý riêng; ở demo phản ánh chỉ ghi vào workspace local, không gọi API.

### 5.9 Staff dashboard, export và nhập CSV

#### `GET /v1/admin/dashboard/overview`

Query filter tùy chọn `period`, `school`, `audience`, `region`. Response `AdminOverview`:

- `period`, `computed_at`, `sample_data`, `suppressed`, `suppression_min`.
- `selected`: `{ period, school, audience, region }`.
- `filters`: danh sách lựa chọn `{ value, label_vi }[]` cho `periods`, `schools`, `audiences`, `regions`.
- `kpis`: null hoặc `{ active_learners, active_learners_previous, accounts_issued, accounts_activated, practice_items, mock_attempts, mock_median, cited_claims_share, cited_claims_target }`.
- `mock_median`: null hoặc `{ share, form_size, learners }`; `form_size` nullable.
- `weekly_active`: null hoặc `{ weeks: [{ week_start, active_learners }], retention: [{ weeks: 1|4|8, share, learners }] }`; `share` nullable.
- `alerts[]`: `{ kind: low_activation|slow_review|old_reports, title_vi, detail_vi }`.
- `accuracy_by_module`: null hoặc `{ learners, items: [{ module_id, short_name, share, low, learners }] }`; share nullable.
- `question_bank`: null hoặc `{ approved, in_review, draft, rejected, issues_covered, issues_total, min_approved_per_issue, round1_median_days, round2_median_days, round2_target_days, rounds_agree_share, reports_received, reports_resolved }`.
- `ai_safety`: null hoặc `{ answers, model_versions, corpus_versions, cited_claims_share, cited_claims_target, insufficient_share, declined_share, flagged_share, reports_per_1000 }`.
- `schools`: null hoặc `{ rows, hidden }`. Row có `code`, `name`, `region`, số tài khoản phát hành/kích hoạt, `activation_low`, weekly active, mock attempts, median và first-to-latest. `hidden[]` nêu nhóm bị ẩn `{ name, region, learners }`.
- `compliance`: null hoặc `{ chat_p95_ms, chat_target_ms, research_consent_learners, research_consent_share, consent_withdrawals, deletion_requests, deletion_median_days }`.
- Khi `suppressed=true` hoặc nhóm nhỏ, UI ẩn số liệu/hiện gạch ngang; không trả 0 giả hoặc các thành phần cho phép suy ngược. Quy tắc suppression phải áp dụng trước khi xuất dữ liệu.
- `sample_data=true` được thể hiện như dữ liệu mẫu, không được trình bày là production metric.

#### `GET /v1/admin/dashboard/export?format=xlsx&{filters}`

- Cùng filter đang chọn với overview.
- Response binary XLSX, header `Content-Disposition: attachment; filename="…"`.
- Client parse filename có dấu ngoặc kép; fallback `bao-cao-tong-quan-toan-quoc.xlsx`.
- Quyền và suppression của export phải khớp dashboard; không được xuất dữ liệu đã bị ẩn trên UI.

#### `POST /v1/admin/users/import`

- Staff Bearer token; request `multipart/form-data`, tên field `file`.
- CSV hiện dùng mẫu header `display_name,organisation_code,audience`; `audience` có `student|graduate`.
- Preview response UI tiêu thụ: `batch_id`, `rows_total`, `rows_valid`, `sample[]`, `errors[]`; mỗi error có `row`, `message_vi`. Sample rows được hiển thị trước bước confirm.
- File thật là bắt buộc ở live; không nhận raw CSV trong JSON body.
- Nếu API chưa phát hành, `501` được hiển thị thành trạng thái chưa sẵn sàng.

#### `POST /v1/admin/users/import/{batch_id}/confirm`

- Body `{}`.
- Response `{ "codes": [...] }`; từng entry hiển thị thông tin người học và mã kích hoạt. Mã thật chỉ xuất hiện sau confirm, thông báo UI nói mã chỉ hiển thị một lần.
- **Cần chốt:** preview batch expiration, quyền confirm, chống confirm lặp, format codes, và cách phục hồi nếu response bị mất sau khi server đã phát hành mã.

## 6. Dữ liệu đang chỉ nằm trên trình duyệt hoặc chưa có backend

| Tính năng | Hiện trạng frontend | Gợi ý nếu cần đồng bộ đa thiết bị |
| --- | --- | --- |
| Trải nghiệm demo | Seed/store `yhdp.demo.v2`; reset demo xóa state local; mock API và mock SSE | Không ghi dữ liệu demo vào tài khoản thật |
| Avatar, mascot, giới tính giao diện | `yhdp.workspace.v1:*` localStorage | Endpoint preference nếu cần đồng bộ |
| Thông báo đã đọc và bật nhắc thẻ | local `read[]`, `remind`; notifications dựng từ `/home` và local activity | Inbox API, read receipt và preference nếu cần push/email/đa thiết bị |
| Hoạt động/streak của header | activity local mirror sau một số POST thành công; streak lấy local dates | Backend activity là nguồn sự thật; UI hiện có thể mất streak khi đổi thiết bị/xóa storage |
| Lịch thi mục tiêu trong Profile | `examPeriod` local; không gửi `/me` | Thêm field/API nếu muốn đồng bộ; khác với `exam_date` server hiện có |
| Lưu câu hỏi/snapshot giải thích | `saved[]` trong workspace | API bookmark/saved-items nếu cần đồng bộ |
| Báo cáo demo | `reportDrafts[]` local | Chỉ live mới gọi `/reports` |
| Đề xuất lịch học | Tính phân bổ tại component; demo lưu `studyPlan` local; live button bị khóa | API plan create/read/update nếu tính năng được bật |
| Thư viện thẻ toàn bộ | Client live chỉ có `/cards/due`, hiện UI cảnh báo giới hạn danh sách | API GET library có search/filter/pagination, `suspended`, `due_at` |
| Nhập CSV demo | Parse local, sinh mã `DEMO-ACT-*` | Không nhầm với mã kích hoạt thật |
| Lecturer / quản lý lớp | Component demo-only, không được route từ `App.tsx` | Chưa đưa vào phạm vi backend mobile |

`src/lib/api.ts` ghi activity local cho learner sau một số response học tập; đây không phải write-back API. Các chỉ số `/progress/rhythm` và dashboard phải được ghi nhận/tính ở server độc lập.

## 7. Việc backend cần chốt trước tích hợp

### P0 — để luồng mobile chạy end-to-end

- [ ] Deploy route/proxy `/api/v1/*` trên Vercel trước catch-all SPA; kiểm tra JSON và SSE không trả `index.html`.
- [ ] Chốt login activation/staff response, expiry, role, refresh-token rotation, logout/revoke và consent-required error code.
- [ ] Chốt `/me` có nested consent hay endpoint riêng; xác nhận schema PATCH và `exam_date`/`examPeriod`.
- [ ] Đưa đầy đủ luồng home/modules/unit/today/practice lên backend; giữ envelope và trạng thái resume ổn định.
- [ ] Idempotency cho unit response, practice response, card review; upsert idempotent cho answer thi; submit/complete trả kết quả nhất quán khi retry.
- [ ] Quyết định chính sách attempt hết giờ, trả `attempt_closed`, tự nộp và `fresh=true`.
- [ ] Cung cấp SSE đủ event và `final` cho cả trạng thái bình thường, từ chối, thiếu bằng chứng, cần làm rõ; trả citation mở được bằng `/passages/{id}`.
- [ ] Chốt schemas `/progress/skills` và `/progress/rhythm`, timezone, zero/null, 56 ngày heatmap và due forecast.
- [ ] Chốt cách xóa tài khoản, rút consent, export data và quy trình audit/retention trước khi mở tính năng.

### P1 — để các màn hình đầy đủ và không tạo trạng thái giả

- [ ] API thư viện card hoặc bổ sung `suspended`, `due_at`, phân trang và filter cho CardBrowser; chốt đơn vị `preview`.
- [ ] Chốt lịch `/lich-on`: response due forecast hiện chỉ được UI dùng như dữ liệu sẵn có; trang đang render ngày cả tháng.
- [ ] Mở `POST /practice-sets` cho live nếu muốn bật PracticeHub (hiện nút live đang khóa).
- [ ] Bật `/reports` và thống nhất nội dung lỗi `501`/quy trình tiếp nhận.
- [ ] Mở CSV import thật, schema preview/confirm, idempotency, quyền xem mã phát hành một lần.
- [ ] Đảm bảo dashboard suppression nhất quán giữa overview, các tab và XLSX export.
- [ ] Quyết định có triển khai inbox/preferences server-side không; hiện thông báo/đã đọc/nhắc ôn đang local.

## 8. Tiêu chí tích hợp backend–mobile

Không chạy thay cho kiểm thử backend; đây là checklist nghiệm thu các contract từ góc nhìn client:

1. Anonymous gọi protected route được đưa về login; sau login quay lại `next` an toàn; role khác không truy cập endpoint ngoài quyền.
2. Learner chưa consent bị dẫn tới consent; consent version đổi giữa lúc đọc trả `409` và client tải văn bản mới.
3. Refresh đồng thời nhiều request/tab chỉ dùng refresh token đúng một lần; response 401/403/network được phân biệt theo code.
4. Retry cùng Idempotency-Key cho quiz/practice/rating chỉ ghi một lần và trả kết quả đã ghi.
5. Reload giữa unit, practice set, card review hoặc mock exam không làm mất tiến trình đã xác nhận server; answer thi không mất do retry.
6. Hết giờ do server quyết định; attempt đóng trả code ổn định và kết quả có `auto_submitted=true`.
7. AI stream gửi được event theo thời gian thực, đúng `Content-Type`, có citations hợp lệ và luôn kết thúc với `final`.
8. Điểm và tiến độ có cùng nguồn dữ liệu; total 0/null không tạo % giả; ngày đúng `Asia/Ho_Chi_Minh`.
9. Mọi API admin kiểm tra staff role; dữ liệu bị suppression không lộ qua export hoặc filter khác.
10. Mã CSV chỉ phát hành sau confirm; không tái hiển thị/nhân đôi mã khi retry mơ hồ.

## 9. Tệp frontend dùng làm nguồn đối chiếu

- Điều hướng, role gate, consent gate: [`src/app/App.tsx`](../../src/app/App.tsx), [`src/app/Shell.tsx`](../../src/app/Shell.tsx)
- Login, consent, hồ sơ: [`src/features/auth/Login.tsx`](../../src/features/auth/Login.tsx), [`src/features/auth/Consent.tsx`](../../src/features/auth/Consent.tsx), [`src/features/auth/Account.tsx`](../../src/features/auth/Account.tsx), [`src/features/auth/Focus.tsx`](../../src/features/auth/Focus.tsx)
- Contract API và types: [`src/lib/api.ts`](../../src/lib/api.ts)
- Auth/refresh: [`src/lib/session.ts`](../../src/lib/session.ts), [`src/lib/client.ts`](../../src/lib/client.ts)
- Home/session/flow: [`src/features/home/Home.tsx`](../../src/features/home/Home.tsx), [`src/lib/flow.ts`](../../src/lib/flow.ts)
- Học/luyện: [`src/features/learning/Modules.tsx`](../../src/features/learning/Modules.tsx), [`src/features/learning/Unit.tsx`](../../src/features/learning/Unit.tsx), [`src/components/PracticeRunner.tsx`](../../src/components/PracticeRunner.tsx), [`src/lib/adaptation.ts`](../../src/lib/adaptation.ts)
- Thẻ: [`src/features/cards/Decks.tsx`](../../src/features/cards/Decks.tsx), [`src/features/cards/CardReview.tsx`](../../src/features/cards/CardReview.tsx), [`src/features/cards/SessionCards.tsx`](../../src/features/cards/SessionCards.tsx), [`src/components/ReviewCard.tsx`](../../src/components/ReviewCard.tsx)
- Thi: [`src/features/exams/Exams.tsx`](../../src/features/exams/Exams.tsx), [`src/features/exams/Exam.tsx`](../../src/features/exams/Exam.tsx), [`src/features/exams/Results.tsx`](../../src/features/exams/Results.tsx)
- AI/SSE/source: [`src/features/chat/Chat.tsx`](../../src/features/chat/Chat.tsx), [`src/components/Conversation.tsx`](../../src/components/Conversation.tsx), [`src/lib/chatTurn.ts`](../../src/lib/chatTurn.ts), [`src/lib/sse.ts`](../../src/lib/sse.ts), [`src/lib/sseRead.ts`](../../src/lib/sseRead.ts), [`src/components/TutorSheet.tsx`](../../src/components/TutorSheet.tsx), [`src/components/Answer.tsx`](../../src/components/Answer.tsx)
- Tiến độ/charts: [`src/features/progress/Progress.tsx`](../../src/features/progress/Progress.tsx), [`src/features/progress/ProgressRhythm.tsx`](../../src/features/progress/ProgressRhythm.tsx), [`src/lib/learningAnalytics.ts`](../../src/lib/learningAnalytics.ts), [`src/lib/charts.ts`](../../src/lib/charts.ts)
- Dashboard/import/report: [`src/lib/dashboard.ts`](../../src/lib/dashboard.ts), [`src/features/management/Dashboard.tsx`](../../src/features/management/Dashboard.tsx), [`src/features/management/UserImport.tsx`](../../src/features/management/UserImport.tsx), [`src/components/ReportIssue.tsx`](../../src/components/ReportIssue.tsx)
- Local state và môi trường: [`src/lib/learnerWorkspace.ts`](../../src/lib/learnerWorkspace.ts), [`src/lib/demo/store.ts`](../../src/lib/demo/store.ts), [`vite.config.ts`](../../vite.config.ts), [`vercel.json`](../../vercel.json)
