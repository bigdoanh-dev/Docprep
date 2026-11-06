# Kế hoạch tích hợp YHDP vào kiến trúc Phase 1

Ngày cập nhật: 06/11/2026.

## Trạng thái triển khai sau khi chốt kế hoạch

Nguồn YHDP cố định tại `c6615866028162b21c81ebc0a9939ab71e9ebed0`; checkpoint Phase 1 `1ee42fe`, tag `checkpoint/phase1-before-yhdp-20261106`. Nhánh tích hợp: `feat/phase1-yhdp-integration`. Không merge nguyên backend SQLite hoặc adapter `src/lib/live` của nhánh nguồn.

| Mốc đã duyệt | Phần thực hiện | Cổng còn lại |
|---|---|---|
| 0. Bảo toàn baseline | Checkpoint, nhánh riêng, commit nguồn và [ma trận chuyển đổi](yhdp-source-map.md) | Không tự push lên remote |
| 1. Adapter khi server tắt | Ollama generation/embedding, metadata, deadline, quarantine; provider disabled phục vụ nghiệp vụ/lịch sử | Kiểm tra hai model từ Chat khi server bật |
| 2. Frontend mới | Ghép Home/chat/markdown/cards; giữ auth/consent, nghiệp vụ server, SSE resume/cancel/idempotency | [Báo cáo chạy mới](yhdp-verification.md), không kế thừa kết quả nguồn làm bằng chứng chuyển đổi |
| 3. Embedding/retrieval | Migration 0015, PostgreSQL/pgvector, hash/model digest/corpus version, FTS+dense+RRF; index qua cùng worker/slot; pure dictionary/chunker tách khỏi SQLite | Thư viện chuẩn bị nội dung chưa phải importer/phát hành corpus thật; cần mapping/duyệt/chữ ký |
| 4. AI thật local/dev | CLI `check-models`, `index`, `job`; [runbook](ollama-local.md) | **Chờ server bật**; chưa xác minh generator/embedding thật |
| 5. Phase 1 đầy đủ | Giữ runtime 2+2 và công cụ bảo mật/vận hành; ghi rõ điều kiện nghiệm thu | Examiner/reranker, corpus ký số, scheduler/content-team, staging và tải/chất lượng cần đầu vào được duyệt |

Cấu hình local/dev đã chốt: generator `qwen3.5:9b-q4_K_M`, embedding `bge-m3`, context 16384. `backend/.env` đã nhận URL LAN do người dùng cung cấp; chỉ Chat đọc model env. `.env.phase1` giữ provider **disabled** trong lúc AI server tắt. Không cần probe server để hoàn thành adapter/test hợp đồng.

Chính sách thử nghiệm mới: **1 active turn, 1 model call toàn cục** dùng chung generation/embedding, queue 20, chờ queue 60 giây, deadline turn 360 giây, provider tối đa 300 giây trong deadline còn lại, stop/drain 390 giây. Không dùng các số này làm sizing GPU.

Frontend giữ `/api/v1`, token/refresh/role/error và SSE Phase 1. Bổ sung Home optional fields, mode gia sư và status `retrieving`; OpenAPI/TypeScript cập nhật đồng thời. Mode tạo/chấm câu hỏi gia sư mới chưa hỗ trợ (501), không dùng generator thay examiner. Vector lỗi thời không được dùng; technical failure không giả thành thiếu bằng chứng.

## Ma trận đáp ứng tài liệu kiến trúc

| Yêu cầu trong Word | Quyết định áp dụng | Bằng chứng cần có để nghiệm thu |
|---|---|---|
| Mục 3, 5, 6, 9: Chat và Business triển khai riêng; dự kiến chat ×2, api ×2 | Giữ hai entrypoint và bốn app containers; một Uvicorn process mỗi container. Các module học, thi, ôn cùng nằm trong Business. | Mỗi app khởi động và phát hành độc lập; mọi endpoint có một chủ thể; Business không tạo model client hoặc nhận model credentials. |
| Mục 2, 6, 9: Caddy, routing và SSE | Giữ frontend `/api/v1`, bỏ `/api` ở Caddy để backend nhận `/v1`. Hint/explain thuộc Chat; chấp nhận suggestion thuộc Business. | Đủ bốn upstream, health check và phân tải; API sai trả JSON; SSE không bị buffer; request POST không bị proxy phát lại. |
| Mục 4, 10: transaction nghiệp vụ | PostgreSQL là nguồn dữ liệu chính; đáp án → mastery → thẻ → hoạt động trong cùng transaction Business. | Lỗi giữa use case rollback; retry không nhân đôi đáp án, điểm, thẻ hoặc hoạt động. |
| Mục 6, 8, 10: Redis queue/slot/stream, một active turn mỗi learner | Giữ queue FIFO hữu hạn, worker lấy việc chung, turn/outbox PostgreSQL và slot toàn cục theo tài nguyên model. | Hai Chat instances không xử lý trùng hoặc vượt slot; hủy, timeout, mất lease, worker chết và Redis restart được phục hồi an toàn. |
| Mục 8, 10: lịch sử và SSE resume | Lưu hội thoại, turn và kết quả ở PostgreSQL; event ID và event tạm thời ở Redis Streams. | Reload, đổi Chat instance và retry không tạo câu trả lời mới; event hết hạn chuyển sang snapshot; không truy cập chéo learner. |
| Mục 6, 9, 10: gateway duy nhất đi tới model | Port giao thức Ollama vào gateway của Chat; mọi lời gọi generator, hint, explain, router và examiner chịu cùng guard/admission. | Không có model call từ Business hoặc trình duyệt; kiểm tra auth/consent/exam trước gọi và trước commit; ghi đúng model/prompt/corpus version. |
| Mục 5, 6, 10: embedding, vector, fusion, rerank và examiner theo kế hoạch | Đã port PostgreSQL FTS/vector/RRF và index qua worker cho local/dev; examiner/reranker và đánh giá chất lượng còn chờ cấu hình được duyệt. | Dữ liệu/index có phiên bản; có bộ đánh giá retrieval và kiểm tra nhận định; chứng minh routing đúng vai trò model và hạn mức tài nguyên. |
| Mục 6: content team riêng, corpus đã duyệt, gói có phiên bản/chữ ký và scheduler | Xây đường nạp corpus riêng, quyền đọc/ghi tối thiểu; content team không đọc learner; Chat đọc nội dung đã duyệt. | Kiểm tra chữ ký/hash/version, từ chối gói lỗi hoặc chưa duyệt; import lặp an toàn; đối soát corpus và nguồn trích dẫn. |
| Mục 10: quyền dữ liệu, schema và migration | Giữ `public` và lịch sử migration hiện có. D1–D7 là miền trách nhiệm để lập ma trận quyền; chỉ tách schema khi có đặc tả và migration được duyệt. | Role runtime không DDL; Chat không đọc identity hoặc ghi điểm/thẻ/thi; migration chạy một lần; budget pool theo tổng process. |
| Mục 10: che định danh và kiểm soát egress | Che ở client/server, kiểm tra ở gateway; log metadata, không lưu prompt/output thô hoặc tokens. Không tự bật provider bên ngoài. | Kiểm tra payload/log cho email, số định danh, token, IP, bí danh, session ID; không rò dữ liệu sang model hoặc log. |
| Mục 7, 10, 11: staging và vận hành | HTTPS, readiness theo dependency, metrics, backup/restore, drain và rollback tương thích schema. Đo tải kết hợp người đọc/học/thi/chat. | Thực đo 30/40/50 learners trên môi trường được duyệt; ghi queue wait, p50/p95, lỗi và tài nguyên; SLO chỉ áp dụng sau khi được chốt. |

Số lượng replica và các quota dev hiện tại không chứng minh năng lực model. Lộ trình đầy đủ bao gồm các yêu cầu corpus/retrieval/examiner; các phần đó chưa được tính là hoàn thành trong đợt hạ tầng local trước đây. Phase 2 huấn luyện vẫn là phạm vi và consent riêng.

## Cổng nghiệm thu còn lại

1. **Kết nối AI thật local/dev:** AI server bật, hai model đã có sẵn; xác nhận từ Chat container, index và chat/hint/explain thật trên nội dung được phép. Hiện chưa thực hiện vì server tắt.
2. **Model bổ sung:** Lead chốt examiner/reranker/standby, auth/health/cancel semantics, resource mapping và hạn mức. Giữ Tier 2 tắt; không dùng generator thay examiner.
3. **Nội dung:** chốt corpus được phép, mapping YHDP → module/unit, manifest/chữ ký/khóa xác minh và quy trình duyệt/phát hành; sau đó mới nối importer, scheduler và role content-team riêng. Hash embedding không thay chữ ký/duyệt nội dung.
4. **Vận hành thật:** staging HTTPS, secrets được cấp, monitoring/backup/drain/rollback; workload và SLO/RPO/RTO được duyệt; đo 30/40/50 learners với model thật. Số đo scripted lịch sử không chứng minh khả năng GPU.

PDF N1 được Word dẫn chiếu chưa được cung cấp; không coi thông số chưa đối chiếu là cấu hình triển khai. D1–D7 là miền trách nhiệm, chưa tự đổi schema public. Phase 2 huấn luyện và consent tương ứng là phạm vi riêng.

Báo cáo phân biệt ba trạng thái: **đã tích hợp local**, **đã kiểm chứng model thật**, **đã nghiệm thu Phase 1 đầy đủ**. Trong lúc AI server tắt chỉ có thể xác nhận trạng thái đầu tiên; không gộp các cổng chờ thành đã hoàn tất.
