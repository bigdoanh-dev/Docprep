# Báo cáo phần backend đã thực hiện trong AI Tutor Alpha V1

**Ngày chuẩn bị:** 13/11/2026.\
**Phiên bản đối chiếu:** nhánh `feat/alpha-v1-backend`, commit `29708ae`.\
**Thời lượng:** khoảng 8–10 phút trình bày, thêm 3–5 phút demo nếu cần.\
**Mục đích:** báo cáo phần backend đã triển khai, giải thích cách hoạt động và nêu rõ những phần còn thiếu. Lời thoại dùng cách xưng “em” để trình bày với Lead.

## 1. Thông điệp mở đầu

> Trong bản Alpha V1, em đã tích hợp backend thật cho luồng tài khoản, học, ôn thẻ, thi thử, tiến độ và dashboard. Dữ liệu được lưu trong PostgreSQL, điểm và lịch ôn do backend xử lý. Sau nền tảng Alpha, code hiện tại đã bổ sung tách Business API và Chat, điều phối Redis và adapter Ollama. Tuy nhiên AI thật đang chưa bật, nội dung vẫn là dữ liệu minh họa và em chưa coi đây là bản Phase 1 đã nghiệm thu đầy đủ.

Điều cần người nghe nhớ: **đã có nghiệp vụ backend và lưu dữ liệu thật; AI, nội dung chuyên môn và năng lực vận hành thật còn các bước nghiệm thu riêng.**

## 2. Phân biệt Alpha ban đầu và code hiện tại

| Giai đoạn | Phần đã có trong code | Cách trình bày |
|---|---|---|
| Alpha V1 ban đầu | FastAPI dạng modular monolith, PostgreSQL, học/ôn/thi, chat pipeline và provider scripted | Nền tảng backend của bản demo tích hợp. |
| Các cập nhật sau Alpha | Business ×2, Chat ×2, Caddy, Redis, turn/outbox, SSE resume/cancel và gateway Ollama | Phần nâng cấp hạ tầng đã bổ sung trên code Alpha. Không mô tả đây là kiến trúc Alpha ban đầu. |
| Snapshot hiện tại | Đăng nhập tên/mật khẩu, migration đến 0016, frontend main ghép với API Phase 1; cấu hình gần nhất giữ AI disabled | Bản đang dùng để báo cáo, vẫn phục vụ local/demo. |

Lần kiểm tra HTTP chỉ đọc khi chuẩn bị tài liệu ngày 13/11 không kết nối được API cổng 18880. Tài liệu này dựa trên code và báo cáo chạy đã ghi; không tuyên bố các dịch vụ đang chạy hoặc toàn bộ test vừa được chạy lại. Bằng chứng khởi động gần nhất được ghi ngày 12/11 trong [README chạy local](../../README-RUN-LOCAL.md).

## 3. Những phần backend đã làm được

| Nhóm | Đã triển khai | Giá trị đối với người dùng/hệ thống |
|---|---|---|
| Tích hợp frontend | Frontend gọi `/api/v1`; proxy chuyển về backend `/v1`; giữ contract danh sách và lỗi | Giao diện có thể dùng API và database thật thay vì chỉ thao tác dữ liệu trong trình duyệt. |
| Tài khoản và quyền | Username/mật khẩu cho learner, email/mật khẩu cho staff; access/refresh token; logout; role và kiểm tra chủ sở hữu | Người học, cán bộ xem báo cáo và quản trị có quyền tương ứng. |
| Consent và vòng đời dữ liệu | Yêu cầu đồng ý dịch vụ, rút consent, xem/cập nhật hồ sơ, xuất/xóa dữ liệu theo API hiện có | Backend kiểm tra điều kiện sử dụng, không chỉ dựa vào giao diện. |
| Học và luyện trong phiên | Học phần, unit, bước học, trả lời, hoàn tất, phiên học ngày và bộ luyện do server cấp | Lưu tiến độ và tiếp tục học từ trạng thái đã ghi. |
| Chấm câu trả lời | Lưu đáp án, chấm đúng/sai, cập nhật mastery, tạo thẻ khi sai và ghi hoạt động | Nghiệp vụ được xử lý trong transaction; có idempotency ở các đường ghi liên quan. |
| Ôn thẻ | Deck, thẻ đến hạn, đánh giá ôn và lịch FSRS; giới hạn thẻ mới/lượt ôn | Lịch ôn được lưu trên server, không phụ thuộc một trình duyệt. |
| Thi thử | Start/resume, autosave, deadline server, submit/results, xem lại sau nộp; đề cố định và đề tự ráp theo cấu hình | Backend quản lý thời gian, chấm và trả kết quả; nộp lại không chấm thành một lượt mới. |
| Tiến độ | Mastery/coverage, ưu tiên học, thống kê bài thi, nhịp học và ước tính ghi nhớ | Số liệu có nguồn từ đáp án, thẻ và hoạt động đã lưu. |
| Dashboard | Tổng hợp và xuất báo cáo theo API hiện có, giữ quy tắc ẩn nhóm nhỏ | Có dữ liệu minh họa để trình diễn, không hạ ngưỡng ẩn để làm đẹp số liệu. |
| Chat và nguồn | Session, lịch sử, hint/explain, citations, rating; pipeline scripted và gateway Ollama | Có đường tích hợp AI qua backend; việc sinh câu trả lời thật hiện chưa được bật/kiểm chứng. |
| Redis và worker | FIFO, giới hạn queue/slot, một active turn mỗi learner, idempotency, fencing, cancel và phục hồi | Phần điều phối đã có code và kiểm thử local, không chỉ đổi cấu trúc thư mục. |
| Môi trường và vận hành | Docker Compose, migration/seed, roles, health/readiness, metrics, công cụ backup/restore và drain | Có cách dựng lại môi trường và kiểm tra vận hành local. |

Theo [ma trận API hiện tại](../phase1/api-matrix.md), hợp đồng Phase 1 có **60 operations: 48 thuộc Business, 12 thuộc Chat**. Trong đó **7 operations chủ động trả 501**; không trình bày thành 60 chức năng đã hoàn thiện. Entrypoint Alpha riêng có 56 operations, không trộn hai số lượng này.

## 4. Cách tổ chức backend và trách nhiệm dữ liệu

### 4.1. Kiến trúc hiện tại để giải thích ngắn gọn

```text
Frontend React
    → /api/v1 → Caddy/proxy
        → Business API: tài khoản, học, ôn, thi, tiến độ, dashboard
        → Chat Orchestrator: chat, hint/explain, nguồn, xử lý turn
            ↔ Redis: queue, lock, slot, event SSE
        → PostgreSQL: dữ liệu nghiệp vụ, nội dung, turn và lịch sử
        → Model Gateway của Chat → provider được cấu hình
```

Mỗi ứng dụng giữ cấu trúc **API → service → repository**. Các thuật toán như mastery, ưu tiên học, FSRS và ráp đề nằm ở module engine. Backend dùng chung package nhưng Business và Chat có entrypoint/lifespan riêng.

**Lời thoại:**

> API nhận request và kiểm tra quyền. Service xử lý một nghiệp vụ hoàn chỉnh; repository làm việc với PostgreSQL. Các thuật toán được tách riêng để kiểm thử. Hiện em đã tách runtime Business và Chat để phần AI có thể được vận hành riêng, còn nghiệp vụ lưu đáp án, cập nhật năng lực và tạo thẻ vẫn giữ cùng một transaction.

### 4.2. Các nhóm bảng chính

| Nhóm | Ví dụ bảng | Dữ liệu lưu |
|---|---|---|
| Tài khoản và quyền | `learner`, `learner_identity`, `learner_credential`, `staff_user`, `auth_token`, `consent_record` | Hồ sơ, mật khẩu băm, token và consent. |
| Nội dung | `document`, `passage`, `question`, `content_item`, `module`, `unit` | Nguồn kiến thức và nội dung học/thi có phiên bản. |
| Học và ôn | `unit_session`, `item_response`, `mastery`, `card` | Trạng thái học, đáp án, năng lực và lịch thẻ. |
| Thi thử | `exam_form`, `exam_attempt` và dữ liệu đáp án liên quan | Đề, lượt thi, thứ tự câu, deadline và kết quả. |
| Hội thoại và điều phối | `chat_session`, `chat_message`, `ai_turn`, `ai_outbox`, `ai_model_call` | Lịch sử, trạng thái xử lý và dấu vết lời gọi model. |
| Chỉ mục dẫn xuất | `embedding_index`, `passage_embedding` | Model/corpus version, hash và vector khi đã lập index. |

Tồn tại bảng không có nghĩa đã có dữ liệu chuyên môn đầy đủ hoặc model đã chạy thật. PostgreSQL giữ dữ liệu bền vững; Redis giữ trạng thái điều phối tạm thời và được dựng lại theo trạng thái PostgreSQL khi phục hồi.

## 5. Các luồng nên giải thích trong buổi báo cáo

### 5.1. Đăng nhập và consent khoảng 45 giây

> Em đã bổ sung form tên đăng nhập và mật khẩu cho người học, đồng thời giữ email cán bộ. Backend trả access/refresh token cùng role thật. Người học chưa đồng ý dịch vụ phải qua bước consent. Mật khẩu được băm bằng Argon2id, có giới hạn đăng nhập sai và kiểm tra quyền theo từng API. Tài khoản hiện được cấp/đặt lại qua CLI; chưa có tự đăng ký hoặc quên mật khẩu qua email.

Điểm kỹ thuật khi được hỏi: migration 0016 thêm bảng credential riêng; Chat không được đọc bảng credential hoặc learner identity. Reset mật khẩu thu hồi token cũ, có xử lý đồng thời với login/refresh. API mã kích hoạt cũ vẫn được giữ tương thích.

### 5.2. Học và trả lời câu hỏi khoảng 1 phút

```text
Người học gửi đáp án
    → kiểm tra token, consent, quyền và trạng thái phiên
    → lấy đáp án chuẩn trên server, chấm đúng/sai
    → lưu câu trả lời và cập nhật mastery
    → nếu sai: tạo hoặc dùng thẻ ôn theo quy tắc chống trùng
    → ghi hoạt động và commit transaction
    → trả kết quả về frontend
```

> Phần quan trọng em đã làm là nối thao tác trên giao diện với dữ liệu server. Điểm và đáp án chuẩn do backend quản lý. Khi trả lời sai, hệ thống có thể tạo thẻ từ câu hỏi và nguồn sẵn có, không cần gọi AI. Các bước ghi liên quan được xử lý trong transaction và kiểm tra idempotency để retry không tạo thêm một kết quả mới.

Mastery là ước lượng theo lịch sử câu trả lời và thuật toán hiện có; không coi đó là kết luận chuyên môn hay dự đoán chắc chắn kết quả thi thật.

### 5.3. Ôn thẻ và tiến độ khoảng 1 phút

> Backend quản lý thẻ đến hạn và dùng FSRS để tính lịch ôn sau mỗi lần người học đánh giá độ nhớ. Tiến độ đọc từ đáp án, lịch sử ôn và hoạt động đã lưu. Các phần chưa đủ dữ liệu được phân biệt với điểm bằng 0.

Nếu mở biểu đồ “hiện tại 100%, sau 7 ngày 77%”, giải thích rõ:

- Đây là dự báo khả năng nhớ của **các thẻ đã ôn**, tính từ trạng thái FSRS; không phải mức độ nắm vững toàn bộ học phần.
- FSRS có thể dự báo ngay sau lần ôn đầu bằng tham số mặc định; số liệu sẽ thay đổi theo các lượt ôn tiếp theo.
- 77% không phải kết quả quan sát sau 7 ngày, cũng không phải câu trả lời do LLM sinh ra.

### 5.4. Thi thử khoảng 1 phút

> Em đã có luồng bắt đầu hoặc làm tiếp một lượt thi, lưu từng đáp án, tính thời gian theo deadline server, nộp và xem kết quả. Khi nộp, backend tự chấm theo đáp án chuẩn; không dùng LLM để chấm trắc nghiệm. Các câu bỏ trống được tách riêng, không coi là đã có một câu trả lời để cập nhật mastery. Người dùng không được đọc đáp án chuẩn của bài thi trước khi nộp.

Điểm bổ sung khi được hỏi:

- Reload có thể khôi phục lượt đang làm và đáp án đã lưu.
- Đồng hồ trình duyệt lệch không thay deadline server.
- Nộp lại trả kết quả đã lưu, không nhân đôi điểm/thẻ.
- `fresh=true` giữ hành vi đã quy định: nộp lượt đang mở rồi tạo lượt mới.
- Có đề tự ráp theo cấu hình local hiện có; chưa coi ngân hàng nhỏ hiện tại là đủ đại diện blueprint kỳ thi thật.

### 5.5. Chat, SSE và gateway khoảng 1 phút

> Phần Chat đã có session, lưu lịch sử, mở nguồn trích dẫn, gợi ý và giải thích. Response chat dùng SSE để giao diện nhận các trạng thái xử lý và kết quả cuối. Frontend có turn ID, idempotency key và event cursor để nối lại sau reload/ngắt kết nối. Em đã tích hợp adapter Ollama cho generation và embedding, nhưng provider hiện giữ disabled nên chưa có bằng chứng gọi model thật thành công.

Scripted provider chỉ dùng dev/test để kiểm tra bốn trạng thái: trả lời được, thiếu bằng chứng, từ chối và cần làm rõ. AI-disabled trả lỗi kỹ thuật rõ ràng; không chuyển lỗi hạ tầng thành câu trả lời thiếu bằng chứng hoặc báo thành công giả.

**Nếu Lead hỏi “AI đã chạy chưa?”:**

> Đường tích hợp, gateway và pipeline đã có, scripted/fake đã được dùng để kiểm thử. Còn generator và embedding trên server thật chưa được nghiệm thu; em đang để disabled theo cấu hình đã thống nhất.

### 5.6. Redis queue và chống xử lý trùng khoảng 1 phút

> Phần Redis và queue đã được code, không chỉ refactor. Hai Chat instances dùng chung FIFO queue, learner lock, model slot và event stream. Turn và outbox được lưu trong PostgreSQL trước; worker lấy việc qua Redis. Một người học chỉ có một turn đang mở; retry cùng key và nội dung gắn lại turn cũ, khác nội dung thì báo conflict.

Khi giải thích phục hồi, chỉ cần nêu:

- Worker có owner/fencing token để worker cũ không ghi đè kết quả mới.
- Mất kết nối SSE không tự hủy tác vụ; client đọc lại trạng thái/kết quả.
- Redis restart có cơ chế đối soát từ PostgreSQL.
- Lời gọi model chưa biết đã dừng hay chưa được giữ cách ly, không tự gọi lại hoặc nhả slot chỉ vì timeout.

Những cơ chế này đã được kiểm thử local theo báo cáo; chưa chứng minh sức chịu tải GPU hay năng lực phục vụ 30–50 người đồng thời.

### 5.7. Quyền và vận hành khoảng 45 giây

> Em đã tách role migrator và runtime. Chat không được đọc định danh/credential hoặc ghi điểm, thẻ, lượt thi. Có health, readiness, metrics, công cụ backup/restore và release có drain. Database và Redis dùng mạng nội bộ trong Compose. Đây là nền vận hành local, chưa phải nghiệm thu bảo mật hoặc hạ tầng production.

Các giới hạn cần nói đúng: bộ lọc định danh theo mẫu không nhận diện mọi PII; Business còn có quyền DB rộng ở một số miền và cần rà soát khi mở kho tài liệu mới; Compose không tự cung cấp rolling deployment hoàn chỉnh.

## 6. Bằng chứng kiểm thử nên đưa vào báo cáo

Các số dưới đây là **kết quả đã ghi trong tài liệu**, không phải lượt chạy mới ngày 13/11. Không cộng các nhóm thành một tổng test duy nhất vì có phạm vi và thời điểm khác nhau.

| Thời điểm / phạm vi | Kết quả đã ghi nhận | Nguồn |
|---|---|---|
| 10/11, tài khoản/schema | 88 ca đạt | [Runbook password login](../phase1/password-login.md) |
| 10/11, Phase 1 | 52 ca đạt | Cùng runbook; DB test riêng. |
| 10/11, frontend | 124 unit test, build và lint đạt | Cùng runbook. |
| 10/11, browser | 18 ca đạt qua Vite và 18 ca tương ứng qua Caddy; mỗi lượt bỏ qua 2 ca cần scripted trong profile disabled | Cùng runbook; desktop/mobile. |
| 10/11, contract | 310 ca đạt, 97 ca bỏ qua, tổng hợp qua hai lượt sau cập nhật assertion số operation | Cùng runbook; không báo thành một lượt full suite sạch liên tục. |
| 06/11, queue/gateway/fault | Báo cáo có kiểm tra idempotency, FIFO/slot, worker chết, Redis restart, citations và adapter phản hồi giả | [Kiểm chứng YHDP](../phase1/yhdp-verification.md); thuộc baseline trước password login. |
| 12/11, khởi động và đăng nhập | Setup exit 0; schema 0016; bốn app healthy; login và `/me` HTTP 200, reload trên 1440/390 qua Vite/Caddy đạt | [README chạy local](../../README-RUN-LOCAL.md). |

**Cách nói ngắn:**

> Em có kiểm thử backend cho tài khoản, quyền, transaction và điều phối, cùng browser test cho các luồng tích hợp. Báo cáo ghi rõ ngày, môi trường, ca bị skip và provider đang dùng. Các test với scripted/fake xác nhận tích hợp và xử lý lỗi, chưa đánh giá chất lượng model thật.

## 7. Kịch bản demo 3–5 phút

### 7.1. Chuẩn bị trước buổi trình bày

Mở Docker Desktop, vào thư mục chứa `package.json` rồi chạy:

```powershell
cd D:\InternAIRC\AI_TuTor\ALPHAV1\Docprep_FE
npm.cmd run dev:full
```

Giao diện mặc định: `http://127.0.0.1:5190/dang-nhap`. Caddy/API: `http://127.0.0.1:18880`. Nếu đổi cổng thì theo `.env.phase1` và [hướng dẫn local](../../README-RUN-LOCAL.md).

Tài khoản minh họa: `learner.demo` / `AlphaLocal2026!`; nếu đã đổi mật khẩu thì dùng mật khẩu hiện tại. Không bấm “Dùng dữ liệu trải nghiệm” khi mục tiêu là chứng minh backend PostgreSQL thật. Chuẩn bị sẵn learner khác bằng CLI nếu cần trình diễn lần đầu/consent; không reset DB hoặc tài khoản đang dùng chỉ để demo.

### 7.2. Trình tự demo

| Bước | Thao tác | Điều cần chỉ ra |
|---|---|---|
| 1 | Kiểm tra `/api/health`, đăng nhập learner | API real; provider disabled là trạng thái được công bố. Nếu learner đã consent thì không cần hiện lại bước consent. |
| 2 | Mở học phần đã có dữ liệu, trả lời một câu | Kết quả do API trả; đáp án được ghi server. |
| 3 | Reload rồi mở tiến độ/ôn thẻ | Trạng thái đã lưu vẫn còn; thẻ/lịch ôn có nguồn từ nghiệp vụ. Chọn câu sai nếu cần minh họa tạo thẻ. |
| 4 | Mở bài đánh giá ngắn, chọn đáp án, reload, nộp | Autosave, làm tiếp và kết quả chấm server. Kiểm tra trước rằng phiên demo không bị bài đang mở khác ảnh hưởng. |
| 5 | Mở chat sau khi đã nộp bài thi | Khi disabled, nêu thông báo AI chưa bật; không trình diễn một câu trả lời giả như model thật. |
| 6 nếu còn thời gian | Đăng nhập cán bộ bằng cửa sổ riêng, mở dashboard | Dashboard đọc dữ liệu PostgreSQL, có dữ liệu synthetic và quy tắc ẩn nhóm nhỏ. |

Nếu cần demo câu trả lời/citation scripted, chuẩn bị một môi trường dev/test riêng theo [runbook](../phase1/ollama-local.md); thông báo rõ đang mô phỏng. Không đổi provider giữa buổi trên môi trường có người đang dùng.

## 8. Những phần chưa nên báo cáo là hoàn thành

| Phần | Trạng thái cần nói rõ |
|---|---|
| Ngân hàng nội dung đầy đủ | Theo kiểm tra ngày 12/11: 42 câu không synthetic nhưng vẫn là nội dung demo, nhãn phủ 2/54 vấn đề; 564 câu synthetic phục vụ mô phỏng. Không phải bộ chuyên môn đã thẩm định. |
| AI thật | Chưa kiểm chứng generator/embedding LAN, chất lượng trả lời và citations với model thật. Adapter có trong code không đồng nghĩa server/model đã sẵn sàng. |
| Index runtime | Kiểm tra ngày 12/11 ghi nhận 0 embedding trong runtime. Vector trong `data.zip` là dữ liệu nguồn riêng, chưa được nhập/kiểm chứng thành index phục vụ. |
| Kho tài liệu mới | Mới có [bản đề xuất thiết kế DB tài liệu](../phase1/document-db-design-proposal.md). Chưa tạo các bảng đề xuất, importer/duyệt/release mới. |
| Duyệt chuyên gia/CSV/report | Bảy endpoint stub tiếp tục trả 501: import/confirm tài khoản, review queue/item/decision/reports và gửi report. Chưa phải workflow hoàn chỉnh. |
| Model và corpus bổ sung | Examiner/reranker, corpus được duyệt/ký số, mapping, content team và scheduler còn điều kiện chờ. |
| Production và tải | Chưa nghiệm thu staging, SLO, tải 30/40/50 với model thật hoặc bảo mật production. |

Trong code đã có thuật toán và dữ liệu lưu thật, nhưng bản bàn giao vẫn ở mức **tích hợp local bằng dữ liệu minh họa**. Nội dung demo được seed ở trạng thái approved không tự chứng minh đã được chuyên gia duyệt.

## 9. Các câu Lead có thể hỏi

**Em tự xây mới toàn bộ backend hay tận dụng demo?**\
Em tận dụng backend FastAPI/PostgreSQL trong demo, giữ các nghiệp vụ và bộ kiểm thử có sẵn, rồi tích hợp frontend, sửa contract và bổ sung các phần nâng cấp. Không trình bày toàn bộ mã kế thừa là được viết mới từ đầu.

**Frontend mới đã dùng backend thật chưa?**\
Đã có luồng live dùng API và PostgreSQL, có báo cáo browser test. Bên cạnh đó vẫn có chế độ trải nghiệm riêng trong trình duyệt; cần chọn đúng live khi demo.

**Điểm, thời gian thi và lịch ôn nằm ở đâu?**\
Backend quản lý và lưu PostgreSQL. Trình duyệt hiển thị và gửi thao tác; không quyết định đáp án chuẩn, điểm hoặc deadline.

**Redis/queue đã code chưa?**\
Đã có admission, worker, FIFO, global slot, learner lock, turn/outbox, fencing và Redis Streams; có kiểm thử local và fault scenarios được ghi trong báo cáo. Chưa đo năng lực model thật.

**AI tắt thì chức năng học/thi/ôn có chạy không?**\
Có. Chấm trắc nghiệm, tạo thẻ từ câu sai, tính FSRS và tiến độ là nghiệp vụ backend. Chat/hint/explain sinh nội dung mới cần provider hoạt động.

**Lần đầu ôn đã có 77% thì con số đó từ đâu?**\
Đó là dự báo FSRS cho các thẻ đã ôn dựa trên đánh giá và tham số mặc định; không phải đo trí nhớ toàn học phần hoặc kết quả model AI.

**Reload hoặc gửi lại có làm mất/nhân đôi kết quả không?**\
Các đường nghiệp vụ liên quan đã có dữ liệu server và idempotency; thi có autosave/resume, Chat có turn snapshot/event cursor. Báo cáo local có các ca kiểm thử, nhưng không dùng kết quả đó để bảo đảm mọi tình huống production chưa đo.

**Phần tiếp theo em sẽ làm gì?**\
Ưu tiên chốt DB tài liệu, form phân loại và người duyệt với Lead; sau đó triển khai importer/duyệt/phát hành có kiểm soát. Khi model server sẵn sàng thì kiểm tra model, lập index và nghiệm thu AI thật, rồi mới tiến tới staging và đo tải theo workload đã chốt.

## 10. Lời kết khoảng 20 giây

> Kết quả chính của em là đã đưa luồng học, ôn và thi sang backend có dữ liệu bền vững, bổ sung đăng nhập, quyền, kiểm thử và nền điều phối Chat dùng Redis. Em đã chuẩn bị đường tích hợp model, nhưng hiện còn chờ nội dung được duyệt và xác minh model thật. Bước tiếp theo em cần chốt cùng anh là thiết kế kho tài liệu và quy trình phát hành để AI sử dụng đúng nguồn.

## 11. Bản nói rút gọn khoảng 90 giây

> Trong Alpha V1, em đã tích hợp frontend với backend FastAPI và PostgreSQL thật. Các nhóm nghiệp vụ gồm tài khoản và consent, học theo unit, trả lời câu hỏi, ôn thẻ, thi thử, tiến độ và dashboard.
>
> Backend quản lý đáp án, điểm, deadline bài thi và lịch ôn. Khi trả lời, hệ thống lưu kết quả, cập nhật mastery, tạo thẻ khi sai và ghi hoạt động trong transaction. Thi đã có autosave, resume và nộp lại không tạo thêm kết quả chấm. Thẻ dùng FSRS; các tỷ lệ nhớ là ước tính trên thẻ đã ôn.
>
> Sau nền tảng Alpha, em đã bổ sung kiến trúc Business API và Chat chạy riêng, đứng sau Caddy. Redis điều phối queue, learner lock, model slot và event stream; PostgreSQL giữ turn/outbox và lịch sử để phục hồi. Đây là phần đã triển khai và kiểm thử local, không chỉ refactor.
>
> Phần AI đã có pipeline, SSE, citations và adapter Ollama. Tuy nhiên provider đang disabled; em chưa báo cáo model thật đã chạy hoặc chất lượng AI đã được nghiệm thu. Nội dung hiện tại vẫn là minh họa, chưa đủ ngân hàng chuyên môn cho toàn bộ học phần.
>
> Em đã có báo cáo kiểm thử tài khoản, quyền, điều phối và browser. Việc tiếp theo là chốt DB tài liệu và quy trình duyệt/phát hành với anh, rồi nối nguồn được phép và kiểm chứng model thật trước khi mở staging hoặc đo tải.

## 12. Tài liệu mở khi cần giải thích sâu

- [Kiến trúc Alpha ban đầu](architecture.md) và [kiến trúc Phase 1 hiện tại](../phase1/architecture.md).
- [Ma trận 60 API](../phase1/api-matrix.md).
- [Đăng nhập và bằng chứng kiểm thử ngày 10/11](../phase1/password-login.md).
- [Báo cáo queue, gateway, fault và giới hạn ngày 06/11](../phase1/yhdp-verification.md).
- [Đồng bộ contract frontend/backend](../testing/frontend-backend-contract-fix.md).
- [Hướng dẫn chạy và smoke ngày 12/11](../../README-RUN-LOCAL.md).
- [Thiết kế DB tài liệu đang chờ chốt](../phase1/document-db-design-proposal.md).

Các lời thoại có thể đọc trực tiếp. Khi báo cáo, ưu tiên kết quả nghiệp vụ, một luồng transaction và giới hạn AI; chỉ mở chi tiết bảng/thuật toán khi được hỏi. Không cần đọc toàn bộ tên endpoint hoặc số lượng test.
