# Kịch bản trình bày kiến trúc backend AI Tutor / DocPrep

**Buổi trình bày dự kiến:** 27/10/2026.\
**Thời lượng:** khoảng 10–12 phút, gồm 2 phút demo; phần hỏi đáp tính riêng.\
**Người nghe giả định:** mentor hoặc team kỹ thuật. Lời thoại dùng cách xưng “em”; có thể đổi thành “tôi” theo buổi báo cáo.

Tài liệu dùng cùng [thiết kế kiến trúc](architecture.md), [báo cáo kiểm thử](verification.md) và [hướng dẫn chạy](../../README.md). Đây là kịch bản nói dựa trên trạng thái đã ghi nhận trong repo; số liệu kiểm thử được dẫn từ báo cáo ngày 26/10/2026, không phải một lần chạy mới cho buổi trình bày.

## 1. Thông điệp cần người nghe nhớ

> Backend dùng kiến trúc một ứng dụng FastAPI chia module. PostgreSQL giữ dữ liệu chính thức; service và engine xử lý nghiệp vụ học/thi/ôn, còn gateway cô lập phần AI. Alpha hiện chạy local với database thật và AI kịch bản; giai đoạn pilot sẽ bổ sung nguồn nội dung được duyệt, AI thật và hạ tầng vận hành.

Khi tập, ưu tiên nắm ba điều: **vì sao chọn kiến trúc này, một yêu cầu đi qua các lớp thế nào, và dữ liệu được bảo vệ ra sao**. Tên thư viện và số lượng bảng là thông tin bổ trợ.

## 2. Phân bổ thời gian

| Thời điểm | Nội dung | Màn hình/tài liệu |
|---|---|---|
| 0:00–0:30 | Bài toán và phạm vi | Tiêu đề tài liệu kiến trúc |
| 0:30–1:30 | Lựa chọn kiến trúc | `architecture.md`, mục 1 |
| 1:30–2:20 | Sơ đồ tổng thể | Mục 3.1 |
| 2:20–3:40 | Phân lớp backend | Mục 4 |
| 3:40–5:00 | Dữ liệu và luồng trả lời câu hỏi | Mục 5 và 6.2 |
| 5:00–6:00 | Luồng thi thử | Mục 6.3 |
| 6:00–7:30 | Pipeline gia sư | Mục 7.1 |
| 7:30–8:30 | Quyền dữ liệu và bằng chứng kiểm thử | Mục 9, sau đó `verification.md` |
| 8:30–9:00 | Hướng lên pilot | Mục 10 |
| 9:00–11:00 | Demo ngắn | Health, Swagger, ứng dụng |
| 11:00–11:30 | Chốt nội dung | Quay lại sơ đồ phân lớp |

Đây là mốc tập luyện, không phải thời lượng đã đo. Nếu cần giữ đúng 10 phút, rút demo còn 1 phút và chỉ nêu một nhóm số liệu kiểm thử.

## 3. Lời thoại chính

### 3.1. Mở đầu — 30 giây

**Thao tác:** mở tiêu đề `architecture.md`.

> Em xin trình bày kiến trúc backend của hệ thống AI Tutor/DocPrep. Backend cần phục vụ chu trình người học từ chọn học phần, học và trả lời câu hỏi, ôn thẻ, thi thử đến theo dõi tiến độ và hỏi gia sư có nguồn.
>
> Bản Alpha được phát triển trên frontend đã thiết kế và backend demo đã có. Mục tiêu của đợt này là tích hợp thành một hệ thống chạy local, lưu dữ liệu thật và kiểm tra các luồng chính. Phần sinh câu trả lời AI hiện dùng kịch bản cố định.

**Chuyển ý:** “Em bắt đầu từ lý do chọn cách tổ chức backend.”

### 3.2. Vì sao chọn modular monolith — 1 phút

**Thao tác:** chỉ vào phần “Mục tiêu và quyết định kiến trúc”.

> Em chọn modular monolith, tức một ứng dụng backend được triển khai chung, nhưng chia bên trong thành các module nghiệp vụ như tài khoản, học tập, ôn thẻ, thi thử và hội thoại.
>
> Có ba lý do. Thứ nhất, team hiện nhỏ và cần tận dụng backend demo đã có. Thứ hai, nhiều thao tác cần cập nhật dữ liệu cùng nhau; ví dụ một câu trả lời có thể làm thay đổi kết quả học, mức năng lực và thẻ ôn. Thứ ba, phân module giúp kiểm thử và sửa từng phần trong khi cách chạy local vẫn gọn.
>
> Stack hiện tại là Python và FastAPI, PostgreSQL cho dữ liệu, psycopg cho truy vấn và connection pool, Alembic cho migration. Pydantic mô tả dữ liệu vào ra; OpenAPI là hợp đồng để frontend và backend đối chiếu.

**Điểm cần hiểu:** modular monolith mô tả cách tổ chức ứng dụng. Nó không có nghĩa hệ thống chỉ được chạy một process mãi mãi.

### 3.3. Sơ đồ tổng thể — 50 giây

**Thao tác:** trỏ theo đường đi từ trình duyệt → Vite → FastAPI → PostgreSQL.

> Trên local, trình duyệt mở frontend qua Vite ở cổng 5190. Frontend gọi đường dẫn `/api/v1`. Vite chuyển tiếp và bỏ phần `/api`, nên backend ở cổng 8000 nhận `/v1`.
>
> Backend xử lý yêu cầu rồi đọc ghi PostgreSQL. Database chạy trong Docker, được đưa ra cổng 15433 trên máy. Named volume giữ dữ liệu qua các lần tạo lại container.
>
> Có hai database là `alphav1` cho ứng dụng và `alphav1_test` cho kiểm thử, vì bộ test có thao tác dựng lại schema. Hai database này vẫn cùng nằm trong một container local.

**Chuyển ý:** “Bên trong FastAPI, em tách trách nhiệm theo các lớp sau.”

### 3.4. Phân lớp backend — 1 phút 20 giây

**Thao tác:** mở sơ đồ mục 4; lần lượt chỉ API, service, engine và repository.

> Lớp API tiếp nhận request, kiểm tra cấu trúc dữ liệu, xác thực, role và consent. Đây là nơi gắn giao thức HTTP với nghiệp vụ.
>
> Lớp service điều phối một use case. Ví dụ khi người học trả lời câu hỏi, service lấy nội dung đã được phép phục vụ, ghi kết quả, gọi thuật toán cập nhật năng lực và tạo thẻ nếu cần.
>
> Engine giữ các quy tắc tính toán như Elo, ưu tiên học và lịch ôn FSRS. Phần này được tách để kiểm thử mà không phụ thuộc vào màn hình hay cách gọi HTTP.
>
> Repository chứa SQL, cách lấy bản ghi và khóa dữ liệu khi cần. Còn pipeline hội thoại và model gateway phụ trách xử lý câu hỏi, nguồn và việc sinh nội dung.
>
> Lợi ích là mỗi lớp có trách nhiệm rõ. Thay provider AI chủ yếu tác động tới gateway và cấu hình; thay cách lưu dữ liệu được khoanh ở repository, đồng thời vẫn phải giữ contract API.

**Tránh nhầm:** các ô trong sơ đồ là module trong cùng backend; không phải mỗi ô là một server hay container riêng.

### 3.5. Dữ liệu và ví dụ một câu trả lời — 1 phút 20 giây

**Thao tác:** mở bảng miền dữ liệu mục 5.1; sau đó chỉ mục 6.2.

> Em chia dữ liệu thành các nhóm: danh tính và consent; nội dung và nguồn; kết quả học và lịch ôn; bài thi; hội thoại; nhật ký và dữ liệu chống ghi lặp. PostgreSQL là nơi giữ trạng thái chính thức của những nhóm này.
>
> Ví dụ người học trả lời sai một câu trong unit. Request đi qua kiểm tra quyền, rồi service ghi đáp án, cập nhật năng lực và tạo thẻ ôn nếu chưa có. Những thay đổi liên quan được xử lý trong transaction trước khi báo thành công cho frontend.
>
> Để xử lý việc mạng chậm khiến client gửi lại, các mutation được hỗ trợ sử dụng Idempotency-Key. Với cùng người dùng, route và key, backend trả lại kết quả đã lưu. Database còn có các ràng buộc chống trùng ở những bản ghi nghiệp vụ tương ứng.
>
> Nội dung và câu hỏi có phiên bản. Lượt thi và bộ luyện giữ phiên bản đã phục vụ để việc sửa ngân hàng câu hỏi về sau không làm thay đổi cách chấm lượt cũ.

**Nếu được hỏi sâu:** cùng key hiện chưa được so sánh bằng hash payload; client phải giữ nguyên payload khi retry. Thẻ được giới hạn theo người học/câu hỏi, không phải mỗi lần trả lời sai đều tạo một thẻ mới.

### 3.6. Luồng thi thử — 1 phút

**Thao tác:** mở sequence diagram mục 6.3, trỏ theo ba bước start → autosave → submit.

> Khi bắt đầu thi, backend tạo hoặc trả lại lượt đang mở, cố định thứ tự câu, phương án, phiên bản nội dung và deadline. Frontend hiển thị thời gian còn lại theo thông tin server.
>
> Mỗi lần chọn đáp án, frontend gửi autosave. Backend kiểm tra chủ sở hữu lượt thi, câu thuộc đề và trạng thái deadline trước khi ghi. Khi nộp, frontend chờ các đáp án được xác nhận lưu; backend chấm, lưu summary và đóng lượt. Nộp lặp sẽ nhận lại kết quả đã lưu.
>
> Có một giới hạn cần nói rõ: việc xử lý lượt hết hạn hiện được thực hiện khi các API liên quan được gọi. Bản Alpha chưa có scheduler độc lập tự quét mọi deadline khi người học không gửi request.

**Chuyển ý:** “Tiếp theo là pipeline gia sư, phần dễ bị nhầm với một chatbot gọi model trực tiếp.”

### 3.7. Pipeline gia sư — 1 phút 30 giây

**Thao tác:** mở sơ đồ mục 7.1, chỉ từng bước từ trên xuống.

> Câu hỏi trước hết đi qua bộ quy tắc nhận diện yêu cầu tư vấn ca bệnh cụ thể. Với câu hỏi học tập, hệ thống chuẩn hóa và tra glossary; thuật ngữ mơ hồ có thể dẫn tới yêu cầu làm rõ.
>
> Sau đó hệ thống tìm passage trong PostgreSQL bằng full-text và cách xếp hạng theo từ khóa. Hiện chưa có tìm kiếm bằng embedding/vector. Nếu không đủ nguồn phù hợp, hệ thống trả trạng thái thiếu bằng chứng.
>
> Nếu có nguồn, pipeline chuyển ngữ cảnh qua gateway rồi kiểm tra kết quả: passage có được truy xuất hay không, quote có xuất hiện trong nguồn và số liệu có khớp nguồn hay không. Các kiểm tra này chưa thay thế thẩm định ý nghĩa y khoa.
>
> Trong Alpha, gateway trả nội dung kịch bản, không gọi mô hình bên ngoài. Nhưng truy xuất, lưu hội thoại, mở citations và truyền phản hồi qua backend vẫn là luồng thật.
>
> SSE gửi các event trạng thái và kết quả; `final` báo lượt xử lý hoàn tất. Với chat và giải thích, backend nhả connection database trong lúc chờ gateway, rồi mượn connection để lưu kết quả trước khi phát câu trả lời cuối.

**Câu cần nói dứt khoát:** “Em đang chứng minh tích hợp pipeline, chưa báo cáo chất lượng một mô hình AI thật.”

### 3.8. Quyền dữ liệu và kiểm thử — 1 phút

**Thao tác:** chỉ mục 9.1, rồi mở bảng kết quả trong `verification.md`.

> Backend kiểm tra cả role lẫn chủ sở hữu dữ liệu. Có role learner không đồng nghĩa được đọc attempt hay hội thoại của learner khác. Consent dịch vụ là một gate riêng; consent nghiên cứu là tùy chọn.
>
> Token hiện là opaque token, lưu hash ở database; client đang giữ token trong localStorage. Dashboard có chính sách ẩn nhóm dưới 10 người. Những phần như chính sách session khi mở pilot và chống suy ngược qua nhiều bộ lọc vẫn cần đánh giá tiếp.
>
> Theo báo cáo kiểm thử ngày 26/10, regression backend có 1.121 test đạt và 95 trường hợp skip theo điều kiện của bộ test. Bộ scripted sau chỉnh sửa cuối có 14 test đạt; browser smoke có 6 trường hợp trên hai viewport. Ngoài ra đã kiểm tra tạo lại container và phục hồi backup, đối chiếu dữ liệu của 44 bảng.
>
> Các kết quả này hỗ trợ kết luận demo tích hợp local hoạt động trong phạm vi đã kiểm tra. Chưa có load test để cam kết số người dùng đồng thời.

### 3.9. Hướng mở rộng — 30 giây

**Thao tác:** mở sơ đồ đề xuất ở mục 10.

> Để chuyển lên pilot, em ưu tiên nguồn nội dung có quyền sử dụng và thẩm định; sau đó là provider AI thật cùng bộ đánh giá, staging HTTPS và các yêu cầu vận hành như log, metrics, backup tự động và phục hồi.
>
> Khi chạy nhiều process hoặc instance, cần điều phối giới hạn model và tổng connection database. Những thành phần bổ sung trong sơ đồ này là phương án đề xuất, chưa phải hạ tầng đã triển khai.

## 4. Demo 2 phút đã chuẩn bị trước

Chuẩn bị sẵn các tab và đăng nhập learner bằng form thật. Không phụ thuộc vào việc tài khoản cũ sẽ hiện lại onboarding hoặc unit mới. Hoàn tất lượt thi đang mở trước khi demo chat, vì frontend hiện chặn chat trong lúc thi.

| Thời lượng | Thao tác | Lời nói gợi ý và bằng chứng |
|---|---|---|
| 20 giây | Mở `http://127.0.0.1:8000/health` | “Mode real cho biết backend chạy với database; provider scripted cho biết phần sinh nội dung dùng kịch bản.” Đây là thông tin runtime, không phải phép kiểm tra mọi dependency. |
| 20 giây | Mở `http://127.0.0.1:8000/docs` | “API được nhóm theo nghiệp vụ và có schema vào/ra để frontend tích hợp.” Chỉ nhanh nhóm auth, units và attempts; không cần gọi lần lượt mọi endpoint. |
| 60 giây | Mở `/hoi-dap`, hỏi `Tỷ lệ hiện mắc là gì?`, rồi mở citation | “Request đi qua pipeline; nguồn mở ra là passage backend trả về. Nội dung đang là kịch bản trên dữ liệu minh họa.” |
| 20 giây | Đóng nguồn, reload hội thoại | “Lịch sử được tải lại từ server.” Có thể chỉ nhanh request `/api/v1/chat/...` trong Network nếu DevTools đã chuẩn bị. |

Reload và mở nguồn là minh họa ngắn cho người nghe; bằng chứng persistence còn dựa vào kiểm thử/API đã ghi trong báo cáo. Không dùng riêng một thao tác reload để kết luận toàn bộ cơ chế lưu trữ đã được kiểm chứng.

**Nếu demo phát sinh lỗi:**

> “Phần demo live đang gặp vấn đề môi trường. Em chuyển sang ảnh và kết quả kiểm thử đã chuẩn bị để tiếp tục giải thích luồng; em sẽ kiểm tra lại nguyên nhân sau buổi báo cáo.”

Chuyển sang ảnh trong báo cáo hoặc sơ đồ, dành tối đa khoảng 30 giây cho thao tác khắc phục ngay tại buổi trình bày. Không đổi sang demo localStorage rồi giới thiệu như backend thật.

### Lời kết — 30 giây

> Kiến trúc hiện tập trung vào ba điểm: chia rõ trách nhiệm trong backend, giữ dữ liệu và quy tắc học tập tại server, và cô lập phần sinh nội dung AI qua gateway.
>
> Alpha đã có luồng tích hợp local và bằng chứng kiểm thử cho các chức năng chính. Bước tiếp theo cần ưu tiên là chất lượng nguồn/AI, môi trường staging và các yêu cầu vận hành trước khi mở pilot. Em xin nhận góp ý về các ranh giới module và thứ tự ưu tiên này.

## 5. Câu hỏi có thể được hỏi

### 1. Vì sao chưa dùng microservices?

> Với phạm vi Alpha và team nhỏ, triển khai chung giúp giảm công việc vận hành và giữ các cập nhật liên quan trong transaction. Các module đã có ranh giới logic để tiếp tục phát triển. Khi có nhu cầu scale hoặc vòng đời triển khai độc lập được chứng minh, em sẽ xem xét tách phần phù hợp.

### 2. Vì sao chọn FastAPI và PostgreSQL?

> Đây là stack của backend demo có thể tái sử dụng. FastAPI/Pydantic hỗ trợ schema và hợp đồng API; PostgreSQL phù hợp dữ liệu quan hệ, transaction, khóa và các ràng buộc của bài thi, đáp án và lịch ôn. Lựa chọn được gắn với yêu cầu của hệ thống, chưa có kết luận benchmark rằng stack này nhanh nhất.

### 3. Phần nào đã có từ demo, phần nào được bổ sung trong Alpha?

> Demo đã có kiến trúc FastAPI, migration và nhiều nghiệp vụ học/thi/ôn. Đợt Alpha tiếp nhận backend vào repo frontend, cấu hình database/môi trường local, bổ sung gateway scripted, seed phục vụ trình diễn, kiểm thử browser, script vận hành và tài liệu đối chiếu. Em không coi toàn bộ backend là phần viết mới từ đầu.

### 4. Các service trong sơ đồ có phải là các server riêng?

> Hiện là các module trong cùng ứng dụng FastAPI. Sơ đồ phân lớp mô tả trách nhiệm; sơ đồ triển khai mới cho biết tiến trình và hạ tầng chạy thực tế.

### 5. Hệ thống đang dùng JWT hay loại token nào?

> Hiện dùng opaque token. Server xác thực bằng bản ghi hash của token, thời hạn và trạng thái thu hồi. Access/refresh token của một phiên có family để phục vụ refresh rotation và logout. Client hiện lưu token trong localStorage; chính sách session cho pilot còn cần đánh giá tiếp.

### 6. Gửi hai lần có bị tính điểm hoặc tạo hai thẻ không?

> Các mutation được hỗ trợ dùng key để trả lại kết quả đã lưu; khóa và unique constraint bổ sung bảo vệ ở database. Cần phân biệt từng endpoint: autosave dùng upsert, submit trả kết quả đã lưu, còn helper idempotency hiện chưa so sánh hash payload. Client phải retry cùng payload và key.

### 7. Đổi câu hỏi sau này có làm đổi điểm bài thi cũ không?

> Lượt thi giữ snapshot thứ tự câu, phương án và map phiên bản câu hỏi đã phục vụ. Việc sửa nội dung phải tạo version mới; quá trình xem lại/chấm lượt cũ dùng phiên bản đã giữ theo thiết kế.

### 8. Nếu thoát trình duyệt rồi hết giờ thì sao?

> Deadline vẫn do server giữ và không được kéo dài theo đồng hồ client. Khi API liên quan kiểm tra lượt đã hết hạn, backend xử lý đóng/chấm theo trạng thái đó. Hiện chưa có scheduler độc lập để bảo đảm mọi lượt tự được quét ngay đúng thời điểm khi không có request.

### 9. AI hiện có thật không, và đã có RAG chưa?

> Phần sinh câu trả lời đang dùng kịch bản, không gọi mô hình bên ngoài. Pipeline đã có truy xuất passage theo full-text, kiểm tra nguồn, citations và lưu lịch sử. Có thể mô tả là pipeline truy xuất nguồn được chuẩn bị cho AI; chưa nên giới thiệu như RAG đã được đánh giá với mô hình thật.

### 10. Có trích dẫn thì đã chắc chắn trả lời đúng chưa?

> Chưa thể kết luận như vậy. Kiểm tra hiện tại xác minh passage, quote và số liệu theo các quy tắc đã có; nó không thay thế đánh giá ý nghĩa y khoa. Cần nội dung được thẩm định và bộ đánh giá chuyên môn trước pilot.

### 11. Hệ thống chịu được bao nhiêu người dùng đồng thời?

> Chưa có load test để cam kết con số. Cấu hình hiện có pool tối đa 10 connection, 4 model turn đồng thời và 20 turn chờ trên mỗi process. Đây là giới hạn cấu hình, không phải số người dùng hệ thống có thể phục vụ. Cần workload và đo đạc trên môi trường dự kiến.

### 12. Dashboard đã bảo vệ dữ liệu và hệ thống đã sẵn sàng production chưa?

> Đã có kiểm tra role và ẩn nhóm dưới 10 ở các luồng báo cáo liên quan, nhưng còn phải đánh giá khả năng suy ngược qua nhiều tổ hợp bộ lọc. Alpha hiện phục vụ demo local. Các việc trước pilot gồm nguồn/AI, HTTPS, privacy, quan sát, backup theo lịch, kiểm thử tải và phục hồi.

### Nếu chưa biết câu trả lời

> “Phần này em chưa có phép đo hoặc chưa kiểm tra đủ để kết luận. Hiện em xác nhận được …; phần còn lại em sẽ đối chiếu mã nguồn hoặc chạy thử rồi bổ sung.”

Điền điều đã biết vào chỗ trống, ví dụ giới hạn cấu hình hoặc hành vi một endpoint. Không chọn một con số ước lượng để trả lời như kết quả kiểm thử.

## 6. Chuẩn bị trước buổi trình bày

### Chạy môi trường trước, từ đúng thư mục

Bật Docker Desktop. Trong terminal thứ nhất:

```powershell
cd "D:\InternAIRC\AI_TuTor\ALPHAV1\Docprep_FE"
docker compose up -d --wait
powershell -ExecutionPolicy Bypass -File scripts/start-backend.ps1
```

Terminal thứ hai:

```powershell
cd "D:\InternAIRC\AI_TuTor\ALPHAV1\Docprep_FE"
npm.cmd run dev -- --strictPort
```

Nếu báo cổng đang được dùng, kiểm tra dịch vụ hiện có ở URL trước; nếu báo `ENOENT package.json`, kiểm tra terminal đã vào `Docprep_FE` hay chưa. Lệnh cài đặt lần đầu nằm trong README; nên xử lý cài đặt trước buổi báo cáo.

### Những thứ cần mở sẵn

- Preview `architecture.md` bằng `Ctrl+Shift+V`; thử trước việc chuyển đến các sơ đồ mục 3, 4, 6.3, 7 và 10.
- `verification.md`, health, Swagger và trang `/hoi-dap`.
- Learner đăng nhập bằng mã `DEMO-0001` qua form thật, không chọn “Dùng dữ liệu trải nghiệm”; đã hoàn thành consent và không có bài thi đang mở.
- Câu hỏi demo và một ảnh chat có nguồn/dashboard đã xem được trên máy. Link ảnh trong báo cáo trỏ vào artifact không được đưa lên Git; nếu dùng máy khác cần tạo lại hoặc mang ảnh dự phòng theo.
- Đồng hồ để tập ít nhất một lần với giọng nói bình thường. Không chạy toàn bộ regression hoặc reset dữ liệu trong phần demo.

## 7. Phiếu nhắc nhanh để đặt cạnh màn hình

| Chủ đề | Cụm cần nhớ |
|---|---|
| Kiến trúc | Một ứng dụng chia module; phù hợp team và transaction |
| Luồng request | Frontend → API → service → repository → PostgreSQL |
| Quy tắc | Engine tính học/ôn; gateway cô lập sinh nội dung AI |
| Dữ liệu | PostgreSQL là nguồn chính; có version, ownership và transaction |
| Retry | Cùng key/người dùng/route; giữ nguyên payload khi gửi lại |
| Thi | Snapshot đề, deadline server, autosave, submit lặp; đóng hết hạn hiện dựa request |
| AI | Pre-gate → glossary → retrieval → gateway → post-check → lưu → answer/final |
| Phạm vi | Database thật, AI scripted; dữ liệu minh họa |
| Kiểm thử | Báo cáo: 1.121 đạt/95 skip; scripted 14; browser 6; phục hồi 44 bảng |
| Tiếp theo | Nguồn và AI được đánh giá; staging HTTPS; vận hành và privacy |

### Bản nói rút gọn khi chỉ có khoảng 2 phút

> Backend AI Tutor hiện dùng modular monolith với FastAPI: triển khai chung một ứng dụng, bên trong tách module tài khoản, học, ôn, thi, hội thoại và báo cáo. Cách này phù hợp team nhỏ và giữ các cập nhật liên quan trong transaction.
>
> Request đi từ frontend qua API để kiểm tra dữ liệu và quyền, xuống service điều phối, rồi repository đọc ghi PostgreSQL. Engine giữ các quy tắc như Elo và lịch ôn FSRS. Database lưu trạng thái chính thức; lượt thi giữ phiên bản đề và deadline của server.
>
> Pipeline gia sư có bước kiểm tra câu hỏi, tra glossary, truy xuất passage, sinh nội dung qua gateway và kiểm tra nguồn trước khi lưu và trả kết quả qua SSE. Alpha hiện dùng gateway scripted; database và luồng lưu hội thoại là thật, còn chất lượng AI thật chưa được đánh giá.
>
> Bản local đã có bằng chứng kiểm thử cho các luồng chính và phục hồi dữ liệu. Để lên pilot, cần ưu tiên nguồn chuyên môn được duyệt, provider AI cùng bộ đánh giá, môi trường HTTPS và các yêu cầu vận hành, privacy và kiểm thử tải.
