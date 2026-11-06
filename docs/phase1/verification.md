# Kiểm chứng Phase 1 local

**Baseline lịch sử 03/11/2026.** Kết quả dưới đây thuộc code/quota trước tích hợp YHDP. Xem [báo cáo tích hợp 06/11](yhdp-verification.md) để biết trạng thái mới; không coi số tải scripted hoặc số test cũ là kết quả model thật/phiên bản mới.

Ngày thực hiện: 03/11/2026. Phạm vi là hạ tầng và điều phối bằng scripted/fake, không phải nghiệm thu GPU, nội dung chuyên môn hoặc production. Chỉ ghi PASS cho những kiểm tra đã chạy; báo cáo Alpha ngày 26/10 là bằng chứng lịch sử riêng.

## Môi trường và phiên bản

- Repository đang ở nhánh `feat/alpha-v1-backend`; thay đổi Phase 1 nằm trong working tree, chưa commit/push.
- Windows PowerShell, Docker Desktop Linux engine; project mới `docprep-phase1`, không dùng volume PostgreSQL của Alpha.
- Runtime container: Python 3.13.18, FastAPI 0.143.0, Pydantic 2.14.0, redis-py 6.4.0, prometheus-client 0.26.0; PostgreSQL 16, Redis 7.4, Caddy 2.10.2. Dependency Python/Node theo lockfile của repository.
- Một process mỗi app container: api-1/api-2/chat-1/chat-2. Host local `127.0.0.1:18880`; backend/DB/Redis không có host port.
- `APP_MODE=real`, `APP_ENV=dev`, `PHASE_MODEL_PROVIDER=scripted`; schema mới `0014`, 48 bảng public. Runtime model thật mặc định disabled nếu không cấu hình provider dev/test.

## Kết quả đã thực thi

| Nhóm | Bằng chứng | Kết quả |
|---|---|---|
| Phase 1 PostgreSQL/Redis | `.local/phase1-tests.xml` | 22 PASS, 92,18 giây; hai app Chat và worker subprocess dùng DB/Redis thật |
| Full regression Alpha, chạy mới | `.local/phase1-alpha-regression.xml` | 1.122 PASS, 95 SKIP, 0 FAIL; 1.754,28 giây (29 phút 14 giây) |
| Migration, schema, thi, xóa tài khoản, contract Alpha | `.local/phase1-targeted-alpha.log` | 214 PASS, 47 SKIP |
| SSE/chat/hint/scripted Alpha | `.local/phase1-targeted-streams.log` | 58 PASS sau khi giữ payload status Alpha tương thích |
| Frontend unit | `npm.cmd test` | 6 PASS |
| Build và lint | `.local/phase1-build.log`, `npm.cmd run lint` | PASS |
| Browser qua Caddy | `.local/phase1-browser.log` | 8 PASS, 36,1 giây; desktop/mobile, staff, học/ôn/thi/tiến độ/chat/citation và mất response POST |
| Routing, AI, restart và failover | `.local/phase1-deployment.json` | PASS; gồm bốn trạng thái, citation, idempotency, hai Business replicas, Redis restart và một Chat replica bị kill |
| Backup/restore | Cùng deployment report | 48/48 bảng có row count và digest khớp database restore riêng |
| Tạo lại PostgreSQL container | Cùng deployment report | 48/48 bảng giữ nguyên digest và row count sau force-recreate, dùng lại named volume |
| HTTPS/SSE | `.local/phase1-tls.json` | Certificate xác minh bằng CA localhost; stream có step/answer/final |
| Monitoring | API nội bộ Prometheus và Grafana | Bốn targets UP; dashboard được provision có 6 panels |
| DB roles | pg_roles và privilege tests | Business/Chat/migrator không superuser, không createdb/createrole; Chat bị từ chối đọc identity/sửa thẻ/thi/DDL |
| PowerShell vận hành | `.local/phase1-powershell.json` | Setup lặp với `-SkipSeed`, release có drain, backup/restore sang DB mới đều exit 0 |
| Contract và kiểm tra mã | OpenAPI `--check`, `git diff --check`, kiểm tra liên kết | PASS; hợp đồng tổng hợp 59 operations, 7 stub được đánh dấu trong ma trận API |

Không cộng các nhóm test trùng nhau để tuyên bố tổng số test độc lập. File `.local`, screenshots, tokens tải và dump không được đưa vào Git.

## Tình huống phục hồi được kiểm tra

- Gửi lại qua Chat instance khác cùng key không tạo thêm turn/assistant message hoặc model call; payload khác bị từ chối.
- Một learner không đọc/hủy turn hoặc event của learner khác.
- Kill worker thật trong subprocess: trước durable invocation marker được requeue; trong fake model call bị interrupted và giữ reservation cách ly.
- Kill ngay trước commit kết quả sau khi model đã trả về: interrupted, không tự gọi lại và không có assistant message. Kill ngay sau commit trước publish answer: snapshot/SSE khôi phục đúng một answer, không gọi model lần hai.
- Mất lease/fence trong lúc model chạy: kết quả trả muộn không được commit. Worker cũ kết thúc sau một lần claim mới không được xóa processing lease của worker thay thế.
- Queue hữu hạn và deadline; FIFO/slot dùng chung được kiểm tra bằng Redis thật, không chỉ mock client.
- Hủy trong lúc model chạy giữ reservation đến khi call trả về; không công bố answer sau hủy.
- Bắt đầu thi, rút consent, xóa learner trong lúc call đang chạy không ghi/công bố answer muộn.
- Hint chờ model không giữ request connection trong pool.
- Redis mất epoch dựng lại điều phối; mất event trả 410 và snapshot DB vẫn có kết quả.
- Browser mất toàn bộ response POST sau khi backend đã commit: retry giữ cùng key, một assistant message, citation còn sau reload.

## Baseline 30/40/50 learners

Các lần đo hiện có dùng 30 giây mỗi mức, 50 token riêng cho synthetic learners; thao tác AI xác suất 10%, think time 1–3 giây, seed 42. Chỉ mô phỏng các API được harness ghi rõ; không phải toàn bộ hoạt động của một lớp học và không phải 30–50 model calls cùng lúc.

| Learners | HTTP 200 | Business p50/p95 giây | AI p50/p95 giây |
|---|---:|---:|---:|
| 30 | 336 | 0,039 / 3,250 | 0,237 / 6,414 |
| 40 | 410 | 0,039 / 4,544 | 0,294 / 6,993 |
| 50 | 448 | 0,041 / 6,876 | 0,343 / 10,178 |

Nguồn: `.local/phase1-load-30.json`, `phase1-load-40.json`, `phase1-load-50.json`. Ba lượt trên image cuối đều có `valid_authentication=true`, toàn bộ request ghi nhận HTTP 200; token được cấp mới và kiểm tra trước chạy. Máy phát triển có full regression dùng chung CPU; không có fault injection trong ba lượt đo này. Không dùng số liệu để kết luận đạt SLO, sizing GPU hoặc khả năng phục vụ dài hạn. Harness tái lập mặc định 60 giây, còn bảng trên chủ động dùng 30 giây/mức. File `.local/phase1-final-checks.json` ghi exit code và thời gian thực thi tuần tự browser → deployment → TLS → seed → ba mức tải, tất cả exit 0.

## Regression và các sửa chữa trong quá trình tích hợp

Lượt regression đầu đã dừng khi fixture migration cũ chỉ đổi version về 0011 nhưng để lại bảng mới. Fixture nay dựng lại đúng phần schema cũ trước khi upgrade, và bộ test migration/schema đã đạt. Một lượt tiếp theo tìm thấy `turn_id: null` làm thay đổi payload status Alpha; serializer Alpha đã loại trường này, 58 test luồng liên quan đã đạt. Không coi các lượt dừng hoặc trạng thái schema lỗi đó là regression đạt.

Full regression mới đã chạy đến hết: **1.122 PASS, 95 SKIP, 0 FAIL**. Đây là kết quả của lượt hoàn chỉnh, không lấy từ báo cáo Alpha lịch sử hoặc lượt bị ngắt ở 53%. Các ca SKIP không được tính là đã nghiệm thu đạt; JUnit giữ nguyên lý do skip để đối chiếu.

95 SKIP thuộc các ma trận contract có điều kiện: 48 `implemented`, 44 `no query parameters`, 3 `stream`. Không dùng số SKIP này để kết luận các chức năng ngoài phạm vi hoặc model thật đã được kiểm thử.

Các giới hạn còn lại: chưa real GPU/model protocol, chưa public DNS/ACME, chưa đánh giá y khoa, chưa SLO/RPO/RTO và chưa kiểm thử môi trường production độc lập. Mục tiêu 30–50 learner vẫn là mục tiêu lập kế hoạch; baseline scripted local không thay các cổng nghiệm thu đó.

## Nhận diện bản kiểm thử

Baseline Git `2961a2dc02609e47387404762b0b2daddf2b069b`, nhánh `feat/alpha-v1-backend`, cộng working tree Phase 1 chưa commit. `.local/phase1-source-manifest.json` lưu SHA-256 của mã backend, frontend và image Docker; `.local` chỉ là bằng chứng trên máy này, không đi theo Git.

- Backend source SHA-256: `1a466432f01964794262e650ce2c0f8853a3f6dfdca13434c35b40b61167b1e6`.
- Frontend source SHA-256: `e983db79f27409544426f3d256c7b234e053133426756435bdf9ea612292918d`.
- Scan toàn bộ file Git nhìn thấy: không có giá trị password ngẫu nhiên từ `.env.phase1`; env thật, tokens, dump và screenshots đều bị ignore.

Các lỗi tích hợp đã sửa gồm migration fixture cũ, payload status Alpha, trigger vòng đời dùng sai NEW/OLD, onboarding browser chờ thiếu bước, answer SSE bị lặp và API sai rơi xuống SPA. Phép thử failover cũng yêu cầu chờ đủ chu kỳ health check: cấu hình hiện dùng interval 5 giây, timeout 2 giây; script chờ 8 giây trước thay container. Proxy không phát lại POST.

Rà soát cuối bổ sung kiểm tra fence ngay cả khi nhả dispatch lease. Log Uvicorn và psycopg pool cũng qua formatter metadata để tránh ghi exception SQL/provider thô; log kết nối pool bình thường không được phát ở mức INFO. Fixture kill-worker chờ process sẵn sàng trước khi bắt đầu kiểm tra dispatch, tách chi phí khởi động process khỏi thời gian chờ tác vụ.

Một lượt browser chạy trùng với release đã gặp upstream unavailable và bị loại khỏi kết quả nghiệm thu. Lượt browser được giữ lại chạy tuần tự trên môi trường ổn định; không dùng retry test để che lỗi.
