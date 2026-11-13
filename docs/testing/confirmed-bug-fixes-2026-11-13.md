# Sửa các lỗi đã xác nhận — 13/11/2026

Nhánh `feat/alpha-v1-backend`, nền `29708ae`. Đợt sửa được chia thành các commit riêng theo nhóm frontend, phiên học, chat và tiến độ trên nhánh này. Theo yêu cầu, ưu tiên lỗi đã xác nhận; không triển khai backlog GAP hoặc streak.

| Mã | Thay đổi | Trạng thái kỹ thuật |
| --- | --- | --- |
| FE-002 | TutorSheet dùng `newKey()` hỗ trợ HTTP LAN; thêm RouteErrorBoundary với tải lại/về trang chủ và phục hồi khi đổi URL. | Đã sửa |
| FE-003 | SSE dùng `newKey()` thay cho gọi trực tiếp `crypto.randomUUID()`. | Đã sửa |
| FE-004 | Một luồng Navigate xử lý đích `next` sau login; giữ bước consent nếu cần, chỉ nhận URL cùng origin. | Đã sửa |
| FE-005 | Đưa các trang thông tin/điều khoản/FAQ ra ngoài RequireLogin. | Đã sửa |
| BE-001 | Advance trả lại phiên đã hoàn tất; hỗ trợ Idempotency-Key. FE giữ cùng key khi gửi lại cùng bước. GET next vẫn mở lượt học mới theo thao tác rõ ràng. | Đã sửa |
| BE-002 | Khóa hàng learner trước khi tìm/tạo phiên, kể cả khi phiên chưa tồn tại. | Đã sửa |
| BE-003 | Alpha chặn gửi chat khi bài thi chưa nộp và còn giờ, trước lưu câu hỏi hoặc phát lại SSE; đồng bộ khóa learner với thao tác bắt đầu thi. | Đã sửa |
| INT-003 | Lưu bền vững kết quả SSE theo key, learner và endpoint. Cùng key/payload trả lại sự kiện đã lưu; đang xử lý trả 409 chat_turn_pending; khác payload trả 409 idempotency_conflict. | Đã sửa |
| INT-002 | Tiến độ trả 6 mức, importer nhận metadata 6 mức tường minh, UI giải thích câu trả lời còn dùng nhóm cũ. | Đang sửa: còn phân loại/thẩm định metadata nội dung |

## Dữ liệu Bloom: phần chưa thể đóng

Migration `0017_six_level_bloom` thêm `question.bloom_level_6` nullable (1–6), giữ `bloom_level` nhóm cũ để tương thích và bảo toàn lịch sử. Không tự gán lại các câu đã duyệt. Các phiên bản đã duyệt được bảo vệ bất biến; metadata mới cần phiên bản mới và quy trình thẩm định nội dung.

`GET /v1/progress/skills` trả đủ Ghi nhớ, Hiểu, Vận dụng, Phân tích, Đánh giá, Sáng tạo cho tổng thể và từng chuyên khoa. Chỉ câu có metadata tường minh mới được đưa vào mức tương ứng. `unclassified_bloom` chứa số đúng/tổng số câu trả lời theo nhóm cũ; chúng vẫn được tính ở chuyên khoa, vấn đề và điểm thi. Các mức chưa được đánh giá không được coi là 0%.

Phân loại câu và kết quả bài thi cũ vẫn dùng nhãn nhóm cũ. Đây là chuyển đổi từng phần có chủ đích để không tạo số liệu giả. INT-002 chưa đủ điều kiện đóng đến khi ngân hàng câu hỏi có metadata sáu mức được duyệt và kiểm tra lại trên nội dung đó.

## Kiểm chứng

- Backend đang chạy thật ở localhost:8000, PostgreSQL local; frontend LAN `http://192.168.20.234:5190`.
- Tài khoản QA tạo qua dịch vụ quản trị tài khoản, `is_synthetic=false`; đăng nhập bằng API/UI thật. Không dùng dữ liệu response giả.
- Hai vòng HTTP + SQL: 8 GET mở chủ đề đồng thời chỉ tạo một phiên; advance cuối gửi lại giữ phiên đã hoàn tất; chat đồng thời/cùng key và phát lại chỉ lưu một cặp tin nhắn; chat đang thi trả 409, nộp bài xong gửi lại được.
- Playwright Chromium trên LAN: đăng nhập về `/profile`, ba trang footer public, xem lại đáp án và Back; hai chủ đề quiz; chat mất phản hồi sau commit tự gửi lại chỉ lưu 2 tin nhắn; kết thúc chủ đề mất phản hồi rồi bấm lại vẫn hoàn tất. Màn hình mobile/desktop.
- Quét lại 30 đường dẫn × 2 kích thước (390/1440): 60/60 không trắng/không pageerror; kiểm tra nội dung đáp án đã tải xong, popup gia sư và điều hướng Phiên học/Back.
- Frontend: 124 test qua; build, lint qua. Bộ hồi quy backend/contract cuối: 48 test qua. Các bộ kiểm tra API/schema/progress/contract bổ sung được ghi riêng trong log; 49 ca contract stub chưa triển khai được skip theo cấu hình sẵn.
- AI provider là `scripted`: kiểm chứng luồng UI/API/DB, chưa kiểm chứng chất lượng mô hình thật.

Log/script/ảnh nằm ngoài repo tại `logs/backend-alpha-v1/qa-codex-2026-11-13/confirmed-fixes/` tính từ thư mục workspace. `results.json` và `run.log` là lượt kiểm tra trực tiếp chính; `additional-results.json` là quét thêm các đường dẫn; `backend-final-checks.log` là bộ kiểm tra cuối. Không lưu mật khẩu/token trong artifact.

## Chạy lại sau khi quay lại dự án

Từ thư mục repository:

```sh
docker compose -f docker-compose.yml -f .local/compose.macos.yml build backend
docker compose -f docker-compose.yml -f .local/compose.macos.yml run --rm --no-deps backend python -m app.cli migrate
docker compose -f docker-compose.yml -f .local/compose.macos.yml up -d db backend
npm run dev -- --host 0.0.0.0 --strictPort
```

Database phát triển được giữ nguyên; không chạy reset-dev. Kiểm thử pytest chỉ được trỏ tới DATABASE_URL_TEST khác database phát triển. Bộ sửa không tự sửa/xóa các phiên trùng đã có trước đó và không gán lại metadata câu đã duyệt.

Với SSE Alpha, key đang xử lý sau một sự cố dừng tiến trình không được chạy lại thành một lượt sinh mới; cơ chế phục hồi tác vụ qua restart thuộc kiến trúc ai_turn của Phase 1. Trong lần sửa này kiểm chứng mất kết nối client sau commit và gửi đồng thời, chưa mô phỏng server bị kill giữa lượt sinh.

## Các commit triển khai

- `58ed962` fix(tien-do): hỗ trợ 6 mức Bloom và giữ riêng dữ liệu nhóm cũ
- `869528a` fix(chat): chặn gia sư khi đang thi và chống lưu trùng tin nhắn
- `5f7fa1b` fix(backend): chống tạo trùng phiên và gửi lại bước học cuối
- `513f7a2` fix(frontend): sửa màn trắng, chat LAN và điều hướng đăng nhập
