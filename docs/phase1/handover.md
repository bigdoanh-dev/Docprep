# Bàn giao Phase 1 local

Đợt này tách Business/Chat và bổ sung điều phối, phục hồi, bảo mật, quan sát. Provider thật vẫn khóa vì chưa có protocol/GPU được duyệt. Xem [kiến trúc](architecture.md) và [bằng chứng kiểm thử](verification.md).

## Chạy trên Windows

Mở Docker Desktop, chạy từ đúng repository:

```powershell
cd "D:\InternAIRC\AI_TuTor\ALPHAV1\Docprep_FE"
powershell -ExecutionPolicy Bypass -File scripts/setup-phase1.ps1
```

Script tạo `.env.phase1` với credentials ngẫu nhiên khi file chưa tồn tại, dựng image, chuẩn bị role, chạy migration/grants một lần rồi khởi động bốn app. Seed chỉ chạy trong dev/test và giữ lại dữ liệu đã có. Không dùng mật khẩu mẫu của Alpha cho PostgreSQL/Redis Phase 1.

Mở **http://127.0.0.1:18880**. Learner local: `DEMO-0001`; staff local: `admin@alpha.local` hoặc `viewer@alpha.local`, mật khẩu `AlphaLocal2026!`. Đây là tài khoản minh họa được seed trong database Phase 1 riêng. Không tạo các tài khoản này trong production.

Nếu đã có dữ liệu và chỉ muốn cập nhật runtime:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-phase1.ps1 -SkipSeed
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml ps
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml logs --tail 50 chat-1 chat-2
```

Alpha vẫn dùng `docker-compose.yml`, volume/project và cổng 15433 cũ. Phase 1 dùng project `docprep-phase1`, volume `phase_pg` và mạng riêng; không đưa cổng DB/Redis/backend ra host. Không dùng `down -v` để khởi động lại.

Nếu cần Vite hot reload: cấu hình `BACKEND_URL=http://127.0.0.1:18880`, khởi động lại Vite rồi mở cổng 5190. Frontend gọi `/api/v1`, Vite chuyển `/v1` cho Caddy; Caddy hỗ trợ cả hai prefix. Khi quay lại Alpha, đổi BACKEND_URL về `http://127.0.0.1:8000`.

## Kiểm thử tái lập

Có thể chạy tuần tự toàn bộ nhóm kiểm tra bằng `powershell -ExecutionPolicy Bypass -File scripts/test-phase1.ps1`; thêm `-IncludeAlphaRegression` hoặc `-IncludeLoad` khi cần. Script chủ động kiểm tra phục hồi nên chỉ chạy lúc không có người đang demo. Full regression Alpha cần database `DATABASE_URL_TEST` riêng theo cấu hình Alpha.

Tạo database kiểm thử riêng một lần; lệnh này báo lỗi nếu đã tồn tại, không xóa/ghi đè:

```powershell
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml exec -T db createdb -U phase_owner phase1_test
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml run --rm --no-deps test
```

Fixture chỉ được phép dựng lại `phase1_test`, Redis namespace bắt đầu bằng `test:` và UUID riêng. Không trỏ bộ test Alpha hoặc Phase 1 vào database demo. Regression Alpha:

```powershell
Push-Location backend
.venv/Scripts/python.exe -m app.cli export-openapi --check
.venv/Scripts/python.exe -m pytest -q
Pop-Location
npm.cmd test
npm.cmd run build
npm.cmd run lint
```

Trình duyệt qua Caddy:

```powershell
$env:PHASE1_URL = 'http://127.0.0.1:18880'
npm.cmd run test:e2e
Remove-Item Env:PHASE1_URL
```

Chạy các kiểm tra sau **lần lượt**, khi không có người đang demo: phép kiểm tra triển khai chủ động restart Redis, kill một Chat replica, drain và tạo lại Chat, backup/restore sang DB mới. Kiểm tra TLS tạm chuyển Caddy sang localhost HTTPS rồi phục hồi cấu hình HTTP.

```powershell
backend/.venv/Scripts/python.exe -X utf8 scripts/verify-phase1.py
backend/.venv/Scripts/python.exe -X utf8 scripts/verify-phase1-tls.py
```

TLS test dùng CA cục bộ của Caddy với xác minh certificate qua Python SSL context; không cài CA vào hệ thống, không tắt kiểm tra chứng chỉ. Nó không chứng minh đã deploy DNS/ACME công khai.

## Baseline tải

Tạo 50 learner synthetic riêng; token chỉ ghi vào `.local` bị Git bỏ qua:

```powershell
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml run --rm --no-deps seed python -m app.phase_cli seed-load --output /artifacts/phase1-load-tokens.json
foreach ($learners in @(30,40,50)) {
  backend/.venv/Scripts/python.exe -X utf8 scripts/load-phase1.py --tokens .local/phase1-load-tokens.json --learners $learners --seconds 60 --output ".local/phase1-load-$learners.json"
}
```

Workload mặc định minh họa: mỗi learner dùng token riêng, 10% lần thao tác gọi AI, phần còn lại đọc Home/modules/cards/progress/exams, think time 1–3 giây, seed 42. Đây chưa phải workload Lead duyệt. Harness ghi status codes, instance và p50/p95 hoàn tất request; scripted không đại diện tốc độ GPU, token hay chất lượng AI. Không chạy đồng thời baseline với fault injection hoặc full regression nếu cần kết quả so sánh.

## Monitoring và sao lưu

```powershell
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml --profile monitoring up -d prometheus grafana
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml --profile operations up -d backup
powershell -ExecutionPolicy Bypass -File scripts/backup-phase1.ps1 -RestoreDatabase phase1_restore_manual_check
```

Grafana: http://127.0.0.1:13000, user `admin`, password từ `GRAFANA_PASSWORD` trong `.env.phase1`. Dashboard được provision sẵn; Prometheus/metrics chỉ ở mạng nội bộ. Quarantine khác 0 cần kiểm tra các model-call record trước khi trả slot. Chưa cấu hình kênh gửi cảnh báo cho người khác.

Backup profile tạo custom dump mỗi 24 giờ vào named volume, không tự xóa bản cũ. Script restore chỉ tạo DB mới tên `phase1_restore_*`; nếu tên đã tồn tại thì dừng. Muốn giữ bản sao ngoài host, dùng `docker compose ... cp db:/backups/<file>.dump <đường-dẫn>` và cơ chế lưu trữ đã được tổ chức duyệt.

## Release và xử lý sự cố

Build image trước rồi cập nhật từng instance, kiểm tra một bản khỏe trước khi chuyển bản tiếp theo:

```powershell
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml build api-1 caddy
powershell -ExecutionPolicy Bypass -File scripts/release-phase1.ps1 -Service chat-1
powershell -ExecutionPolicy Bypass -File scripts/release-phase1.ps1 -Service chat-2
```

Drain dùng SIGUSR1 bên trong container Linux. Instance ngừng nhận request/claim mới, readiness trả 503; script chờ running turns và chờ proxy rút upstream. Nếu timeout, script giữ trạng thái drain để kiểm tra, không tự kill. Chỉ deploy lần lượt các code version đã kiểm tra tương thích schema; không cho bốn instance tự chạy Alembic.

Khi Redis mất dữ liệu, worker dựng lại queue/locks/reservations từ PostgreSQL. Event tiến trình đã mất không được tái tạo giả; client đọc snapshot. Khi worker chết trong model call, turn bị interrupted và slot giữ cách ly. Sau khi xác minh lời gọi đã dừng, người vận hành có thể chạy bằng môi trường migrator/owner:

```powershell
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml run --rm --no-deps migrate python -m app.phase_cli release-model-call <call-uuid> --confirm-stopped
```

Lệnh này là xác nhận thủ công, không kiểm tra GPU giúp người vận hành. Không dùng chỉ vì lease hết hạn.

## Điều kiện mở model hoặc staging thật

- Model protocol, URL, ID, authentication, health/cancel/timeout semantics và resource/slot budget được duyệt.
- Tập nội dung, privacy/retention/consent và đánh giá AI phù hợp với phạm vi pilot.
- Hostname/DNS hợp lệ, secrets mới và `APP_ENV=production`; generation để disabled khi chưa có provider hợp lệ.
- Ngưỡng p95, tỷ lệ lỗi, thời gian chờ và workload được Lead xác nhận; đo lại trên hạ tầng thực.

`compose.https.yml` chỉ là cấu hình sẵn cho hostname được duyệt; không có endpoint GPU, địa chỉ WireGuard hay bí mật hạ tầng được tự điền. Các chức năng ngoài phạm vi vẫn 501/chưa hỗ trợ.
