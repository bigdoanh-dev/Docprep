# Ghép frontend vào nhánh backend — cập nhật 08/11/2026

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
