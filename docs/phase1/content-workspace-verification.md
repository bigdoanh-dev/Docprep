# Kiểm chứng kho tài liệu YHDP — 16/11/2026

## Đồng bộ nhánh Git ngày 17/11/2026

Đã ghép 5 commit từ `origin/feat/alpha-v1-backend`, từ nền `29708ae` đến `fcbd6f7`, với phần content local. Giữ các sửa lỗi upstream về đăng nhập/màn trắng/SSE, chống trùng phiên và tin nhắn, exam guard, sáu mức Bloom và dữ liệu Bloom cũ.

- Giải quyết trùng revision: `0017_six_level_bloom.py` giữ theo upstream, corpus chuyển sang `0018_corpus_releases.py`. Migration `0018` hỗ trợ cả DB upstream 0017 và DB corpus local 0017 cũ; có hai ca regression riêng. Runtime đang dùng đã nâng lên **0018**, content schema vẫn **0003**.
- Backup runtime trước nâng cấp: `/backups/manual-20261116T165509Z.dump`. Dùng `setup-phase1.ps1 -SkipSeed`, không reset DB; content vẫn **477 classified + approved**, giữ policy tạm và lịch sử.
- Sửa cấu hình container test để mount `openapi.yaml` từ checkout, tránh kiểm tra source mới với contract cũ trong image. Cập nhật browser test theo đúng sáu mức Bloom hiện hành.
- Unit frontend: **124 passed**. Build learner, build content, lint và OpenAPI drift check đạt.
- Phase 1: **56 passed / 154,97 giây**. Content: **17 passed / 105,17 giây**, trên DB test riêng.
- Regression toàn bộ thư mục backend `tests`: **1.171 passed, 97 skipped / 1.127,38 giây**, không có failure/error; gồm các sửa lỗi upstream và hai đường nâng cấp migration. Lượt đầu dùng OpenAPI cũ trong image đã được dừng và thay bằng lượt chạy sạch sau khi sửa mount; con số này chỉ thuộc lượt chạy sạch đó. JUnit nằm trong `.local/sync-alpha-tests.xml` (không commit).
- Browser qua Caddy runtime: **6 passed / 29 giây**, gồm learner học → ôn → thi → tiến độ → chat disabled và dashboard staff, ở desktop/mobile. Browser reviewer dùng API QA riêng: **2 passed / 7,7 giây**.
- Log mới lưu local tại `%TEMP%/docprep-sync-*.log`; artifact browser ở `%TEMP%/docprep-sync-browser-accepted/` và `%TEMP%/docprep-sync-content-browser/`. Provider vẫn disabled; không có nghiệm thu model thật hoặc tải GPU.

Các phần tiếp theo ghi lại mốc kiểm chứng content ban đầu ngày 16/11, trước lần đồng bộ này.

> **Cập nhật sau yêu cầu chấp nhận tạm data.zip:** workspace hiện có **477 classified + approved**, 954 quyết định `source-baseline-v1`; chưa thẩm định chuyên môn. Các số 0 quyết định/0 classified trong baseline ban đầu bên dưới là trạng thái trước thay đổi này. Không chuyển corpus runtime. Chi tiết chính sách và cách rà soát lại nằm trong [runbook](content-workspace.md#chấp-nhận-tạm-dữ-liệu-nguồn-khi-chưa-có-chuyên-gia).

Kiểm tra cho cập nhật này: content suite **17 passed / 90,38 giây**; sau điều chỉnh đọc lịch sử dưới khóa, nhóm baseline/API **4 passed, 13 deselected / 44,58 giây**. Build reviewer và lint đạt. Browser thật qua Caddy 18882 ở 1440×1000 và 390×844: 477/477, policy tạm hiển thị đúng, lọc classified → xem chi tiết/hai quyết định → reload giữ trạng thái; không lỗi console/JavaScript hoặc tràn ngang. Dùng Playwright vì Browser plugin không có trong phiên. Ảnh lưu ngoài repo tại `%TEMP%/content-baseline-desktop.png` và `%TEMP%/content-baseline-mobile.png`. Log `%TEMP%/docprep-content-baseline-tests.log`, `%TEMP%/docprep-content-baseline-recheck.log`.

Backup trước cập nhật: `backups/content/20261116162350`. Digest nội dung sau cập nhật vẫn là `0ca89eb3d25954166abe6b8cb997b1b8`; một audit `source_baseline_accepted`. Không có migration mới cho chính sách; dùng trường `policy_version` đã có. Quyết định cũ giữ nguyên và sau này có thể được thay thế bằng quyết định hiện hành mới.

## Phạm vi và phiên bản

Kết quả ban đầu dưới đây được chạy trên Windows, Docker Linux Engine, Python 3.13, PostgreSQL 16 và Chromium. Tại mốc đó code nằm trong working tree nhánh `feat/alpha-v1-backend`, nền `29708ae`, chưa commit/push. Trạng thái đồng bộ mới hơn được ghi ở đầu tài liệu. Đây không phải kết quả của báo cáo Alpha trước đây.

Ở mốc ban đầu runtime dùng migration corpus local `0017`; khi đồng bộ Git đã chuyển sang `0018` như phần cập nhật trên. Database content dùng chuỗi migration SQL riêng đến `0003`. Frontend reviewer là build từ `src/content`, cùng API thực `app.main_content`. Provider runtime vẫn **disabled**; không có kiểm chứng model thật, chữ ký thật hoặc tải GPU.

## Kết quả chạy mới

| Nhóm | Kết quả | Phạm vi thực sự đã kiểm tra |
|---|---|---|
| Content/PostgreSQL | **14 passed**, 51,31 giây | Import 477 chunk, chạy lặp, hash/tag lệch, SQLite ưu tiên hơn JSONL, nhập một tài liệu rồi cả gói, hai quyết định, stale/idempotency, quyền, token, giới hạn login, asset, immutable data và OpenAPI bearer/error envelope. |
| Phase 1 | **56 passed**, 121,18 giây | Toàn bộ `tests_phase1`, bao gồm 4 ca mới về publication, candidate visibility, pin/rollback/revoke, trust, privacy prompt và quyền miền dữ liệu. |
| Backend regression Alpha | **186 passed**, 441,82 giây | Migration/schema, retrieval, password login, cards, exams, rhythm/skills, daily session, practice, chat/quiz, dashboard overview/export. Đây là nhóm được chọn, không phải toàn bộ thư mục `tests`. |
| Frontend unit | **124 passed** | Bộ test frontend hiện tại qua `npm.cmd test`. |
| Build/lint | **Đạt** | Build reviewer, TypeScript, ESLint; `git diff --check` không có lỗi whitespace. |
| Browser reviewer | **2 passed**, 8,2 giây | Desktop 1440×1000 và mobile 390×844: login → xem nguồn → sửa nhãn → xác nhận phân loại → duyệt nội dung → export → reload lịch sử → logout. |
| Browser workspace đang dùng | **Đạt**, cả hai viewport | Đăng nhập thật qua Caddy 18882, danh sách 477/0, mở chunk, không tràn ngang/lỗi JavaScript; API sai trả JSON 404. Chỉ đọc nội dung, không duyệt dữ liệu thật. |
| Transfer bằng CLI | **Đạt** | Manifest browser → role `phase_publisher` → verify-only rollback → candidate → chạy lặp reused → activate; một passage tồn tại trong `phase1_test`. |
| Backup/restore content | **Đạt** | Restore sang DB/volume mới; đủ chunk/asset, hash khớp; không ghi đè workspace. |

Lần chạy Phase 1 trước đó có lỗi teardown do test để lại `APP_ENV=production`; test đã được sửa để giới hạn monkeypatch trong context. Con số **56 passed** phía trên thuộc lần chạy lại sạch, sau khi sửa. Không cộng các lần chạy lại thành số ca mới.

## Dữ liệu và môi trường cách ly

**Workspace đang dùng:** project Compose `docprep-content`, DB `content_workspace`, 3 tài liệu, **477 chunk, 0 quyết định human**; chưa chunk nào classified/approved. Có 26 asset metadata và 26 file asset theo hash. Import không lấy users, JWT secret hoặc log model từ ZIP.

Snapshot nguồn có 171 tag `auto` và 306 tag `review`. Các nhãn này là đề xuất, không trở thành xác nhận human. Hai tag không khớp chunk/hash được ghi trong báo cáo nhập. SQLite chỉ có chunk của 3 tài liệu; không tạo chunk giả cho hai mục registry còn lại. Không có file nguồn DOCX/PDF gốc nên revision ghi `derived_only`.

**Content API tests:** chỉ dựng lại schema `content_workspace_test`, dùng thư mục asset tạm. **Browser QA:** cũng dùng DB này nhưng được chuẩn bị riêng sau khi unit tests kết thúc, import 180 chunk của `qd2760`; user `reviewer.e2e`, mapping `AUTOMATED-QA-ONLY`. Đây là mapping kỹ thuật tổng hợp để kiểm tra đường dữ liệu, **không phải mapping/duyệt chuyên môn**.

Browser dùng build Caddy thật tại 18882; Playwright chuyển các request API sang API QA thật tại 18884, không tạo phản hồi thành công giả. API 18884 chỉ bind loopback và đã dừng sau kiểm tra. Vì vậy kết quả này kiểm chứng giao diện + API + DB QA; không phải một lần human duyệt dữ liệu thật trong workspace.

**Runtime tests:** `phase1_test` và `alpha_content_test`, tách khỏi runtime `phase1`. Sau kiểm tra, runtime `phase1` vẫn có **0 managed release, 0 activation**; corpus demo đang dùng không bị chuyển sang nguồn QA. Tài khoản, điểm và lịch học đang dùng không bị reset.

## Backup và phục hồi đã thực hiện

Backup content: `backups/content/20261116160047/`, gồm PostgreSQL custom dump, immutable asset archive và manifest SHA-256. Restore tạo:

- Database `content_restore_20261116160100`.
- Volume `docprep_content_restore_assets_20261116160100`.
- Schema content version 3, 477 chunk, 26 asset metadata.
- Digest tổng hợp các `content_sha256`, sắp theo chunk ID: `0ca89eb3d25954166abe6b8cb997b1b8`, khớp DB nguồn.
- 26/26 file phục hồi có SHA-256 bằng tên file.

Đã sửa backup để stream tar binary trực tiếp ra host vì Docker cp không đọc được file trong tmpfs `/tmp` của API. Lần backup/restore thành công phía trên sử dụng bản đã sửa. Script kiểm tra SHA-256 của hai artifact trước restore và từ chối entry asset ngoài định dạng hash.

Trước migration runtime đã tạo thêm PostgreSQL backup `/backups/manual-20261116T153859Z.dump` trong volume backup Phase 1. **Lần kiểm tra này không restore runtime dump đó**; kết quả restore phía trên là kho content mới.

## Chạy lại

Làm theo [runbook](content-workspace.md) để setup, cấp account và nhập nguồn. DB test phải được tạo riêng trước lần chạy đầu:

```powershell
docker compose --env-file .env.content -f deploy/compose.content.yml run --rm content-test
docker compose --env-file .env.phase1 -f deploy/compose.phase1.yml run --rm test
npm.cmd test
npm.cmd run build:content
npm.cmd run lint
```

Browser case: [e2e/content-workspace.spec.ts](../../e2e/content-workspace.spec.ts); fixture reset có chốt `APP_ENV=test`, `CONTENT_QA_RESET=1` và tên DB chính xác trong [prepare_browser.py](../../backend/tests_content/prepare_browser.py). Chạy browser sau content unit tests, không đồng thời trên cùng DB. Xem hướng dẫn cấu hình QA trong runbook. Không sử dụng fixture mapping hoặc manifest QA để phát hành nội dung thật.

Evidence local, không chứa credential trong báo cáo này:

- `%TEMP%/docprep-content-tests-final.log`
- `%TEMP%/docprep-content-phase1-clean.log`
- `%TEMP%/docprep-content-alpha-regression.log`
- `%TEMP%/docprep-content-frontend-tests.log`
- `%TEMP%/docprep-content-browser.log`
- `%TEMP%/docprep-content-cli-publication.log`
- `%TEMP%/docprep-content-ui-20261116/` — screenshot và manifest browser QA.

## Giới hạn còn lại

1. Cần Lead xác nhận mapping chuyên môn, chất lượng nguồn và bản gốc; không tự duyệt 477 chunk.
2. Release hiện tại chỉ là unsigned `local_dev`. `SignatureVerifier` từ chối mặc định; chưa có thuật toán/khóa/protocol được duyệt. Ngoài dev/test bị chặn; Ollama không được sinh nội dung trên release local chưa verified.
3. Publication chuyển text, location, nhãn, approval và source hash sang passage runtime. Asset được duyệt/xem trong kho content; chưa có giao thức phát hành binary asset hoặc DOCX/PDF gốc sang runtime learner.
4. Chưa có OCR/parser DOCX mới, auto-classifier mới, nhập ngân hàng câu hỏi, lịch duyệt tự động hoặc garbage collector asset. Content authentication phục vụ triển khai nội bộ local hiện tại.
5. Không suy ra chất lượng AI, năng lực 30–50 learners, SLO, staging HTTPS hay nghiệm thu Phase 1 đầy đủ từ các kết quả này.
