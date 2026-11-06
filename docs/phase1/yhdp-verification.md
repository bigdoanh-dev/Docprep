# Kiểm chứng tích hợp YHDP — 06/11/2026

Nguồn UI/domain YHDP `c6615866028162b21c81ebc0a9939ab71e9ebed0`; checkpoint Phase 1 `1ee42fe`; nhánh bàn giao `feat/phase1-yhdp-integration`, chưa push. FE/BE cùng repository; lấy commit bàn giao bằng `git log -1 --oneline`. [Báo cáo 03/11](verification.md) chỉ là baseline lịch sử.

Môi trường: Windows PowerShell, Python 3.13, React/Vite, Docker Desktop Linux engine, PostgreSQL 16/pgvector và Redis thật. Phase 1 chạy 2 Business/2 Chat qua Caddy 18880; test dùng `phase1_test`, Alpha regression dùng `alphav1_test` ở project/volume riêng. Không dựng lại schema database demo.

## Bằng chứng chạy mới

| Nhóm | Kết quả | Artifact local (không đưa vào Git) |
|---|---|---|
| PostgreSQL/Redis Phase 1 | 49 PASS, 147,58s sau bổ sung bảo vệ exception bất thường | `.local/phase1-tests.xml`, `.local/yhdp-phase-final.log` |
| Gateway và quyền index | 26 PASS, 15,21s; implicit latest, digest đổi, model trả sai, index/chat/quarantine; Chat đọc/ghi index được, Business bị từ chối | `.local/yhdp-ollama-final.xml`, `.local/yhdp-ollama-final.log` |
| Frontend unit | 104 PASS, 0 FAIL; bao gồm bộ pure/demo tests tái sử dụng | `.local/yhdp-frontend-tests.log`, acceptance log |
| Build/lint | Build PASS; lint cuối PASS, không cảnh báo | `.local/yhdp-final-build.log`, `.local/yhdp-lint-final.log` |
| Browser AI disabled qua Caddy và Vite | 2 PASS trên mỗi bề mặt (4 ca), desktop/mobile; nghiệp vụ/lịch sử sẵn sàng, AI503, Home mở tutor gửi đúng một lần cả StrictMode | `.local/yhdp-offline-caddy.log` (21,4s), `.local/yhdp-offline-vite.log` (30,6s) |
| Browser scripted qua Caddy | 8 PASS, 2 SKIP đúng profile, 55s; learner và hai staff roles trên desktop/mobile, lost POST response/retry/reload/citation | `.local/yhdp-acceptance.log` |
| Routing/replica/fault | PASS: JSON404, private endpoints, 4 trạng thái nội dung, citations, idempotency, cả hai Business replicas, Redis restart, kill/failover Chat | `.local/phase1-deployment.json` |
| Backup/restore và volume | 50/50 bảng khớp row count/digest ở DB restore riêng; force-recreate PG giữ nguyên dữ liệu | Cùng deployment report |
| HTTPS/SSE local | PASS với CA localhost được xác minh; stream kết thúc final | `.local/phase1-tls.json` |
| Release/runtime | Bốn instances thay lần lượt có drain/readiness; graceful shutdown 390s; healthy, schema0015, model env chỉ vào Chat và provider cuối disabled | `.local/yhdp-graceful-release.log`, `.local/yhdp-runtime.json` |
| Toàn bộ Alpha regression | 1.122 PASS, 95 SKIP, 0 lỗi còn lại trên 1.217 node duy nhất qua hai lượt; không có node bị bỏ sót | `.local/yhdp-alpha-summary.json`, hai JUnit/log regression và completion |

Các nhóm có thể trùng test; không cộng lại thành tổng số độc lập. Offline tests bị skip trong profile scripted là có chủ đích; đã chạy riêng ở profile disabled. Kiểm thử model HTTP dùng `httpx.MockTransport`; PostgreSQL/Redis, auth, ownership, pipeline và persist turn vẫn chạy thật.

Regression Alpha được thực hiện qua **hai lượt**, không phải một lần chạy từ đầu liên tục sau sửa: lượt đầu 1.023 PASS/95 SKIP, dừng tại kiểm tra danh mục schema chưa khai báo hai bảng embedding. Đã thêm đúng `embedding_index`/`passage_embedding` vào danh sách kỳ vọng, giữ phép so sánh schema chính xác. Sau đó chạy lại ca lỗi và 98 ca chưa chạy: **99 PASS**, 128,95s. Đối chiếu collection với hai JUnit cho đủ 1.217 node, không còn failure/error. 95 SKIP giữ nguyên, không tính là PASS. Lượt đầu mất 1.774,29s; toàn bộ code nghiệp vụ được kiểm tra trên schema 0015.

## Ranh giới được kiểm tra

- Payload generator đúng model/context/non-streaming/JSON; embedding đúng model, shape hữu hạn/nonzero/normalized; token thiếu lưu null, cost null.
- Model role examiner chưa chốt bị từ chối; không fallback Anthropic hoặc log prompt/output/provider exception detail.
- Lỗi HTTP được xác nhận khác timeout/mất mạng/JSON wire không đáng tin. Không retry transport; call chưa rõ kết quả giữ quarantine qua Redis recovery.
- Index job cùng FIFO/slot với chat, learner không đọc được system job, corpus hash/model revision/version được kiểm tra; nội dung đổi không dùng vector cũ, index lặp không embed lại nội dung không đổi.
- Mode gia sư dùng nguồn của hội thoại đã sở hữu; lưu mode vào turn/history; mode auto giữ tương thích idempotency cũ; tạo/chấm quiz mới trả 501.
- Hai Chat instances: idempotency/payload conflict, learner lock, FIFO/queue/timeout/slot, fencing/late result, worker chết trước/sau model/commit, cancel và thay đổi exam/consent/account; SSE snapshot/resume/event expiry và pool không bị giữ khi hint/model chờ.
- DB roles: runtime không DDL, Chat không đọc identity/ghi điểm-thẻ-thi; quyền thêm chỉ dành cho index dẫn xuất. Model env có ở Chat, không có ở Business.

## Giới hạn và cổng chờ

**Chưa kiểm chứng model thật:** AI server tắt theo xác nhận người dùng. Provider cuối giữ `disabled`; URL/model local đã điền nhưng chưa gọi generator/embedding LAN, chưa đánh giá citation/retrieval/AI thật. Scripted acceptance là kiểm tra tích hợp, không phải kết quả model.

**Chưa nghiệm thu Phase 1 đầy đủ:** cần examiner/reranker/resource mapping, corpus/mapping được duyệt và gói ký số/khóa xác minh, scheduler/content-team, staging và workload/SLO/RPO/RTO được chốt. Chưa đo mới 30/40/50 với model thật hoặc tuyên bố năng lực GPU. Pure dictionary/chunker chưa nối thành importer/phát hành nội dung.

Các lượt test dừng vì DB Alpha chưa chạy, OpenAPI chưa export hoặc kiểm tra UI trước khi hoàn tất onboarding không được tính PASS. Đã khởi động đúng DB test, export contract và sửa flow kiểm thử; các kết quả cuối ở bảng trên lấy từ lượt hoàn chỉnh tương ứng. Bộ lọc privacy theo mẫu không nhận diện mọi PII. Rollback code chỉ với schema đã xác nhận tương thích; khôi phục bản cũ cần DB riêng và kiểm tra trước chuyển URL.

Tái lập theo [runbook local/Ollama](ollama-local.md) và `scripts/test-phase1.ps1`. `-ScriptedAcceptance` tạm tạo lại Chat, chờ Caddy nhận upstream rồi khôi phục provider trong finally. Không dùng script fault khi có người đang demo.
