# Chạy AI Tutor / DocPrep trên Windows

Hướng dẫn cho nhánh `feat/alpha-v1-backend`, sử dụng backend Phase 1: hai Business API, hai Chat Orchestrator, PostgreSQL, Redis và Caddy. AI đang tắt (`PHASE_MODEL_PROVIDER=disabled`); các chức năng nghiệp vụ và lịch sử vẫn sử dụng API/database thật. Nút dùng dữ liệu trải nghiệm là chế độ demo riêng trong trình duyệt.

## 1. Chuẩn bị

- Cài Node.js 22.12 trở lên và Docker Desktop với Linux engine. Máy đang dùng Node.js 24.
- Mở Docker Desktop và đợi Engine chạy. Lệnh sau phải trả phiên bản Server:

```powershell
docker version --format '{{.Server.Version}}'
```

Mở PowerShell tại đúng thư mục chứa `package.json`:

```powershell
cd D:\InternAIRC\AI_TuTor\ALPHAV1\Docprep_FE
```

Không chạy npm từ thư mục `ALPHAV1` phía ngoài: thư mục đó không có `package.json`.

## 2. Khởi động toàn bộ dự án

```powershell
npm.cmd run dev:full
```

Lệnh dùng `scripts/start-local.ps1` để dựng database/Redis, build image, chạy migration, cấp quyền database, seed dữ liệu local và mở Vite. Lần đầu có thể cần vài phút để tải image và dependency. Giữ terminal này mở khi sử dụng frontend.

| Địa chỉ | Chức năng |
|---|---|
| http://127.0.0.1:5190/dang-nhap | Giao diện Vite, tự cập nhật khi sửa frontend |
| http://127.0.0.1:18880/dang-nhap | Giao diện đã build, phục vụ qua Caddy |
| http://127.0.0.1:18880/api/health | Trạng thái Chat/runtime |

Cổng `18880` lấy từ `PHASE_HTTP_PORT` trong `.env.phase1`. Khi đổi cổng này, dùng lại `dev:full` để Vite nhận đúng proxy. Caddy bỏ `/api` trước khi chuyển request về backend `/v1`.

Chỉ cần bản build qua Caddy, không cần Vite:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/setup-phase1.ps1
```

Backend đã chạy và không cần build/migration/seed lại:

```powershell
npm.cmd run dev:full -- -SkipSetup
```

## 3. Đăng nhập

| Loại tài khoản | Tên đăng nhập | Mật khẩu local mặc định |
|---|---|---|
| Người học | `learner.demo` | `AlphaLocal2026!` |
| Quản trị | `admin@alpha.local` | `AlphaLocal2026!` |
| Xem báo cáo | `viewer@alpha.local` | `AlphaLocal2026!` |

Người học mới cần đồng ý dịch vụ trước khi học. Seed không ghi đè mật khẩu đã đổi hoặc lịch sử đã lưu. Nếu đã đổi mật khẩu, dùng mật khẩu hiện tại; xem [cách cấp/đặt lại tài khoản](docs/phase1/password-login.md).

Đây là tài khoản minh họa local. Không dùng bộ mật khẩu này khi triển khai online. Giữ `.env.phase1` và `backend/.env` ngoài Git; không bật Ollama khi AI server chưa sẵn sàng.

## 4. Dừng và mở lại

Nhấn `Ctrl+C` trong terminal Vite để dừng frontend. Docker vẫn chạy backend. Để dừng stack và giữ dữ liệu:

```powershell
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml stop
```

Mở lại bằng `npm.cmd run dev:full`. PostgreSQL lưu trong named volume. Không dùng `docker compose down -v` nếu cần giữ tài khoản và dữ liệu học.

## 5. Kiểm tra và xử lý lỗi

Kiểm tra container và API từ thư mục `Docprep_FE`:

```powershell
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml ps
Invoke-RestMethod http://127.0.0.1:18880/api/health
```

Xem log khi khởi động lỗi:

```powershell
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml logs --tail 80 migrate api-1 api-2 chat-1 chat-2 caddy
```

| Lỗi | Cách xử lý |
|---|---|
| `ENOENT ... package.json` | Chuyển vào `Docprep_FE` rồi chạy npm lại. |
| Không tìm thấy pipe `dockerDesktopLinuxEngine` | Mở Docker Desktop, đợi Engine chạy rồi kiểm tra `docker version`. |
| Docker báo thiếu Virtual Machine Platform | Bật tính năng Windows theo thông báo Docker và khởi động lại máy; chưa cần sửa Dockerfile. |
| PowerShell chặn `npm.ps1` | Dùng `npm.cmd` như các lệnh trong hướng dẫn. |
| Cổng 5190 đang được dùng | Dùng cửa sổ Vite đã chạy hoặc dừng đúng tiến trình cũ; có thể chạy `npm.cmd run dev:full -- -SkipSetup -Port 5191`. |
| Giao diện mở nhưng API 502/không đăng nhập được | Kiểm tra container và `/api/health`, sau đó khởi động bằng `dev:full` để nhận đúng proxy. |
| Vừa sửa `.env` nhưng container vẫn dùng giá trị cũ | Chạy lại `dev:full` để tạo lại container khi cần; `docker compose restart` không nạp biến môi trường mới. |
| Chat báo AI chưa sẵn sàng | Đây là trạng thái dự kiến khi provider là `disabled`; không phải xác nhận model thật đã hoạt động. |

Sau khi sửa frontend và muốn cập nhật bản giao diện tại cổng 18880, chạy lại `setup-phase1.ps1`. Vite ở cổng 5190 cập nhật trực tiếp khi sửa source.

## 6. Kết quả chạy trên máy ngày 12/11/2026

- Docker Engine 29.6.2; Node.js 24.14.0; npm 11.9.0. Setup kết thúc với mã 0; PostgreSQL, Redis và cả bốn ứng dụng API/Chat đều healthy. Database ở migration `0016`.
- Vite chạy tại cổng 5190, Caddy tại cổng 18880; runtime là `real`, model provider `disabled`.
- Playwright/Chromium kiểm tra cả hai địa chỉ ở chiều rộng 1440 và 390: đăng nhập `learner.demo` trả HTTP 200, `/me` trả 200, tải lại vẫn giữ đăng nhập. Nút hiện/ẩn mật khẩu hoạt động; không tràn ngang, không có lỗi console/page hoặc Vite overlay. Thông báo AI đang tắt đã được gỡ khỏi giao diện.
- Browser plugin không có trong phiên kiểm tra nên dùng Playwright. Log và ảnh local nằm ở `%TEMP%\docprep-start-20261112`; log setup ở `%TEMP%\docprep-start-phase1-20261112.log`.
- Lượt này kiểm tra khởi động và đăng nhập; chưa chạy lại toàn bộ regression, luồng học/thi hay model AI thật.

Xem thêm [kiến trúc Phase 1](docs/phase1/architecture.md) và [hướng dẫn bàn giao](docs/phase1/handover.md).
