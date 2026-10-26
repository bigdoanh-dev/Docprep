# AI Tutor / DocPrep — Alpha V1 local

Frontend React/Vite kết nối FastAPI và PostgreSQL thật. AI chạy **kịch bản cố định, không gọi API mô hình**. Nội dung và số liệu cohort chỉ dùng minh họa, chưa được thẩm định để mở pilot.

## Cài đặt trên Windows

Cần Python **3.13**, Node.js **22.12+**, Docker Desktop đang chạy Linux engine và PowerShell. Chạy các lệnh tại thư mục chứa `package.json`.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-alpha.ps1
npm.cmd exec playwright -- install chromium
```

Setup tạo `.env` từ `.env.example` nếu chưa có, cài dependency theo lockfile, dựng PostgreSQL, chạy 12 migration rồi nạp tài khoản và cohort minh họa. Lần seed sau giữ nguyên mật khẩu, hồ sơ và lịch sử đã có. Cohort đã tồn tại sẽ không được tạo lại hoặc cập nhật thời gian tự động.

Nếu chỉ cần người học và chưa cần dashboard: thêm `-SkipCohort` vào lệnh setup. Tạo cohort lần đầu có thể mất vài phút.

## Chạy dự án

Terminal 1:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-backend.ps1
```

Terminal 2:

```powershell
npm.cmd run dev -- --strictPort
```

- Frontend: http://127.0.0.1:5190/dang-nhap
- Backend: http://127.0.0.1:8000/health
- Swagger: http://127.0.0.1:8000/docs
- PostgreSQL local: `127.0.0.1:15433`; database `alphav1` và `alphav1_test` tách riêng.

Tài khoản local do `seed-alpha` tạo:

| Loại | Đăng nhập |
|---|---|
| Người học | Mã kích hoạt `DEMO-0001` |
| Quản trị | `admin@alpha.local` / `AlphaLocal2026!` |
| Chỉ xem báo cáo | `viewer@alpha.local` / `AlphaLocal2026!` |

Chọn form **Người học** hoặc **Cán bộ** để gọi backend thật. Nút “Dùng dữ liệu trải nghiệm” vẫn là demo trong trình duyệt, không phải đường nghiệm thu Alpha.

Mật khẩu và database credential trên chỉ dành cho môi trường local. Không dùng cấu hình này khi triển khai online. Không commit `.env`.

## AI kịch bản

`.env` dùng `APP_ENV=dev`, `APP_MODE=real`, `MODEL_PROVIDER=scripted`. Giao diện hiện nhãn **AI mô phỏng — dữ liệu minh họa**. Mô hình scripted bị từ chối ngoài dev/test; không cần API key và không tự chuyển sang gọi mô hình thật.

Câu hỏi có câu trả lời và nguồn:

- `Tỷ lệ hiện mắc là gì?`
- `Tỷ lệ mới mắc là gì?`
- `Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?`

Thử thêm `Tỷ lệ mắc là gì?` để thấy yêu cầu làm rõ; hỏi về ca bệnh cụ thể để thấy từ chối; hỏi ngoài kịch bản để thấy thiếu bằng chứng. Nguồn trích dẫn là passage trong PostgreSQL, qua pipeline kiểm tra và lưu lịch sử thật. Phần giải thích quiz chỉ có đáp án kịch bản khi nguồn phù hợp; trường hợp khác trả thiếu bằng chứng.

## Kiểm thử

Giữ backend ở cổng 8000, sau đó chạy:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test-alpha.ps1
```

Lệnh này kiểm tra OpenAPI, chạy pytest, test SSE frontend, build và Playwright desktop/mobile. Playwright tự mở Vite nếu chưa chạy. **Browser plugin not available** trong phiên triển khai; kiểm thử trình duyệt sử dụng Playwright.

Pytest dựng lại schema của `DATABASE_URL_TEST`; phải khác `DATABASE_URL`. Playwright tạo tài khoản `ALPHA-E2E-*` mới qua fixture local, không reset tài khoản `DEMO-0001`. Artifact nằm trong `.local/` và `test-results/`, không commit.

## Backup, phục hồi và reset

```powershell
backend\.venv\Scripts\python.exe scripts/db-maintenance.py backup
backend\.venv\Scripts\python.exe scripts/db-maintenance.py restore backups\TEN_FILE.dump
```

Backup dùng định dạng PostgreSQL custom và ghi nhị phân an toàn trên Windows. Restore luôn tạo database `alphav1_restore_*` mới; không ghi đè database học/test. Đổi tên file trong lệnh restore theo đường dẫn mà backup in ra.

Dừng PostgreSQL bằng `docker compose stop`; mở lại bằng `docker compose up -d --wait`. Named volume giữ dữ liệu khi tạo lại container. Không chạy `docker compose down -v` nếu cần giữ dữ liệu.

**Reset sẽ xóa toàn bộ dữ liệu trong database dev đang cấu hình.** Chỉ dùng khi muốn bắt đầu lại bản demo; backup trước nếu cần:

```powershell
cd backend
.venv\Scripts\python.exe -m app.cli reset-dev
.venv\Scripts\python.exe -m app.cli seed-alpha
```

## Phạm vi và tài liệu

Alpha gồm tài khoản/consent, học, phiên ngày, ôn thẻ đến hạn, thi thử, tiến độ, chat kịch bản và dashboard. CSV, bàn duyệt, luyện tập tự chọn, toàn bộ thư viện thẻ và đồng bộ bookmark/thông báo/lộ trình chưa được mở. Header live dẫn tới nhịp học từ server, không hiển thị streak từ localStorage như số liệu chính thức.

- [Hướng dẫn trình diễn và backlog](docs/alpha-v1/handover.md)
- [Thiết kế kiến trúc hệ thống](docs/alpha-v1/architecture.md)
- [Ma trận 55 API](docs/alpha-v1/api-matrix.md)
- [Kết quả kiểm thử và giới hạn](docs/alpha-v1/verification.md)
- [Hợp đồng frontend chi tiết](docs/handoffs/mobile-backend-handoff.md)

Backend, migration, seed và OpenAPI ban đầu được tiếp nhận từ `NLHN-YHDP-main.zip`; frontend cũ trong ZIP không được nhập. Các handler đã có chỉ được coi là hoạt động trong phạm vi đã kiểm thử ghi ở báo cáo.
