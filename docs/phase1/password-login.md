# Đăng nhập tên và mật khẩu trong Phase 1

Form chung từ `main` gọi `POST /api/v1/auth/login`, được chuyển tới Business `/v1/auth/login`. Người học nhập username, cán bộ nhập email vào cùng ô. Server trả access/refresh token, thời hạn, role và trạng thái consent. Frontend giữ role thật; learner chưa đồng ý dịch vụ phải qua consent. Reviewer không bị chuyển thành learner.

Migration **0016** thêm `learner_credential`: username duy nhất, password hash Argon2id và liên kết learner hiện có. Chat không được đọc bảng này. Username không có trong `/me` hoặc payload dựng cho model. Xóa tài khoản ở cả erase và keep_pseudonymous đều xóa credentials. API mã kích hoạt và staff login cũ vẫn phục vụ client cũ.

Username người học có 3–64 ký tự ASCII: chữ, số, dấu chấm, gạch dưới hoặc gạch ngang, bắt đầu bằng chữ/số. Server chuẩn hóa viết thường và bỏ khoảng trắng đầu/cuối. Username không chứa `@`, tránh trùng namespace email cán bộ. Mật khẩu cấp/đặt lại có 12–1024 ký tự, giữ nguyên khoảng trắng. Chưa mở tự đăng ký hoặc khôi phục mật khẩu qua email.

## Chạy local

Tại gốc repo, chạy `npm.cmd run dev:full` để build, migration và seed. Giữ provider AI `disabled` khi server AI chưa bật.

| Loại | Tên đăng nhập | Mật khẩu local |
|---|---|---|
| Người học | `learner.demo` | `AlphaLocal2026!` |
| Quản trị | `admin@alpha.local` | `AlphaLocal2026!` |
| Xem báo cáo | `viewer@alpha.local` | `AlphaLocal2026!` |

Seed chỉ gắn credentials vào demo learner nếu chưa có; không ghi đè mật khẩu đã đổi, consent hoặc lịch sử. Tài khoản mẫu chỉ được seed trong dev/test. Nếu demo learner đã có username khác, dùng tài khoản đó; không tự thay danh tính hoặc chiếm username đang thuộc learner khác.

## Cấp tài khoản trên Windows

Mở PowerShell tại gốc repo. Các lệnh tool sau dùng database Phase 1 và hỏi mật khẩu hai lần; không truyền mật khẩu qua tham số dòng lệnh:

```powershell
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml run --rm -it --no-deps seed python -m app.cli create-learner --username hocvien.01 --name "Học viên 01"
```

Gắn credentials vào learner đã có, giữ nguyên dữ liệu học, bằng đúng ID do người vận hành xác định:

```powershell
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml run --rm -it --no-deps seed python -m app.cli create-learner --username hocvien.01 --learner-id 123
```

Lệnh từ chối username đã dùng hoặc learner đã có credentials. Không tự nối hai tài khoản. Khi tự động hóa, CLI cũng đọc `LEARNER_PASSWORD` từ môi trường tiến trình; không ghi giá trị vào Git, ảnh hoặc log.

## Đặt lại mật khẩu

```powershell
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml run --rm -it --no-deps seed python -m app.cli reset-learner-password --username hocvien.01
```

Lệnh thu hồi các access/refresh token hiện có. Login và refresh dùng chung khóa learner với reset để phiên cũ không sống lại khi chạy đồng thời. Mã kích hoạt cũ vẫn là phương thức độc lập để tương thích; lệnh này không thu hồi mã kích hoạt. Learner inactive không đăng nhập được.

Đăng nhập sai trả lỗi chung, có giới hạn sai theo IP và khóa PostgreSQL dùng chung giữa Business instances. Endpoint staff cũ/mới dùng cùng bucket staff. Log không ghi body đăng nhập. Các biện pháp này chưa thay thế nghiệm thu bảo mật và vận hành staging.

## Kiểm chứng local ngày 10/11/2026

- 88 ca tài khoản/schema và 52 ca Phase 1 đạt trên database test riêng; gồm reset chạy đồng thời với login/refresh, xóa tài khoản, quyền Chat bị từ chối và token được dùng qua hai Business instances.
- Bộ contract có 310 ca đạt và 97 ca bỏ qua có chủ đích. Một assertion số lượng operation cũ được cập nhật từ 48 lên 49 handler Alpha đã triển khai rồi chạy lại đạt; các kết quả này đến từ hai lượt, không phải một lượt sạch duy nhất.
- 124 unit test frontend, build và lint đạt. 18 ca E2E đạt qua Vite và 18 ca tương ứng đạt qua bản build Caddy ở desktop/mobile; mỗi lượt bỏ qua 2 ca cần scripted vì generation đang disabled. Gồm login learner/staff, consent, học/ôn/thi, tiến độ, dashboard và hai bản sửa dữ liệu.
- Demo account đã đăng nhập HTTP 200; runtime ở migration 0016. Kiểm tra trực tiếp quyền SELECT credentials: Chat bị từ chối, Business được phép.
- Ảnh form mới, JSON và log tại `%TEMP%/docprep-password-login-20261110/`; XML backend ở thư mục `.local` của worktree review tách riêng. Browser plugin không có nên dùng Playwright/Chromium. Không gọi AI thật và chưa nghiệm thu staging hoặc tải GPU.
