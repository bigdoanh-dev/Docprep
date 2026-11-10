# Frontend kết nối backend Phase 1 local

Frontend mới tại gốc repo gọi API thật qua cùng origin:

```text
Trình duyệt :5190 → Vite /api/* → Caddy :18880 → Business API / Chat → PostgreSQL / Redis
Trình duyệt :18880 → Caddy phục vụ bản build và định tuyến /api/* trực tiếp
```

## Chạy trên Windows

Mở Docker Desktop rồi chạy tại gốc repo:

```powershell
npm.cmd run dev:full
```

Lệnh chạy setup Phase 1, migration và seed local theo script hiện có, kiểm tra `/api/health` trả runtime thật, sau đó mở Vite. Setup giữ dữ liệu đã có; không reset database. Khi backend đã chạy:

```powershell
npm.cmd run dev:full -- -SkipSetup
```

- Frontend phát triển: `http://127.0.0.1:5190/dang-nhap`.
- Bản build Docker: `http://127.0.0.1:18880/dang-nhap`.
- Người học local: `learner.demo` / `AlphaLocal2026!`; cán bộ nhập email vào cùng form. Xem [cấp tài khoản](password-login.md).
- Tài khoản cán bộ local theo README. Nút dùng dữ liệu trải nghiệm vẫn chỉ dùng demo trong trình duyệt.

Script `scripts/start-local.ps1` lấy `PHASE_HTTP_PORT` từ `.env.phase1` hoặc biến môi trường, mặc định `18880`, rồi đặt `BACKEND_URL` cho Vite. Có thể dùng `-Port 5191` khi cần cổng frontend khác. Trong phiên cấu hình hiện tại, `.env.local` cũng đặt `BACKEND_URL=http://127.0.0.1:18880` để `npm.cmd run dev` hoạt động trực tiếp. Các file môi trường thật không được commit.

## Chat và dữ liệu

Chat đã nối tới API Phase 1. Mặc định `PHASE_MODEL_PROVIDER=disabled`: đọc lịch sử được, nhưng yêu cầu sinh câu trả lời trả `503 ai_disabled` và giao diện hiển thị thông báo. Không coi đây là đã kết nối model Ollama thật; xem `ollama-local.md` để cấu hình server/model riêng.

Backend đã bổ sung dữ liệu phân loại câu hỏi và phân tích chi tiết cho frontend mới. Xem [bản sửa hợp đồng và kiểm chứng](../testing/frontend-backend-contract-fix.md) về thống kê 3 nhóm nhận thức, 54 vấn đề, phạm vi đề và giới hạn ôn thẻ. Kết nối live không đưa kết quả demo vào các số liệu này.

## Kiểm tra kết nối thật

`e2e/alpha.spec.ts` kiểm tra đăng nhập, consent, học và ghi đáp án, ôn FSRS, chọn/nộp đề qua giao diện mới, autosave/resume, tiến độ, dashboard và phản hồi chatbot theo provider. Luồng nghiệp vụ vẫn chạy khi AI disabled. `e2e/offline.spec.ts` kiểm tra lỗi AI rõ ràng, không tạo câu trả lời hoặc citation giả.

Kết quả ngày 07/11/2026: **8/8 ca qua Vite 5190 và 8/8 ca qua Caddy 18880 đều đạt**, tổng cộng 16 ca desktop/mobile, không bỏ qua ca nào. Artifacts nằm trong `.local/live-integration/`. Các ca này dùng API, PostgreSQL và Redis thật, cấp mã test riêng qua fixture; không dùng API giả lập. Provider cuối giữ `disabled`.
