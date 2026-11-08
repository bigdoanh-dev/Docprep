# Đối chiếu frontend và backend — 07/11/2026

> Đây là hiện trạng **trước khi sửa**. Xem [bản sửa hợp đồng và kết quả kiểm chứng](frontend-backend-contract-fix.md) cho trạng thái mới nhất.

**Kết luận:** các API live chính được gọi đúng và các response đã thử có đủ trường bắt buộc của frontend. Tuy nhiên, dữ liệu cho frontend mới **chưa khớp đầy đủ**, đặc biệt ở thống kê Bloom, phân tích chuyên khoa/vấn đề, đề theo chuyên khoa và phân loại câu hỏi. Việc các luồng đăng nhập/học/thi đi hết không chứng minh các phần thống kê này đúng.

## Phạm vi và bằng chứng

- Frontend gốc repo, Vite `http://127.0.0.1:5190`, proxy đến Phase 1 `http://127.0.0.1:18880`.
- Backend thật, PostgreSQL/Redis thật, provider `disabled`; dùng tài khoản kiểm thử mới, không đổi hồ sơ hay bài làm của tài khoản demo người dùng.
- Đọc OpenAPI tổng hợp từ code trong container đang chạy; đối chiếu 86 vị trí gọi trực tiếp `api.*`, `staffApi.*`, `publicPost`, `postSSE`. Khai triển các nhánh/base cho ra 91 tuyến tham chiếu, gồm 54 mẫu method/path riêng. 89 tuyến tham chiếu khớp OpenAPI; hai tuyến còn lại đều là `POST /v1/practice-sets` dùng trong demo và đã bị chặn ở live.
- Thực hiện 69 request kiểm thử: 63 trả 200; sáu phản hồi 404/422/501/503 là các phép thử chức năng thiếu/giới hạn/provider nêu bên dưới. Không thấy lỗi 500 trong lượt này.
- Đối chiếu 42 response thành công với kiểu TypeScript của frontend: không phát hiện thiếu trường bắt buộc hoặc sai kiểu trong các mẫu đã thử. Các trường mở rộng bên dưới được khai báo optional nên vẫn có thể thiếu mà phép kiểm tra này không báo lỗi.
- Tái hiện các chỗ lệch dữ liệu trên Edge desktop 1440×1000 và mobile 390×844. Hai ca xác nhận hiện trạng đều đạt; đây là bằng chứng tái hiện lỗi, không phải xác nhận UI đã đúng.
- Không sửa mã ứng dụng trong đợt audit này. Script, JSON kết quả và sáu ảnh nằm trong `.local/frontend-api-audit/`.

## 1. Nhãn Bloom đang diễn giải sai dữ liệu live — cần ưu tiên

Backend tại `backend/app/services/progress.py:18` và `backend/app/schemas/progress.py:74` dùng ba **nhóm** nhận thức. Frontend tại `src/lib/learningAnalytics.ts:1` có sáu mức Bloom; `src/features/progress/SpecialtyAnalysis.tsx:83` lấy số liệu theo cùng số `level` nhưng bỏ nhãn do server gửi.

| Level | Ý nghĩa backend     | Nhãn frontend hiện dùng |
| ----- | ------------------- | ----------------------- |
| 1     | Nhớ, Hiểu           | Ghi nhớ                 |
| 2     | Vận dụng            | Hiểu                    |
| 3     | Phân tích, Đánh giá | Vận dụng                |

Trong mẫu live, API trả level 2 là **Vận dụng, 1/3**, nhưng UI hiển thị **Hiểu, 1/3**. Đã xác nhận trên cả hai viewport. Đây là sai ý nghĩa dữ liệu, không chỉ thiếu một biểu đồ.

Schema database và importer hiện cũng chỉ nhận `bloom_level` 1–3 (`backend/migrations/versions/0003_content.py:90`, `backend/seed/content.py:95`). Không được tự chia ba nhóm thành sáu mức hoặc đổi nhãn để giả định đã có metadata chi tiết. Cần thống nhất thang dữ liệu và để UI tôn trọng thang/nhãn server trả về.

## 2. API chưa cung cấp thống kê chi tiết mà UI mới đọc

- `GET /v1/progress/skills`: thiếu `specialties`, `bloom_by_specialty`, `issues_by_specialty`.
- `GET /v1/attempts/{id}/results` và response submit: thiếu cả ba trường trên và `levels`.
- `backend/app/services/progress.py:63` chỉ trả coverage, priorities, mock_scores, group_grid và ba nhóm levels. Schema kết quả thi tại `backend/app/schemas/exams.py:137` cũng chưa khai báo các trường mới.
- `src/features/exams/Results.tsx:152` chỉ render phân tích khi có `specialties` và `levels`; vì response thiếu nên toàn bộ phần này bị ẩn ở kết quả live.
- `src/features/progress/Progress.tsx:217` truyền các trường optional đang thiếu cho `SpecialtyAnalysis`, nên các góc nhìn chuyên khoa/vấn đề không có số liệu. Khi thiếu `bloom_by_specialty`, lựa chọn chuyên khoa cũng không có dữ liệu riêng để lọc các mức nhận thức.

Cần bổ sung thống kê từ bài thi đã nộp và phiên bản câu hỏi thực tế, giữ phạm vi `latest3`/`all` và biểu diễn đúng phần chưa được đánh giá.

## 3. Thi theo chuyên khoa chưa có dữ liệu hợp đồng

`GET /v1/exams` hiện trả ba đề, **không đề nào có `module_id`**; schema `ExamForm` ở `backend/app/schemas/exams.py:64` chưa có `module_id`/`module_name`.

Trong khi đó, `src/features/exams/Exams.tsx:60` lấy danh sách chuyên khoa và lọc đề dựa vào `form.module_id`. Bấm **Thi thử theo chuyên khoa** thực tế hiển thị “Chưa có bài thi theo chuyên khoa.” dù vẫn có đề tổng hợp. Đã xác nhận trên desktop/mobile.

Đây là khả năng chưa được backend cung cấp; endpoint liệt kê đề vẫn đúng. Cần có metadata/phạm vi đề do backend xác định, không tự gán mọi đề vào một chuyên khoa trên frontend.

## 4. Metadata phân loại câu hỏi chưa được trả về

Response `GET /v1/attempts/{id}/items/{question_id}` thiếu `module_id`, `module_name`, `core_issue_id`, `core_issue_name`, `bloom_level`, `difficulty_label`. Item trong `GET /v1/session/today/practice` cũng thiếu metadata tương ứng.

Các schema `AttemptItemView` (`backend/app/schemas/exams.py:161`) và `PracticeItem` (`backend/app/schemas/practice.py:50`), cùng service tạo response, chưa đưa các trường này ra API. Frontend tại `src/features/exams/Results.tsx:469` và `src/components/PracticeRunner.tsx` đã render `QuestionClassification`.

Kết quả live hiện **“Chưa phân loại”** dù database đã có một phần metadata câu hỏi. Cần trả metadata của đúng phiên bản câu đã phục vụ, với giá trị null rõ ràng khi nguồn chưa được phân loại; không suy diễn dữ liệu còn thiếu từ nội dung câu hỏi.

## 5. Giới hạn thẻ được lưu nhưng queue chưa áp dụng đầy đủ

Kiểm thử lưu `new_cards_per_day=1`, `max_reviews_per_day=1` qua `PATCH /v1/me` thành công; `GET /v1/me` đọc lại đúng. Sau khi tạo thẻ từ câu trả lời sai của tài khoản test, `GET /v1/cards/due` vẫn trả **11 thẻ**, `total_due=11`.

`backend/app/services/cards.py:15` và truy vấn due hiện dùng `limit` request cùng thời điểm đến hạn, chưa dùng đầy đủ ngân sách ôn/ngày. `max_reviews_per_day` có được dùng khi xây bước phiên học; vì vậy không thể kết luận cài đặt hoàn toàn không được đọc. Frontend Profile cũng đã có cảnh báo khả năng này chưa hoàn thiện (`src/features/auth/Account.tsx:214`).

Ngoài ra có một **trường hợp biên có thể trả 422**: cài đặt cho phép `max_reviews_per_day` đến 1000; `cards_step` có thể tạo bước trên 200 thẻ; `src/features/cards/SessionCards.tsx:31` gửi nguyên `step.count` vào `/cards/due?limit=...`, trong khi endpoint chỉ nhận tối đa 200 (`backend/app/api/cards.py:16`). Phép thử trực tiếp `limit=201` đã trả 422. Chưa tạo tài khoản có hơn 200 thẻ đến hạn để tái hiện toàn bộ trường hợp biên này qua UI.

Cần thống nhất ngân sách ôn và kích thước mỗi batch giữa Home, Decks, session và due queue, thay vì chỉ lưu cài đặt.

## Các đường gọi đã khớp và giới hạn đã được xử lý

Các mẫu response được thử gồm đăng nhập/refresh, consent, hồ sơ, học phần, unit, đáp án/feedback, phiên học/practice, thẻ, thi/nộp/xem lại bài, tiến độ, passage, lịch sử chat và dashboard quản trị. Refresh token đọc lại hồ sơ bằng token mới thành công. Upload CSV của frontend dùng đúng `multipart/form-data` với trường `file`.

Các phần sau không bị coi là lỗi frontend gọi nhầm API:

| API/khả năng                                                      | Kết quả hiện tại   | Cách frontend xử lý                                              |
| ----------------------------------------------------------------- | ------------------ | ---------------------------------------------------------------- |
| `POST /practice-sets`                                             | 404, chưa có route | Các nút tạo lượt mới bị khóa/ẩn ở live; vẫn dùng được trong demo |
| `POST /reports`                                                   | 501                | Có thông báo server chưa hỗ trợ và giữ nội dung form để thử lại  |
| Import CSV, review queue                                          | 501                | Là các handler chưa triển khai; upload CSV gửi đúng định dạng    |
| Sinh câu trả lời chat                                             | 503 `ai_disabled`  | Hiện thông báo AI chưa bật; không tạo answer/citation giả        |
| Tạo/chấm quiz mới trong chat                                      | Chưa hỗ trợ        | Nút tạo quiz mới bị khóa                                         |
| Thư viện thẻ đầy đủ, lộ trình dài hạn, đồng bộ thông báo/bookmark | Chưa đủ API live   | Có phần dùng dữ liệu local hoặc thông báo giới hạn               |

Đợt audit này chưa kiểm chứng generation với model thật, SSE thành công, resume/cancel của một lượt đang generate, hoặc toàn bộ biến thể tài khoản/dữ liệu. Các ca E2E trước đó đã kiểm tra đường đi nghiệp vụ cơ bản; chúng không thay thế việc đối chiếu các trường mở rộng và ý nghĩa thống kê nêu trên.
