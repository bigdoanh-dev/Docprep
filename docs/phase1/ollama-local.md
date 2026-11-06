# Ollama local/dev — chạy khi server tắt và kích hoạt sau

Hiện giữ generation **disabled**: AI server chưa bật. Business, lịch sử và citations đã lưu vẫn hoạt động. Yêu cầu AI trả 503 `ai_disabled`, không tạo câu trả lời thành công giả.

## Chạy hiện tại

Từ thư mục `Docprep_FE`, Docker Desktop đang chạy:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-phase1.ps1 -SkipSeed
```

Bỏ `-SkipSeed` ở lần cài mới cần tài khoản/dữ liệu minh họa. Script giữ named volume và env đã có; bootstrap role/extension vector, migration/grants rồi khởi động Business ×2, Chat ×2 và Caddy. Mở http://127.0.0.1:18880. Không dùng `down -v` để restart.

`backend/.env` riêng chỉ cấp Chat, không commit hoặc đưa vào image/frontend. Cấu hình local người dùng đã chốt:

```dotenv
YHDP_OLLAMA_URL=http://192.168.88.15:11434
YHDP_LLM_MODEL=qwen3.5:9b-q4_K_M
YHDP_EMBED_MODEL=bge-m3
YHDP_LLM_NUM_CTX=16384
YHDP_OLLAMA_TIMEOUT_SECONDS=300
```

File mẫu dùng loopback. `.env.phase1` giữ `APP_ENV=dev`, `PHASE_MODEL_PROVIDER=disabled`, active turns 1, model slots 1, max waiting 20, queue 60s, turn 360s. Đây là quota ứng dụng thử nghiệm, chưa phải năng lực GPU. Business không nhận model env.

Nếu sửa UI bằng Vite, đặt `BACKEND_URL=http://127.0.0.1:18880` trong `.env.local`, chạy `npm.cmd run dev -- --strictPort` từ `Docprep_FE`; mở 5190. Lệnh npm không khởi động backend.

## Chỉ kích hoạt sau khi server bật

Xác nhận mạng/firewall/quyền dùng model và hai model đã có sẵn. Không tự pull model, bật fallback hoặc mở cổng Ollama ra Internet. Đổi `PHASE_MODEL_PROVIDER=ollama` trong `.env.phase1`; giữ `postcheck.tier2_enabled: false` trong `backend/config.yaml` vì examiner chưa chốt.

```powershell
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml up -d --no-deps --force-recreate --wait chat-1 chat-2
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml exec -T chat-1 python -m app.phase_cli check-models
```

Phải **tạo lại**, restart không nạp env mới. Readiness yêu cầu `/api/tags` có đúng tên và digest cả hai model. Nếu không ready, quay provider về disabled và tạo lại Chat; không bỏ readiness. `check-models` chỉ đọc metadata, chưa chứng minh generation/embedding.

Adapter chấp nhận tên không ghi tag (`bge-m3`) tương ứng `bge-m3:latest`, không chọn model khác. Digest được đọc mới trước mỗi model call; cache 5 giây chỉ dùng cho metadata readiness. Không thay tag/model trong lúc nghiệm thu; metadata không phải cơ chế pin weights nguyên tử phía server. Giao thức đối chiếu với [Ollama chat](https://docs.ollama.com/api/chat), [embed](https://docs.ollama.com/api/embed), [tags](https://docs.ollama.com/api/tags) và [quy tắc tên model](https://github.com/ollama/ollama/blob/main/types/model/name.go). Embedding đặt truncate=false để không âm thầm cắt nguồn dài; không tự suy đoán context/dimension của embedding model.

Lập index bằng job PostgreSQL/outbox, được worker Chat lấy qua cùng Redis FIFO và shared reservation `ollama:shared`:

```powershell
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml exec -T chat-1 python -m app.phase_cli index
# Thay <turn_id> bằng UUID vừa in:
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml exec -T chat-1 python -m app.phase_cli job <turn_id>
```

CLI không gọi embedding trực tiếp. Worker xử lý lô tối đa 32 passage, nhả DB connection trước model I/O. Job chỉ đọc corpus nonsynthetic hiện có, chưa nhập corpus YHDP thật. Mỗi model chỉ có một index job đang mở. Deadline job 360s: corpus lớn có thể cần enqueue tiếp sau job trước kết thúc; vector đã commit đúng hash/digest được dùng lại, không replay call chưa rõ kết quả.

Sau `completed`, thử chat có nguồn, citation và reload; thử hint trước đáp án, explain sau đáp án. Đối chiếu model/digest/corpus, token/latency khi provider trả. Chi phí chưa biết lưu null. Đây mới là mốc xác minh AI thật.

Đổi passage text/context xóa vector dẫn xuất; thêm passage hoặc đổi model digest/corpus version cũng cần index lại. Query từ chối index thiếu/sai hash/dimension/version với lỗi kỹ thuật `retrieval_index_not_ready`. Tìm kiếm exact pgvector + PostgreSQL FTS, hợp nhất RRF; chưa có ANN tuning/reranker/examiner hoặc đánh giá chất lượng chuyên môn.

## Timeout và cách ly model call

Hết deadline/đóng socket sau dispatch không chứng minh GPU đã dừng. Turn `interrupted`; reservation được giữ cách ly trong PG/Redis, kể cả Redis restart. Quota 1 có thể khiến lượt sau chờ hoặc timeout; không tăng quota để vượt reservation.

Operator phải xác nhận lời gọi phía model đã dừng trước khi nhả:

```powershell
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml exec -T chat-1 python -m app.phase_cli release-model-call <call_id> --confirm-stopped
```

`call_id` lấy từ `ai_model_call` bằng tài khoản vận hành, không phải turn_id. Không có endpoint public nhả slot. Chưa xác nhận được thì giữ cách ly và tắt admission generation; không gửi lại request.

## Kiểm thử không cần AI server

```powershell
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml run --rm --no-deps test
$env:PHASE1_URL='http://127.0.0.1:18880'
npm.cmd run test:e2e -- e2e/offline.spec.ts
# Acceptance scripted local, tạm tạo lại Chat rồi khôi phục provider trong finally:
powershell -ExecutionPolicy Bypass -File scripts/test-phase1.ps1 -ScriptedAcceptance
```

Chỉ chạy fault/backup/release test khi không có người demo. Dùng `phase1_test` và `alphav1_test` riêng; fixture dựng schema không được trỏ vào database demo. Test scripted/fake không chứng minh model thật, chất lượng AI hoặc tải 30–50 learners.
