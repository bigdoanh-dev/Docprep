# Kho biên soạn tài liệu YHDP

Ngày cập nhật: **18/11/2026**. Đây là luồng **local/dev**: nhập dữ liệu YHDP đã xử lý → sửa nhãn → reviewer xác nhận phân loại và nội dung → xuất gói → publisher nhập candidate → activate. Không có OCR, auto-tagger mới hoặc xác minh model thật trong đợt này.

## Kiến trúc và dữ liệu

- Content API: `app.main_content:app`, database `content_workspace` riêng, schema migration riêng trong `backend/content_migrations`. Không import router learner, không dùng token learner, không kết nối DB runtime.
- Giao diện React riêng, build bằng `npm.cmd run build:content`; Caddy content phục vụ tại **http://127.0.0.1:18882**. Không xuất giao diện reviewer qua Caddy learner.
- Tài khoản content có các quyền `editor`, `reviewer`, `publisher`. Một người có thể có nhiều quyền. Tạo/reset bằng CLI operator; không nhập users hoặc JWT secret từ ZIP.
- Publisher CLI dùng role DB `phase_publisher`, chỉ đọc taxonomy và ghi nguồn/release cần thiết trong runtime. Không đọc identity hoặc ghi điểm/thẻ/thi.
- [ERD kho tài liệu](content-workspace-erd.mmd); [schema nguồn và workflow](../../backend/content_migrations/0001.sql), [ràng buộc quyết định](../../backend/content_migrations/0002.sql), [quyền duyệt mapping](../../backend/content_migrations/0003.sql).
- Runtime dùng migration [0018](../../backend/migrations/versions/0018_corpus_releases.py) sau `0017` Bloom từ nhánh Git; giữ nguyên dữ liệu cũ. Bản local trước đồng bộ từng dùng mã `0017` cho corpus; migration `0018` nhận diện schema này, bổ sung metadata Bloom còn thiếu và giữ dữ liệu nguồn đã có.

### Bloom trần của tài liệu

Danh mục hỗ trợ đủ sáu mức theo thứ tự: **Nhớ, Hiểu, Áp dụng, Phân tích, Đánh giá, Sáng tạo**. Mức Sáng tạo có thể chưa có chunk sử dụng nhưng luôn có trong danh mục để biên soạn. `GET /v1/taxonomies` cung cấp danh sách cho form; schema API và kiểm tra nhãn dùng cùng định nghĩa.

Migration content [0004](../../backend/content_migrations/0004.sql) mở rộng ràng buộc database, giữ nguyên toàn bộ nhãn và lịch sử đã lưu. Không tự đổi chunk cũ sang mức 6. Đây là `chunk_tag_set.bloom_ceiling`, độc lập với `question.bloom_level_6` dùng cho thống kê năng lực; sửa nhãn tài liệu không tự gán mức cho câu hỏi.

Kiểm chứng 18/11/2026: 19 test content trên PostgreSQL test đạt; browser QA desktop 1440×1000 và mobile 390×844 đạt luồng chọn Sáng tạo → lưu → xác nhận → xuất manifest → reload. Không có lỗi console/pageerror hoặc tràn ngang trong luồng này. Dùng Playwright vì phiên làm việc không có Browser plugin; API/DB QA tách riêng, không đổi nhãn tài liệu thật. Local content schema đã lên 0004, 477 nhãn nguồn giữ nguyên. Build frontend content đạt; image backend local được cập nhật trên image dependency sẵn có vì Docker Hub gặp lỗi DNS, chưa kiểm chứng build image từ môi trường sạch trong lần này.

### Hai nhóm chunk

| Nhóm | Điều kiện |
|---|---|
| `unclassified` | Chưa có nhãn hoặc nhãn mới là đề xuất; chưa có quyết định xác nhận cho phiên bản hiện tại. |
| `classified` | Bộ nhãn hợp lệ được reviewer xác nhận hoặc chấp nhận tạm theo chính sách nguồn bên dưới: một primary, tối đa hai secondary, 1–2 miền và các trường form hợp lệ. |

`content_status` độc lập: `pending`, `approved`, `needs_revision`, `rejected`. Một chunk classified chưa chắc đã được duyệt nội dung. Chỉ export khi có cả hai quyết định accept và mapping đã được reviewer xác nhận.

Snapshot nguồn có **477 chunk**, 171 tag `auto`, 306 tag `review`; cả 477 được nhập ở trạng thái chưa xác nhận. Hai tag không khớp chunk/hash được giữ trong báo cáo nhập, không gán nhầm vào phiên bản hiện tại. Registry có 5 nguồn, nhưng snapshot SQLite chỉ có chunk của 3 tài liệu.

### Chấp nhận tạm dữ liệu nguồn khi chưa có chuyên gia

Theo yêu cầu người phụ trách ngày 16/11, dùng `data.zip` làm baseline đúng tạm thời cho phát triển. Chính sách **`source-baseline-v1`** ghi hai quyết định accept (phân loại/nội dung) theo tài khoản content thực hiện, kèm hash ZIP và lý do. Đây là chấp nhận dữ liệu nguồn theo yêu cầu dự án, chưa phải kết quả thẩm định chuyên môn. UI hiển thị rõ dấu chấp nhận tạm. Nhãn gốc, text, cờ chất lượng và lịch sử được giữ nguyên.

Đã áp dụng trên workspace local: **477/477 classified + approved**, 954 quyết định `source-baseline-v1`, một audit cho thao tác chấp nhận gói. Backup trước thay đổi: `backups/content/20261116162350`. Nội dung chunk không bị sửa; digest tổng hợp vẫn khớp bản trước chấp nhận. Runtime demo chưa có release/activation mới từ thao tác này.

Lệnh operator chỉ cho phép dev/test, mặc định preview, cần `--apply` mới ghi. Nó chỉ áp dụng revision hiện tại khớp đúng gói đã import, kiểm tra nội dung/nhãn với nguồn, không tự điền nhãn thiếu, không ghi đè chunk đã có quyết định. Toàn bộ apply là một transaction; chạy lặp cùng gói/lý do không nhân đôi quyết định. Ví dụ với tài khoản reviewer:

```powershell
docker compose --env-file .env.content -f deploy/compose.content.yml run --rm -it content-operator accept-baseline /exports/input/data.zip --reason "User accepted data.zip as temporary development baseline; expert review deferred."
docker compose --env-file .env.content -f deploy/compose.content.yml run --rm -it content-operator accept-baseline /exports/input/data.zip --reason "User accepted data.zip as temporary development baseline; expert review deferred." --apply
```

Sau này dùng **Cần sửa nhãn / Cần sửa nội dung / Từ chối nội dung**, sửa form và xác nhận lại để thay quyết định hiện hành; quyết định cũ không bị xóa. Nếu cần sửa text, cập nhật bộ dữ liệu nguồn và nhập revision mới. Chính sách hiệu lực từng mục được API trả qua `classification_policy` và `content_policy`; manifest giữ đúng policy hoặc `mixed-v1` khi trộn các loại quyết định.

Chấp nhận baseline không tự duyệt mapping sang runtime, không ký corpus, không activate release và không bật AI. Các bước kỹ thuật đó tiếp tục thực hiện riêng; không dùng mapping QA để công bố nội dung thật.

SQLite là nguồn chuẩn. JSONL lệch được báo cáo, không ghi đè text/loc SQLite. File gốc DOCX/PDF không có trong ZIP được ghi `derived_only`, không giả là đã đủ nguồn. Asset được lưu theo SHA-256 trong volume riêng; source ZIP, secret và log model không được đưa vào asset phục vụ web.

## 1. Khởi động

Mở Docker Desktop, chạy từ thư mục `Docprep_FE`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/setup-content.ps1
```

Setup tạo `.env.content` với mật khẩu DB ngẫu nhiên nếu chưa có; build và migrate kho content. Mở **http://127.0.0.1:18882**. Chỉ web được bind vào loopback; DB và API không có host port trong cấu hình thường.

Không tạo tài khoản mặc định trong seed. Cấp tài khoản nội bộ, nhập mật khẩu hai lần:

```powershell
docker compose --env-file .env.content -f deploy/compose.content.yml run --rm -it content-operator create-user --username content.local --name "Content local" --roles editor reviewer publisher
```

Tài khoản local đã tạo trong lần triển khai trên máy này là `content.local`; mật khẩu ngẫu nhiên nằm trong **`.local/content/operator.local.json`**. File này bị Git bỏ qua, không đưa vào slide hoặc commit. Cài mới dùng lệnh cấp tài khoản trên, không trông chờ file local có sẵn.

Đặt lại mật khẩu và thu hồi token hiện có:

```powershell
docker compose --env-file .env.content -f deploy/compose.content.yml run --rm -it content-operator reset-password --username content.local
```

Tài khoản, mật khẩu, token và log chưa được duyệt không được copy từ DB YHDP nguồn. Không dùng credentials learner để đăng nhập kho content.

## 2. Nhập dữ liệu

Chuẩn bị file ở thư mục riêng đã được Git bỏ qua:

```powershell
New-Item -ItemType Directory -Path .local/content/input -Force
Copy-Item -LiteralPath D:\InternAIRC\AI_TuTor\data.zip -Destination .local/content/input/data.zip
```

Preview chỉ đọc, không cần đăng nhập hoặc ghi DB:

```powershell
docker compose --env-file .env.content -f deploy/compose.content.yml run --rm content-operator preview /exports/input/data.zip
```

Import có xác thực tài khoản content, hỏi username/mật khẩu:

```powershell
docker compose --env-file .env.content -f deploy/compose.content.yml run --rm -it content-operator import /exports/input/data.zip --document qd2760
docker compose --env-file .env.content -f deploy/compose.content.yml run --rm -it content-operator import /exports/input/data.zip
```

Importer giới hạn 128 MiB gói nén, 1 GiB tổng giải nén, từ chối path traversal và entry trùng. Mỗi lần apply dùng một transaction: lỗi thì rollback, chạy lại an toàn. File content-addressed đã ghi trước rollback có thể còn trên volume nhưng không được phục vụ nếu không có metadata asset. Chưa có garbage collector; không xóa thủ công asset còn được backup/revision tham chiếu.

Khóa nhập lặp bao gồm namespace, SHA-256 gói, phiên bản importer/mapping và lựa chọn tài liệu. Nhập trước một tài liệu rồi nhập toàn bộ không tạo trùng revision hoặc chunk đã có. Import không ghi đè quyết định human.

## 3. Duyệt và mapping

Trên giao diện:

1. Chọn tài liệu và một trong hai nhóm phân loại.
2. Mở chunk để xem text, mục/trang, cờ chất lượng và asset. Markdown được hiển thị không chạy HTML từ tài liệu.
3. Editor sửa form: taxonomy, vấn đề chính/phụ, miền, Bloom, content type, population và lý do.
4. Lưu đề xuất tạo tag set mới và đưa trạng thái về unclassified; không sửa lịch sử cũ.
5. Reviewer ghi nhận xét rồi **Xác nhận phân loại**; thao tác này không tự duyệt nội dung.
6. Reviewer ghi nhận xét nguồn/chất lượng rồi **Duyệt nội dung**, hoặc yêu cầu sửa/từ chối. Nguồn dẫn xuất và lỗi bảng/hình cần được kiểm tra trong nhận xét; approval local không trở thành bằng chứng chuyên môn cho production.

Mỗi lần ghi kiểm tra `row_version` và Idempotency-Key. Bản cũ trả 409, cần tải lại; không được tự ghi đè quyết định mới. SQL bảo vệ cùng chunk/task/purpose và reviewer có quyền. Quyết định và audit append-only.

### Mapping không tự suy ra từ thứ tự hoặc tên

Runtime phải được setup/migrate trước khi dùng publisher:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/setup-phase1.ps1 -SkipSeed
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml run --rm publisher mapping-template --output /exports/mapping.template.json
```

Template chưa được duyệt. Đối chiếu với chuyên môn và điền mapping có version, ví dụ cấu trúc:

```json
{
  "version": "mapping-da-duoc-chot-v1",
  "approved": true,
  "issues": {
    "MA_NGUON": { "runtime_issue_id": 0, "competency_code": "MA_DICH" }
  },
  "domains": { "MA_MIEN_NGUON": 0 }
}
```

Các giá trị trong ví dụ là **placeholder**, không dùng trực tiếp. Lưu bản đã đối chiếu vào `.local/content/mapping.approved.json`; tài khoản reviewer xác nhận snapshot:

```powershell
docker compose --env-file .env.content -f deploy/compose.content.yml run --rm -it content-operator taxonomy --mapping /exports/mapping.approved.json
```

Chọn taxonomy mới trên form chunk, lưu và xác nhận lại nhãn. Snapshot cũ không bị sửa. Khi import lần đầu đã có mapping được duyệt, có thể thêm `--mapping /exports/mapping.approved.json`; tài khoản phải có cả editor và reviewer. Người chỉ có editor không được xác nhận mapping.

Không dùng fixture `mapping.test.json` của kiểm thử để công bố nguồn thật. Bloom trần của chunk không được ép thành Bloom 1–3 của bảng question; đợt này không chuyển ngân hàng câu hỏi.

## 4. Export, publish, activate và rollback

Publisher chọn các chunk đủ điều kiện trên giao diện, nhập version và **Xuất manifest**. Giao diện tải file JSON xuống máy; chuyển file đó vào `.local/content/`. Hoặc xuất bằng CLI:

```powershell
docker compose --env-file .env.content -f deploy/compose.content.yml run --rm -it content-operator export --version yhdp-dev-v1 --chunks UUID_CHUNK_DA_DUYET --output /exports/yhdp-dev-v1.json
```

Kiểm tra và nhập candidate bằng role publisher, không dùng owner:

```powershell
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml run --rm publisher publish /exports/yhdp-dev-v1.json --verify-only
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml run --rm publisher publish /exports/yhdp-dev-v1.json
```

`--verify-only` chạy kiểm tra trong transaction rồi rollback; không để candidate tồn tại. Publish thật vẫn chưa đổi nguồn đang phục vụ. Cùng version khác manifest bị từ chối; chạy lặp cùng gói gắn lại release đã có.

Kích hoạt có chủ đích:

```powershell
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml run --rm publisher activate --version yhdp-dev-v1 --reason "Nghiem thu local"
```

Không kích hoạt gói thử trên môi trường đang có người demo. Bản triển khai ban đầu giữ corpus demo runtime, không tự publish/activate 477 chunk.

Rollback bằng `activate` version trước đã kiểm tra. Thu hồi release:

```powershell
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml run --rm publisher revoke --version yhdp-dev-v1 --reason "Can kiem tra lai nguon"
```

Thu hồi active release làm đường sinh nội dung fail closed; không âm thầm quay sang nguồn khác. Release bị thu hồi không thể activate lại bằng công cụ này. Passage đã công bố không bị ghi đè/xóa. Citation lịch sử của release ready có thể mở theo quyền; nguồn revoked không được mở lại qua passage API.

### Giới hạn tin cậy và model

Tất cả release do công cụ hiện tại tạo đều có `trust=local_dev`, chưa có chữ ký. Chỉ dùng khi `APP_ENV=dev/test`. Interface `SignatureVerifier` từ chối mặc định; chưa có adapter thuật toán/khóa thật được Lead duyệt. Ngoài dev/test, publisher từ chối thao tác. Gateway Ollama cũng từ chối generation trên release local chưa xác minh.

Index job hỗ trợ version nguồn cụ thể, vẫn đi qua outbox/Redis/gateway chung. Không dùng BLOB vector SQLite làm index runtime. `PHASE_MODEL_PROVIDER=disabled` được giữ nguyên; đọc nguồn đã activate có thể kiểm tra local, còn gọi model thật và index với nguồn verified là cổng sau.

## 5. Contract và các điểm bảo vệ runtime

- [OpenAPI Content](../../openapi.content.yaml) độc lập; API learner không đổi đường dẫn hoặc schema.
- Content API gồm auth/me, documents/revisions, taxonomies, chunks, tags, decisions, assets và export release.
- Chuẩn lỗi `{error:{code,message_vi}}`. Phiên bản cũ và idempotency conflict trả 409; thiếu quyền trả 403.
- FTS, dense search, corpus/index, hint/explain và direct citation cùng kiểm tra release visibility. Candidate không được phục vụ chỉ vì `is_synthetic=false`.
- Turn lưu corpus version server chọn khi admission; worker dùng context riêng, không sửa config global. Kiểm tra lại thu hồi trước model và trước commit; lock publication ngăn revoke chạy chen giữa kiểm tra cuối và commit.
- Nội dung legacy không bị tự chuyển thành nguồn chuyên môn đã duyệt. Khi chưa chọn release mới, luồng demo cũ được giữ để regression.
- Business không được ghi nguồn/release; Chat chỉ đọc và ghi index dẫn xuất theo quyền; publisher không có quyền learner. DB content ở mạng/instance riêng trong Compose local.

## 6. Kiểm thử và backup

DB test là `content_workspace_test`; runtime regression dùng DB khác runtime. Bộ test chủ động dựng lại schema, không chạy trên DB đang demo.

```powershell
docker compose --env-file .env.content -f deploy/compose.content.yml exec -T content-db createdb -U content_owner content_workspace_test
docker compose --env-file .env.content -f deploy/compose.content.yml run --rm content-test
```

Lệnh createdb chỉ dùng lần đầu; nếu DB đã có thì không tạo lại. Browser test `e2e/content-workspace.spec.ts` chỉ chạy khi có `CONTENT_E2E_URL`, `CONTENT_QA_API_URL`, `CONTENT_E2E_PASSWORD`. QA dùng API/DB riêng, không xác nhận tự động tài liệu thật trong workspace.

### Browser QA trên DB riêng

Chuẩn bị `data.zip` như mục 2. Runtime Phase 1 cần sẵn sàng để xuất danh mục tham chiếu. Các lệnh sau tạo **mapping giả lập chỉ cho test**, ghép domain theo thứ tự để đi qua ràng buộc kỹ thuật, không mang ý nghĩa chuyên môn. File chỉ được nạp vào `content_workspace_test`; tuyệt đối không dùng cho workspace thật hoặc phát hành nguồn thật.

```powershell
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml run --rm publisher mapping-template --output /exports/mapping.reference.json
backend/.venv/Scripts/python.exe backend/tests_content/make_mapping.py
$env:CONTENT_E2E_PASSWORD=[Net.NetworkCredential]::new('',(Read-Host 'Mat khau QA rieng, it nhat 12 ky tu' -AsSecureString)).Password
$env:CONTENT_QA_RESET='1'
$env:CONTENT_TEST_MAPPING='/exports/mapping.test.json'
docker compose --env-file .env.content -f deploy/compose.content.yml run --rm -e CONTENT_E2E_PASSWORD -e CONTENT_QA_RESET -e CONTENT_TEST_MAPPING content-test python -m tests_content.prepare_browser
```

Lệnh prepare **xóa và tạo lại schema DB test**, không chạy đồng thời content unit tests. Nó từ chối môi trường khác `test`, tên DB khác `content_workspace_test` hoặc mapping version khác `AUTOMATED-QA-ONLY`. Tạo API QA tạm bằng cùng backend code:

```powershell
docker compose --env-file .env.content -f deploy/compose.content.yml run --rm --no-deps -d --name docprep-content-browser-qa -p 127.0.0.1:18884:8000 content-test uvicorn app.main_content:app --host 0.0.0.0 --port 8000 --no-access-log
$env:CONTENT_E2E_URL='http://127.0.0.1:18882'
$env:CONTENT_QA_API_URL='http://127.0.0.1:18884'
$env:PHASE1_URL=$env:CONTENT_E2E_URL
npx.cmd playwright test e2e/content-workspace.spec.ts
docker stop docprep-content-browser-qa
Remove-Item Env:CONTENT_E2E_PASSWORD,Env:CONTENT_QA_RESET,Env:CONTENT_TEST_MAPPING,Env:CONTENT_E2E_URL,Env:CONTENT_QA_API_URL,Env:PHASE1_URL -ErrorAction SilentlyContinue
```

Luôn dừng API QA sau khi kiểm tra, kể cả test lỗi; không mở port 18884 ra mạng. Lặp lại lần test cần prepare lại vì thao tác reviewer đã thay đổi fixture. Playwright dùng API QA thật qua `route.fetch`; không giả response thành công. Chromium phải được cài trước bằng `npm.cmd exec playwright -- install chromium`.

Backup cả DB và immutable assets:

```powershell
backend/.venv/Scripts/python.exe scripts/backup-content.py backup
backend/.venv/Scripts/python.exe scripts/backup-content.py restore backups/content/TIMESTAMP
```

Restore tạo DB `content_restore_*` và volume asset mới; không ghi đè workspace đang chạy. Công cụ không tự đổi URL/volume ứng dụng sang bản restore. Đối soát count/hash trước khi quyết định chuyển môi trường. Dừng bằng `docker compose --env-file .env.content -f deploy/compose.content.yml stop`; không thêm `-v` nếu cần giữ dữ liệu.

Kết quả kiểm chứng của lần triển khai được ghi riêng trong [báo cáo kiểm thử](content-workspace-verification.md); không coi hướng dẫn chạy là bằng chứng các ca đã đạt.
