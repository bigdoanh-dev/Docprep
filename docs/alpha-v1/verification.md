# Báo cáo kiểm thử Alpha V1 local

**Ngày:** 26/10/2026, Asia/Ho_Chi_Minh. **Kết luận:** các luồng trong phạm vi demo tích hợp local đã đạt các kiểm tra bên dưới. Chưa nghiệm thu pilot, chất lượng y khoa hoặc AI thật.

## Phiên bản và môi trường

- Frontend gốc: Git `1392912750240aec53a96ef51a32d780ddff267f`; thay đổi Alpha nằm trong working tree, chưa tạo commit mới.
- Backend tiếp nhận từ `NLHN-YHDP-main.zip`, SHA-256 `5efe7976fb6d054e52c7532e58ba4c9837d3b6824aa4013c50de9e234f54bbc3`.
- Fingerprint runtime backend: `b88ae2dca68b3a054cb80987b35a53b123920d820061c334195d54c76ede012e` (157 file trong app/seed/migrations và cấu hình/lockfile).
- Fingerprint frontend: `c70d8aa365b2334484c4d6a78668446183cf636ab9da200ed57c3f0d110fa59f` (152 file trong src và package/config).
- Windows, Python **3.13.12**, Node **24.14.0**, FastAPI **0.143.0**, Pydantic **2.14.0**, psycopg **3.3.6**, FSRS **6.3.2**, PostgreSQL **16.13**.
- Frontend `http://127.0.0.1:5190`; backend `http://127.0.0.1:8000`; PostgreSQL loopback `:15433`. `APP_MODE=real`, `MODEL_PROVIDER=scripted`, `APP_ENV=dev`.
- Browser plugin not available; dùng Playwright **1.64.1**, Chromium **156**, viewport desktop **1440×1000** và mobile **390×844**. Mobile là giả lập Chromium, không phải xác nhận Safari/iOS hay thiết bị thật.

## Kết quả thực thi

| Kiểm tra | Kết quả | Bằng chứng/phạm vi |
|---|---|---|
| Regression backend | **1.121 PASS, 95 SKIP, 0 lỗi** | 1.216 trường hợp, 26 phút 11 giây; `.local/backend-tests.xml` |
| Gateway scripted sau chỉnh sửa cuối | **14 PASS** | `.local/scripted-tests.xml`; đủ bốn trạng thái, quotes đúng corpus, chặn cấu hình ngoài dev/test, không tạo model client ngoài, unknown quiz-chat không dùng nhầm kịch bản, seed lặp giữ hồ sơ/mật khẩu |
| Test frontend | **3 PASS** | UTF-8 chia qua nhiều network chunk, lỗi mất kết nối, kết thúc các bước đang chạy khi stream hỏng |
| Browser sau khi khởi động lại | **6 PASS**, 0 flaky | Người học + viewer + admin, mỗi vai trò trên hai viewport; `.local/playwright-results.json` |
| TypeScript/build | **PASS** | `npm.cmd run build` |
| Lint | **PASS** | `npm.cmd run lint` |
| Dependency Python | **PASS** | `pip check`; cài lại từ `requirements-lock.txt` thành công |
| OpenAPI | **PASS** | `python -m app.cli export-openapi --check`, hợp đồng `1.0.0-draft.1` giữ nguyên |
| Migration/seed lặp | **PASS** | Revision `0012`, không thêm migration; `seed-alpha` chạy lặp không sinh lại cohort |
| Script cài đặt/khởi động | **PASS** | Đã thực thi `setup-alpha.ps1 -SkipCohort` trên môi trường đã cài, rồi khởi động lại bằng `start-backend.ps1` và Vite |
| Dữ liệu khi tạo lại container | **PASS — 44/44 bảng** | `docker compose up -d --force-recreate --wait db`; row count và digest của mọi bảng public giữ nguyên, cả sau chạy lại setup |
| Backup/restore | **PASS — 44/44 bảng** | Backup custom 484.632 byte, restore vào `alphav1_restore_alpha_acceptance`; khớp digest của cả 44 bảng, gồm 22 đáp án learner không thuộc cohort synthetic |

95 trường hợp SKIP là nhánh điều kiện trong bộ contract gốc: **48 “implemented”**, **44 “no query parameters”**, **3 “stream”**. Đây không phải 95 chức năng được tự coi là đạt. Các API và SSE tương ứng còn được kiểm tra bởi các suite nghiệp vụ; 7 stub vẫn là ngoài phạm vi. Sau khi thêm guard cho câu hỏi quiz-chat ngoài kịch bản, đã chạy lại riêng toàn bộ 14 test scripted trên mã cuối; không cộng số này vào full regression như các test độc lập không trùng.

Dependency được cài từ venv mới và `npm ci` lúc bắt đầu. Script setup cũng đã được chạy lại thành công; chưa kiểm thử trên một máy Windows thứ hai chưa có Python/Node/Docker.

## Luồng trình duyệt đã kiểm tra

**Người học:** phát mã local mới → dùng form kích hoạt thật → consent bắt buộc → chọn học phần → đọc và trả lời sai → tạo thẻ → reload giữ lựa chọn/feedback → hoàn tất unit → ôn thẻ → mở đề ngắn → autosave một đáp án → reload giữ đáp án → nộp → đọc kết quả → xem tiến độ 56 ngày → hỏi “Tỷ lệ hiện mắc là gì?” → nhận SSE → mở passage → reload giữ hội thoại và citations.

Test thi hiện dùng API để chuẩn bị lượt thi, rồi thao tác chọn đáp án/autosave/nộp trên giao diện. Không coi bước bấm qua trang quy định đề thi là đã được tự động kiểm tra trong smoke này.

**Staff:** đăng nhập viewer, mở dashboard và chờ KPI hiển thị. Với admin, đăng nhập vào vận hành rồi bấm “Tổng hợp” để mở dashboard. Kiểm tra phản hồi API có KPI và không bị suppression ở phạm vi toàn quốc của dataset này; giữ nguyên ngưỡng 10. Các suite backend kiểm tra quyền và ẩn nhóm nhỏ.

| Kiểm tra UI | Kết quả |
|---|---|
| Đúng URL/title, có nội dung chính | PASS |
| Không có trang trắng/overlay lỗi trên luồng người học | PASS |
| Không có pageerror/console error trong luồng đã chạy | PASS; staff kiểm tra cả console warning |
| Chat mobile không tràn ngang | PASS |
| Câu trả lời và nguồn mở được | PASS |
| Dashboard có KPI thật sau khi hết loading | PASS |
| Nhãn AI/dữ liệu minh họa | PASS |

Header live dẫn tới nhịp học server; khối streak tính từ workspace local chỉ còn ở demo trình duyệt. Tiến độ live lấy API, không dùng số streak local làm kết quả chính thức.

Ảnh đã xem trực tiếp:

- [Chat mobile](../../test-results/alpha-learner-activate-con-3fcc5-ess-and-cited-scripted-chat-mobile/alpha-chat.png).
- [Dashboard admin desktop](../../test-results/alpha-staff-admin-alpha-local-dashboard-reads-the-real-API-desktop/alpha-dashboard.png).

Artifact trong `.local/` và `test-results/` được bỏ qua bởi Git. Chạy lại bộ kiểm thử để tạo lại trên checkout khác. Fingerprint dữ liệu là tại thời điểm kiểm tra phục hồi; lượt smoke cuối có tạo thêm tài khoản và hoạt động kiểm thử.

## Giới hạn và phạm vi chưa nghiệm thu

- Chưa mở CSV, bàn duyệt, tạo lượt luyện tự chọn, library card đầy đủ hoặc API đồng bộ bookmark/thông báo/lộ trình. Giữ `501`, nút khóa hoặc thông báo giới hạn tương ứng.
- Hỏi đáp, hint và giải thích dùng kịch bản; thời gian, token và chi phí ghi bởi gateway scripted không đại diện mô hình thật. Chưa đánh giá retrieval trên corpus chuẩn hoặc tính đúng đắn y khoa.
- Chưa load test, kiểm tra thiết bị thật/Safari, deploy qua HTTPS/reverse proxy online hoặc đánh giá toàn diện bảo mật production. Các kiểm tra quyền, consent, retry và privacy trong bộ backend không thay thế các đánh giá này.
- Chưa kiểm thử browser khi mất mạng thực, hoặc ngắt browser giữa SSE; có test unit/backend cho luồng lỗi và stream bị ngắt. Không ghi các ca mobile resilience đề xuất là đã đạt chỉ dựa trên smoke.
- Dashboard dùng cohort minh họa cộng hoạt động local; nhóm nhỏ có thể bị ẩn. Chưa nghiệm thu chính sách chống suy ngược giữa nhiều tổ hợp bộ lọc cho pilot.
- Khi mở lại một unit đã hoàn tất, backend demo có thể tạo lượt học lại. Smoke xác nhận completion từ phản hồi advance; không dùng GET `/next` sau completion như một phép đọc thuần không tạo lượt mới.

## Chạy lại

Theo README để setup và chạy backend. Chạy `powershell -ExecutionPolicy Bypass -File scripts/test-alpha.ps1` cho regression, frontend và browser. Smoke riêng: `npm.cmd run test:e2e`.

Trạng thái hiện tại đạt mục tiêu **demo tích hợp local** đã chốt. Các yêu cầu mở pilot được theo dõi riêng trong [backlog](handover.md).
