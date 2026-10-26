# Bàn giao Alpha V1

## Kiến trúc và cấu hình

Vite `:5190` nhận `/api/*`, bỏ prefix `/api` rồi chuyển tới FastAPI `:8000`. FastAPI giữ `/v1`, error envelope, token opaque, refresh rotation, role và consent của backend demo. PostgreSQL 16 ở Docker `:15433`, named volume riêng. Không cần Redis, queue ngoài, GPU hoặc tài khoản dịch vụ AI.

API kiểm tra quyền; service điều phối nghiệp vụ/transaction; repository giữ SQL; engine tính lịch ôn, ưu tiên và chấm điểm. Migration giữ nguyên chuỗi `0001`–`0012`. OpenAPI được xuất từ code và kiểm tra drift bằng `python -m app.cli export-openapi --check`.

`MODEL_PROVIDER=scripted` thay gateway sinh nội dung. Retrieval, pre-gate, post-check, DB, citations và SSE giữ luồng thật. Provider chỉ hoạt động khi `APP_ENV` ghi rõ `dev` hoặc `test`. Thông tin runtime nằm ở `/health` ngoài `/v1`, frontend lấy qua `/api/health`. Không đổi schema của API `/v1`.

Không dùng số liệu thời gian/token/chi phí của gateway scripted để kết luận hiệu năng hoặc chất lượng AI thật. Cohort synthetic có cờ riêng; learner demo không được cấp ngân hàng câu hỏi synthetic. Dashboard giữ ngưỡng ẩn nhóm dưới 10; dữ liệu của từng cơ sở có thể bị ẩn với cohort nhỏ.

## Kịch bản trình diễn 10–15 phút

1. **1 phút — kiểm tra hệ thống:** `/health` trả `real`, `scripted`; frontend có nhãn minh họa. Không chọn demo trong trình duyệt.
2. **2 phút — onboarding:** nhập `DEMO-0001`, đồng ý dịch vụ, chọn học phần đầu tiên có nội dung. Research consent không bắt buộc. Với tài khoản đã dùng, giới thiệu hồ sơ và chọn lại học phần thay vì hứa xuất hiện onboarding lần nữa.
3. **3 phút — học:** mở chủ đề, đọc nội dung, trả lời sai một câu để thấy phản hồi và tạo thẻ; reload để chứng minh đáp án đã lưu. Đi hết unit rồi mở phiên học hôm nay để thấy trạng thái backend điều phối.
4. **1 phút — ôn thẻ:** mở thẻ đến hạn, hiện đáp án, đánh giá mức nhớ; kiểm tra lượt ôn/lịch đã thay đổi. Nếu thẻ vừa ôn chưa đến hạn, dùng tài khoản mới thay vì sửa ngày trong database.
5. **3 phút — thi:** chọn đề ngắn có sẵn, trả lời vài câu, reload, nộp và xem kết quả. Nếu bấm “làm lượt mới”, lượt đang mở được nộp với các đáp án đã lưu rồi mới tạo lượt mới.
6. **2 phút — AI:** hỏi “Tỷ lệ hiện mắc là gì?”, mở nguồn; reload thấy lịch sử. Hỏi “Tỷ lệ mắc là gì?” để thấy làm rõ; thử câu ngoài kịch bản. Nộp bài thi trước khi hỏi AI vì frontend đang chặn chat khi thi.
7. **2 phút — quản trị:** đăng xuất, dùng form Cán bộ với admin/viewer, mở dashboard. Giải thích đây là cohort minh họa, nhóm nhỏ vẫn bị ẩn. Không trình diễn CSV như chức năng đã hoàn thành.

Muốn có learner mới để trình diễn lại onboarding: chạy `backend/.venv/Scripts/python.exe -m seed.browser` từ thư mục `backend`; dùng mã vừa được in. Lệnh chỉ phát mã local, không sửa tài khoản cũ.

## Vận hành local

- `.env` là cấu hình runtime; giữ `DATABASE_URL_TEST` riêng. Lock dependency Python ở `backend/requirements-lock.txt`, Node ở `package-lock.json`.
- `setup-alpha.ps1` giữ trạng thái đã có. `seed-alpha` chỉ tạo staff còn thiếu, không đổi mật khẩu staff cũ. Dùng `create-staff` để tạo tài khoản khác; không coi seed là chức năng quản lý người dùng.
- Cohort được nạp theo thời gian chạy lần đầu. Khi demo vào tháng khác, chọn kỳ có dữ liệu; muốn tái tạo kỳ hiện tại thì backup và reset dev có chủ đích.
- Khi API không kết nối: kiểm tra Docker, `docker compose ps`, backend `/health`, rồi Vite. Nếu nhận HTML thay vì JSON, kiểm tra đúng cổng dev/proxy.
- Khi port bận, dừng đúng dịch vụ của dự án hoặc đổi đồng bộ cấu hình; không để Vite tự chuyển cổng mà vẫn kiểm thử cổng cũ.
- Rollback code bằng checkout commit đã kiểm thử và lockfile tương ứng. Nếu cần phục hồi dữ liệu, restore sang DB mới, kiểm tra rồi mới đổi `DATABASE_URL`. Chưa có migration mới ngoài chuỗi gốc.

## Backlog sau Alpha

| Ưu tiên | Công việc | Điều kiện mở |
|---|---|---|
| 1 | Nguồn tài liệu và ngân hàng câu hỏi chuẩn | Có quyền sử dụng, phiên bản nguồn và thẩm định chuyên môn |
| 1 | Nhà cung cấp AI thật và bộ đánh giá | Xác nhận model/API đang hỗ trợ, ngân sách, chính sách dữ liệu và bộ câu hỏi đánh giá độc lập |
| 1 | Staging HTTPS | Hosting, secrets, API rewrite trước SPA fallback, kiểm thử SSE qua proxy, backup và giám sát |
| 2 | Nhập CSV và phát mã | Chốt preview/confirm, duplicate, expiry, recovery và quyền staff |
| 2 | Báo lỗi và bàn duyệt | Chốt người xử lý, hai vòng duyệt, audit và quyền truy cập |
| 2 | Luyện tập tự chọn, library card | API/schema, thiếu câu hỏi, filter và phân trang |
| 3 | Đồng bộ thông báo/bookmark/kế hoạch học | Chốt dữ liệu cần đồng bộ và hành vi đa thiết bị |
| Trước pilot | Privacy và vận hành thật | Văn bản consent, retention, policy xóa/xuất, kiểm tra token/browser, suppression giữa nhiều bộ lọc và giới hạn tải |

Alpha local không nghiệm thu chất lượng y khoa, chất lượng mô hình, khả năng tải nhiều lớp học, tính sẵn sàng hoặc khả năng vận hành production.
