# Ghép frontend vào nhánh backend — cập nhật 10/11/2026

## Cập nhật theo lựa chọn đăng nhập tên và mật khẩu

Sau lần ghép dưới đây, người phụ trách chọn mở rộng backend để người học cũng dùng username/password. Trạng thái hiện tại: form chung của `main`, API `/v1/auth/login` thuộc Business, migration 0016 và bảng credentials riêng; giữ token pair, role thật, consent và client mã kích hoạt cũ. Nội dung lần ghép bên dưới mô tả bước trung gian trước lựa chọn này. Xem [runbook cấp tài khoản và đặt lại mật khẩu](password-login.md).

## Lần ghép ngày 10/11/2026

Nhánh đích là `feat/alpha-v1-backend-2`. Nguồn giao diện mới là `origin/main` tại `46f6b3e63c336c9c26f9d083b09a1d639e153769`. Trước khi ghép, hai bản sửa tên từ API và thống kê demo bỏ qua câu trống đã được lưu ở `d525c69`; nhánh checkpoint là `checkpoint/alpha-v1-backend-2-before-main-20261110`.

- Nhận phần giải thích gọn hơn trong practice và xem lại bài thi: bỏ tiêu đề lặp, giữ phân loại câu hỏi, nội dung giải thích và trích dẫn.
- Nhận cách khóa form khi đang đăng nhập, chặn gửi lặp và cải tiến xử lý lỗi từ `main`.
- Điều chỉnh helper đăng nhập của `main` theo Phase 1: cán bộ gửi email/mật khẩu tới `/api/v1/auth/staff/login`, giữ nguyên access token, refresh token và role do server trả về. Người học tiếp tục dùng `/api/v1/auth/activate`, qua consent và chọn học phần như trước.
- Không dùng contract YHDP `/api/v1/auth/login` với token đơn hoặc tự gán mọi tài khoản thành learner. Backend Phase 1 hiện chưa hỗ trợ đăng nhập tên/mật khẩu cho người học. Proxy Vite tiếp tục dùng quy tắc chung `/api` → `/v1`, tương thích Caddy.
- Giữ hai bản sửa dữ liệu, runtime notice, API học/ôn/thi/tiến độ và SSE. Không đổi backend, OpenAPI, migrations hoặc biến môi trường riêng trong lần ghép này.

Kiểm tra mới trên Windows, frontend Vite `http://127.0.0.1:5191` kết nối môi trường PostgreSQL/Redis riêng qua Caddy `18881`, provider `disabled`:

- **124/124** unit tests frontend đạt; build và lint đạt.
- **18/18** ca trình duyệt được chạy đạt trên Chromium desktop 1440×1000 và mobile 390×844. Gồm 8 ca dùng API/database thật và 10 ca demo/đối chiếu contract. Hai ca phục hồi SSE yêu cầu scripted bị bỏ qua đúng điều kiện; không coi AI disabled là một lượt generation thành công.
- Các luồng được kiểm tra: learner activation/consent/học/ôn/thi/tiến độ, dashboard viewer/admin, lỗi AI disabled, tên do API cung cấp, fallback response cũ và thống kê demo bỏ trống. Không phát hiện lỗi JavaScript trong các ca này.
- Browser plugin không có trong phiên kiểm tra nên dùng Playwright. Config, JSON, log và ảnh QA lưu ngoài repository tại `%TEMP%/docprep-main-integration-20261110/`.

Các kết quả và nguồn ngày 07–08/11 dưới đây là lịch sử của lần ghép trước, không phải số liệu chạy lại ngày 10/11.

## Lần ghép trước ngày 08/11/2026

Thay đổi áp dụng tại **gốc repository**, nơi `src/`, `tests/`, `backend/` và `deploy/` nằm cùng cấp. Hai thư mục con `Docprep/` và `Docprep-feat-alpha-v1-backend/` là các bản riêng trong workspace, không thuộc nội dung ghép vào Git.

## Nguồn và cách giải quyết

Nhánh đích là `feat/alpha-v1-backend-2`, bắt đầu tại `13fb683` và ghép `origin/main` tại `18ac4cf`, cũng là commit của repo frontend `Docprep/`. Nhánh `feat/alpha-v1-backend` giữ nguyên tại `13fb683`. Đã giải quyết 11 file conflict, nhận các thay đổi không xung đột từ frontend và giữ phần tích hợp Phase 1:

- Giữ runtime notice và nhịp học từ máy chủ trong live mode.
- Giữ chat SSE, resume/cancel turn, lọc dữ liệu đầu vào, render Markdown và trích dẫn.
- Giữ trang chủ theo phiên học, mục tiếp tục gần nhất và gợi ý gia sư của nhánh backend.
- Nhận giao diện chọn hình thức thi, phân trang kết quả, phân loại câu hỏi và phân tích 54 vấn đề.
- Kết hợp CSS cho trang chủ Phase 1 với CSS mới của thi thử và phân loại câu hỏi.
- Giữ test SSE Phase 1, nhận test phân tích vấn đề và cập nhật test demo cho các bộ đề mới.

Sau khi ghép frontend, backend và OpenAPI được bổ sung dữ liệu thống kê/phân loại, phạm vi đề và giới hạn ôn thẻ để khớp giao diện mới; xem [bản sửa hợp đồng và kiểm chứng](../testing/frontend-backend-contract-fix.md). Migration, seed và dependency/lockfile giữ nguyên. Dữ liệu demo không được dùng thay số liệu live.

## Kiểm tra bản ở gốc repo

- `npm.cmd run build`: đạt.
- `npm.cmd run lint`: đạt.
- `npm.cmd test`: 116/116 đạt, không có test bỏ qua.
- `e2e/frontend-merge.spec.ts`: 4/4 đạt trên Edge desktop 1440×1000 và mobile 390×844, chạy với production build qua Vite preview.
- Không còn dấu conflict trong mã frontend và test.

Các ca frontend-merge dùng dữ liệu demo và response Alpha giả lập để kiểm tra tương thích. Kiểm thử tiếp theo chạy với PostgreSQL/Redis thật: 174 ca regression backend và 16 ca tích hợp desktop/mobile qua Vite/Caddy đạt. Bộ test bổ sung được tạo ngoài repo theo yêu cầu: 9 ca frontend, 4 ca backend và 4 lượt kiểm tra giao diện mới đều đạt; tổng lượt kiểm thử gần nhất là 125 frontend, 178 backend và 20 ca giao diện. Các file test bổ sung và artifact ngoài repo không được đưa vào commit. Provider AI giữ disabled; chưa kiểm chứng model thật.

Bản sao trước khi sửa, index Git cũ, hash backend/cấu hình và artifact kiểm thử được lưu trong `.local/root-frontend-merge-20261107-200429/`. Các file conflict đã được giải quyết; toàn bộ thay đổi được tập trung trên `feat/alpha-v1-backend-2`, giữ nguyên nhánh backend ban đầu.
