# Kế hoạch tích hợp YHDP vào kiến trúc Phase 1

Ngày cập nhật: 06/11/2026.

Mục tiêu là tái sử dụng frontend và các module hữu ích của YHDP, đồng thời hoàn thiện kiến trúc Phase 1 theo tài liệu `AIRC_Kien_truc_backend_Alpha_V1_den_Phase_1.docx`. Kiến trúc đích giữ Business API và Chat Orchestrator độc lập, PostgreSQL, Redis và Caddy. SQLite và cách triển khai một FastAPI trong nhánh YHDP là hiện trạng của nguồn mã được tham khảo, không thay thế kiến trúc đích đã chọn.

## 1. Căn cứ và trạng thái đã xác nhận

- Đã đọc toàn bộ nội dung chính của file Word, gồm các mục 1–11. Word phân biệt hiện trạng Alpha, thiết kế Phase 1 và đề xuất triển khai; kế hoạch này giữ nguyên sự phân biệt đó.
- PDF thiết kế gốc ký hiệu N1 được Word dẫn chiếu chưa được đối chiếu trực tiếp. Thông số GPU, sơ đồ chi tiết D1–D7 và những quyết định còn mở trong N1 không được coi là đã xác nhận.
- Nguồn tái sử dụng là nhánh `sync/yhdp-frontend-api-v1`, tại commit `c6615866028162b21c81ebc0a9939ab71e9ebed0`. Người phụ trách xác nhận nhánh đã được test và hoạt động ổn định. Đợt tích hợp kế thừa baseline đó, tập trung kiểm tra các ranh giới thay đổi.
- Nền Phase 1 local có [kiến trúc hiện tại](architecture.md), [ma trận API](api-matrix.md) và [báo cáo ngày 03/11/2026](verification.md). Báo cáo local với scripted/fake không thay nghiệm thu model thật hoặc staging.
- `backend/.env` đã được cấu hình `YHDP_OLLAMA_URL` theo địa chỉ người phụ trách cung cấp. File được Git và Docker build bỏ qua. Kiểm tra GET `/api/version`, GET `/api/tags` và TCP ngày 06/11 từ máy phát triển chưa kết nối được; TCP timeout. Chưa kiểm tra đường mạng từ Chat container hoặc xác minh model trên server.
- Phase 1 hiện chỉ nhận `PHASE_MODEL_PROVIDER=disabled|scripted`; mã cấu hình hiện tại chưa đọc URL trong `backend/.env`. Thêm URL chưa bật Ollama cho runtime đang chạy.

## 2. Ma trận đáp ứng tài liệu kiến trúc

| Yêu cầu trong Word | Quyết định áp dụng | Bằng chứng cần có để nghiệm thu |
|---|---|---|
| Mục 3, 5, 6, 9: Chat và Business triển khai riêng; dự kiến chat ×2, api ×2 | Giữ hai entrypoint và bốn app containers; một Uvicorn process mỗi container. Các module học, thi, ôn cùng nằm trong Business. | Mỗi app khởi động và phát hành độc lập; mọi endpoint có một chủ thể; Business không tạo model client hoặc nhận model credentials. |
| Mục 2, 6, 9: Caddy, routing và SSE | Giữ frontend `/api/v1`, bỏ `/api` ở Caddy để backend nhận `/v1`. Hint/explain thuộc Chat; chấp nhận suggestion thuộc Business. | Đủ bốn upstream, health check và phân tải; API sai trả JSON; SSE không bị buffer; request POST không bị proxy phát lại. |
| Mục 4, 10: transaction nghiệp vụ | PostgreSQL là nguồn dữ liệu chính; đáp án → mastery → thẻ → hoạt động trong cùng transaction Business. | Lỗi giữa use case rollback; retry không nhân đôi đáp án, điểm, thẻ hoặc hoạt động. |
| Mục 6, 8, 10: Redis queue/slot/stream, một active turn mỗi learner | Giữ queue FIFO hữu hạn, worker lấy việc chung, turn/outbox PostgreSQL và slot toàn cục theo tài nguyên model. | Hai Chat instances không xử lý trùng hoặc vượt slot; hủy, timeout, mất lease, worker chết và Redis restart được phục hồi an toàn. |
| Mục 8, 10: lịch sử và SSE resume | Lưu hội thoại, turn và kết quả ở PostgreSQL; event ID và event tạm thời ở Redis Streams. | Reload, đổi Chat instance và retry không tạo câu trả lời mới; event hết hạn chuyển sang snapshot; không truy cập chéo learner. |
| Mục 6, 9, 10: gateway duy nhất đi tới model | Port giao thức Ollama vào gateway của Chat; mọi lời gọi generator, hint, explain, router và examiner chịu cùng guard/admission. | Không có model call từ Business hoặc trình duyệt; kiểm tra auth/consent/exam trước gọi và trước commit; ghi đúng model/prompt/corpus version. |
| Mục 5, 6, 10: embedding, vector, fusion, rerank và examiner theo kế hoạch | Đưa vào mốc mở rộng để đáp ứng đích đầy đủ; chọn thuật toán/model sau khi đối chiếu cấu hình và đánh giá. RRF/BM25/vector trong YHDP là ứng viên tái sử dụng; chưa có reranker/graph expansion hoàn chỉnh trong mã đó. | Dữ liệu/index có phiên bản; có bộ đánh giá retrieval và kiểm tra nhận định; chứng minh routing đúng vai trò model và hạn mức tài nguyên. |
| Mục 6: content team riêng, corpus đã duyệt, gói có phiên bản/chữ ký và scheduler | Xây đường nạp corpus riêng, quyền đọc/ghi tối thiểu; content team không đọc learner; Chat đọc nội dung đã duyệt. | Kiểm tra chữ ký/hash/version, từ chối gói lỗi hoặc chưa duyệt; import lặp an toàn; đối soát corpus và nguồn trích dẫn. |
| Mục 10: quyền dữ liệu, schema và migration | Giữ `public` và lịch sử migration hiện có. D1–D7 là miền trách nhiệm để lập ma trận quyền; chỉ tách schema khi có đặc tả và migration được duyệt. | Role runtime không DDL; Chat không đọc identity hoặc ghi điểm/thẻ/thi; migration chạy một lần; budget pool theo tổng process. |
| Mục 10: che định danh và kiểm soát egress | Che ở client/server, kiểm tra ở gateway; log metadata, không lưu prompt/output thô hoặc tokens. Không tự bật provider bên ngoài. | Kiểm tra payload/log cho email, số định danh, token, IP, bí danh, session ID; không rò dữ liệu sang model hoặc log. |
| Mục 7, 10, 11: staging và vận hành | HTTPS, readiness theo dependency, metrics, backup/restore, drain và rollback tương thích schema. Đo tải kết hợp người đọc/học/thi/chat. | Thực đo 30/40/50 learners trên môi trường được duyệt; ghi queue wait, p50/p95, lỗi và tài nguyên; SLO chỉ áp dụng sau khi được chốt. |

Số lượng replica và các quota dev hiện tại không chứng minh năng lực model. Lộ trình đầy đủ bao gồm các yêu cầu corpus/retrieval/examiner; các phần đó chưa được tính là hoàn thành trong đợt hạ tầng local trước đây. Phase 2 huấn luyện vẫn là phạm vi và consent riêng.

## 3. Cách tái sử dụng nhánh mới

### Frontend và hợp đồng công khai

- Lấy màn hình và tương tác mới; giữ contract Phase 1 làm chuẩn tích hợp. Lập bảng đối chiếu 59 operations hiện tại với 23 operations chính của YHDP, gồm path, request/response, quyền, idempotency và nơi lưu trạng thái.
- Không mang nguyên cơ chế lưu consent, đáp án thi trước submit, lịch sử chat hoặc tiến độ quan trọng trong `src/lib/live/` sang Phase 1. Các dữ liệu này đi qua Business/Chat và lưu bền vững phía server; trình duyệt chỉ giữ UI, draft và thông tin reconnect.
- Giữ activation, access/refresh token, role hiện tại và SSE `status/step/answer/final`. Không thay bằng JWT 12 giờ hoặc NDJSON từ backend YHDP. Chuẩn hóa lỗi theo `{error:{code,message_vi}}`; technical failure không giả thành thiếu bằng chứng.
- Đối chiếu các ID `de_muc/van_de` với module/unit hiện có bằng bảng mapping có phiên bản và được duyệt nội dung. Không suy diễn chúng tương đương chỉ từ thứ tự hoặc tên.
- Cập nhật OpenAPI và TypeScript cùng thay đổi; mọi thay đổi contract phải có ví dụ request/response và ca tương thích.

### Nghiệp vụ và dữ liệu nguồn

- Giữ luồng học/thi/ôn, deadline, chấm điểm, lịch ôn và quyền sở hữu ở Business. Chỉ port thuật toán thuần và khả năng hữu ích từ YHDP; không dùng workflow SQLite làm nguồn dữ liệu nghiệp vụ thứ hai.
- Tách parser DOCX, chia chunk, dictionary, tagging và thuật toán MCQ khỏi SQL/file-layout phụ thuộc backend YHDP. Đầu ra cần schema/version rõ, liên kết nguồn và trạng thái duyệt trước khi nạp PostgreSQL.
- Các hành động AI đề xuất tạo bài/thêm thẻ trở thành ý định nghiệp vụ được xác thực và thực hiện qua Business; Chat không ghi trực tiếp bảng học/thi/ôn.
- Reviewer của YHDP không được tự ánh xạ thành admin/viewer. Chốt quyền duyệt nội dung riêng trước khi đưa giao diện reviewer vào; CSV và những chức năng chưa hỗ trợ vẫn trả trạng thái đúng.

### Ollama và ranh giới gateway

- Dùng URL `YHDP_OLLAMA_URL` trong `backend/.env` làm đầu vào provider. Khi triển khai adapter, local Chat đọc cấu hình này; Compose chỉ cấp file/biến model cho hai Chat containers qua `env_file`, không cấp cho Business, frontend hoặc build image. Không đổi `BACKEND_URL` của frontend thành địa chỉ Ollama.
- Thêm provider `ollama` có chọn lựa rõ ràng, giữ `disabled` và scripted dev/test. Tái sử dụng giao diện `Gateway.complete → ModelResult`; đợt nối đầu dùng Ollama chat non-streaming bên trong, SSE bên ngoài giữ contract hiện tại. Không bật provider trước khi kết nối và model mapping được xác nhận.
- Dùng protocol đã có trong client YHDP cho `/api/chat` và `/api/embed` khi đúng vai trò. URL không xác nhận được model ID, auth, GPU, model resource mapping, context/token budget, timeout hoặc cancel semantics; không sao chép mặc định Qwen/bge-m3 thành cấu hình đã được Lead chốt.
- Điều chỉnh worker/gateway để phân biệt model call hoàn tất được xác nhận với trạng thái không xác định sau timeout/mất mạng. Trường hợp chưa chắc lời gọi trên server đã dừng phải giữ reservation cách ly; đóng HTTP hoặc lease hết hạn không được coi là đã hủy model. Không tự retry invocation không rõ kết quả.
- Port prompts/tutor moves, kiểm tra citations và kết quả có cấu trúc sau khi làm sạch payload. Không mang cơ chế `_llm_log` ghi messages/output thô của client YHDP vào đường dữ liệu learner.

## 4. Thứ tự thực hiện và đầu ra từng mốc

| Mốc | Công việc | Điều kiện kết thúc |
|---|---|---|
| 0. Chốt hợp đồng | Nhận diện baseline local và commit nguồn; hoàn thiện ma trận endpoint, quyền, trạng thái bền vững, nguồn nội dung và các quyết định model còn mở. | Mọi nhóm chức năng có nơi sở hữu; mỗi phần mã được phân loại giữ, tái sử dụng qua adapter hoặc triển khai ở mốc sau. |
| 1. Tích hợp frontend | Chuyển từng nhóm màn hình mới sang Business/Chat Phase 1: auth/consent → học/ôn → thi/tiến độ → chat/citations → dashboard. | Trọn luồng chạy qua Caddy; không giảm mức bảo đảm dữ liệu so với baseline Phase 1. |
| 2. Nối model qua Chat | Xác minh đường mạng từ Chat tới URL đã cung cấp; chốt model/config; triển khai Ollama gateway, privacy, deadlines và xử lý invocation không xác định. | Test lỗi provider/fencing/hủy đạt; thử hỏi đáp có nguồn trên dữ liệu được phép; bật real generation có kiểm soát ở dev/staging. |
| 3. Hoàn thiện pipeline nội dung và AI | Port ingest cần thiết; triển khai gói corpus được duyệt, xác minh chữ ký và scheduler; bổ sung vector/fusion/rerank/examiner theo đặc tả đã chốt. | Corpus có phiên bản, nguồn truy vết được; index đổi model được rebuild; chất lượng retrieval/citations/examiner có báo cáo riêng. |
| 4. Nghiệm thu Phase 1 đích | Staging HTTPS, hai API/hai Chat, model và đường mạng thật; fault tests, tải phối hợp, monitoring, backup/restore, drain/rollback. | Các tiêu chí Word mục 11 có bằng chứng tương ứng; các giới hạn còn lại được Lead chấp nhận rõ ràng trước pilot. |

Các mốc 0–2 là thứ tự tích hợp gần nhất. Mốc 3–4 giữ đủ yêu cầu kiến trúc đích, không được bỏ khỏi backlog hoặc ghi đã hoàn thành chỉ vì đợt tách runtime/scripted đã chạy ổn định. Chuẩn bị nội dung và quyết định hạ tầng có thể tiến hành song song; pipeline chỉ được mở cho learner sau khi vượt các điều kiện của nó.

## 5. Kiểm thử và tiêu chí nghiệm thu tích hợp

Kế thừa kết quả test của hai nền đã được xác nhận. Chạy regression có mục tiêu cho phần vừa chuyển, và chạy bộ bắt buộc trước mỗi mốc phát hành; không coi một lần chạy ổn định trên backend YHDP là bằng chứng cho runtime Phase 1 sau khi port.

- **Hợp đồng/frontend:** URL/rewrite đúng, JSON error đúng, dữ liệu server thay cho localStorage; auth/refresh/consent/role; học/ôn/thi/tiến độ/dashboard; desktop/mobile và mở citation.
- **Nghiệp vụ:** gửi lặp, rollback giữa đáp án/mastery/thẻ/hoạt động, autosave/resume, server deadline, submit một lần, lệch giờ client và không lộ đáp án khi thi.
- **Điều phối:** cùng learner qua hai instances, FIFO cấp lượt, queue đầy, slot theo tài nguyên, fencing cả khi commit/nhả lease; Redis restart và worker chết trước/sau invocation/commit.
- **Gateway thật:** phản hồi hợp lệ/sai cấu trúc, model không tồn tại, auth lỗi, timeout, mất mạng và hủy; invocation không xác định không bị gọi lại hoặc cấp trùng slot. Không có external fallback ngầm.
- **Quyền/privacy:** không truy cập chéo learner; thi/consent/account đổi khi đang chờ/chạy; prompt và log không mang định danh/token; Business không gọi model; Chat không ghi nghiệp vụ.
- **Nguồn nội dung:** chữ ký/hash/version và trạng thái duyệt; import lặp; corpus/model/index đổi phiên bản; quyền content team; citations trỏ tới nội dung thực đã được duyệt.
- **Vận hành/tải:** dependency readiness, failover, restore vào DB riêng, release từng instance có drain; tải 30/40/50 learners theo workload được duyệt. Đo model thật gồm TTFT, tokens/s khi provider cung cấp số đo, độ trễ generator/examiner và queue wait; không điền GPU metrics giả.

## 6. Quyết định còn cần xác nhận

1. Đường mạng từ máy triển khai/Chat đến Ollama: LAN, VPN/WireGuard, firewall và auth. Timeout từ máy phát triển hiện tại chưa xác định nguyên nhân phía server.
2. Model ID theo từng vai trò generator, embedding, reranker, examiner/standby; endpoint tương ứng, health/cancel semantics và resource/slot budget được duyệt. Một URL Ollama chưa xác nhận toàn bộ topology GPU trong Word.
3. Corpus được phép sử dụng, tiêu chí chuyên môn/AI, mapping nội dung, manifest/chữ ký, khóa xác minh và quy trình duyệt/phát hành.
4. Workload 30–50 learners, tỷ lệ/tần suất gọi AI, mức chờ/lỗi/p95 chấp nhận, RPO/RTO và môi trường staging.

Những mục này là điều kiện đầu vào của mốc tương ứng; không được tự chọn giá trị để báo hoàn thành. Báo cáo cuối ghi riêng yêu cầu theo Word, phương án triển khai đã chọn, bằng chứng kiểm thử và mục còn chờ quyết định.
