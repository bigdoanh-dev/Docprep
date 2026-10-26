# Kế hoạch kiểm thử Mobile–Backend DocPrep

> **Alpha V1 local — 26/10/2026:** kết quả thực thi và phạm vi được nghiệm thu nằm ở [báo cáo Alpha](../alpha-v1/verification.md). CSV, bàn duyệt, AI thật và triển khai online không thuộc đợt này. Các ca đề xuất dưới đây không tự động được coi là đã PASS.

**Phiên bản:** 1.0  
**Ngày lập:** 25/10/2026  
**Đối tượng sử dụng:** Backend, frontend, QA, product  
**Phạm vi:** ứng dụng mobile DocPrep và các API learner/staff đang được frontend tiêu thụ  
**Tài liệu đối chiếu:** docs/handoffs/mobile-backend-handoff.md

> Đây là kế hoạch và bộ ca kiểm thử đề xuất cho backend dev/staging. Tài liệu không khẳng định API đã được triển khai. Trước khi chạy, đối chiếu OpenAPI và chốt các hành vi được đánh dấu “Cần chốt” trong tài liệu bàn giao. Không sử dụng tài khoản hoặc dữ liệu cá nhân thật.

## 1. Mục tiêu

Xác nhận frontend mobile và backend:

1. Dùng cùng schema, role, trạng thái, status code và quy tắc lỗi.
2. Hoàn thành được các luồng đăng nhập, đồng ý, học, luyện tập, ôn thẻ, thi và hỏi AI.
3. Không mất dữ liệu server đã xác nhận khi reload, retry hoặc mất mạng tạm thời.
4. Tính tiến độ nhất quán theo tài khoản và múi giờ Asia/Ho_Chi_Minh.
5. Bảo vệ dữ liệu learner/staff ở API, dashboard, export và log.
6. Hiển thị đúng loading, rỗng, lỗi, hết giờ và chưa hỗ trợ trên thiết bị mobile.

## 2. Cách sử dụng

- Chạy theo các gate ở mục 11. Gate 0–2 là điều kiện cho luồng learner cốt lõi; Gate 3–4 phụ thuộc việc bật AI, analytics và staff API.
- Ghi mỗi ca là PASS, FAIL, BLOCKED hoặc NOT RUN. Với FAIL, lưu môi trường, build, fixture, bước tái hiện, request ID và ảnh/video.
- Khi FE và OpenAPI khác nhau, ghi defect contract; không âm thầm bỏ field hoặc đổi nghĩa dữ liệu.
- Không dùng demo data để đánh dấu pass cho backend live. Kết quả demo phải được ghi riêng.
- Không chạy destructive test trên production. Chỉ smoke test an toàn với tài khoản QA được cấp phép.
- Chi tiết field/request/response nằm trong tài liệu bàn giao; tài liệu này tập trung vào kịch bản, bước và expected result.

## 3. Phạm vi

### 3.1 Trong phạm vi

- API routing qua /api/v1 ở FE và /v1 ở BE; Vite/Vercel proxy, CORS, JSON và SSE.
- Learner activation, staff login, access/refresh token, logout, role và consent.
- Hồ sơ, trang chủ, phiên hôm nay, module/unit, câu trả lời, practice set và spaced-repetition cards.
- Mock exam: start/resume, lưu câu, hết giờ, submit, result và review.
- AI chat: lịch sử, POST SSE, event stream, citations, hint/explain, rating, suggestion.
- Progress skills/rhythm: coverage, tỷ lệ, nhịp học, heatmap, ngày biên, null/zero.
- Staff API được FE tiêu thụ: dashboard, XLSX export, CSV import và report nội dung.
- Trạng thái UI mobile: loading, empty, partial data, lỗi mạng/HTTP, retry, thao tác chạm và responsive.
- Privacy: quyền truy cập, consent, export/delete theo semantics đã chốt, suppression và log redaction.

### 3.2 Tính năng chưa được xem là live bắt buộc

| Tính năng | Hiện trạng ghi nhận trong frontend | Cách kiểm thử |
| --- | --- | --- |
| Tạo practice set tự chọn ở PracticeHub | Nút live đang khóa | Có thể contract-test API nếu BE đã có; không tính nút disabled là lỗi. |
| Thư viện toàn bộ cards/search/filter | Client live hiện tải due cards; chưa xác nhận API library | Chỉ nghiệm thu due queue; thêm test khi API library được bật. |
| CSV import live | Có nhánh xử lý 501 | Khi chưa hỗ trợ, kiểm tra thông báo rõ và không phát mã giả. |
| Báo lỗi nội dung | Có nhánh xử lý 501 | Khi chưa hỗ trợ, UI không được giả báo gửi thành công. |
| Notification/read marker, streak/activity, study plan và một số preferences | Lưu local/demo | Không yêu cầu đồng bộ đa thiết bị; xác nhận dữ liệu demo không lẫn vào live. |
| Lecturer/review workspace | Chưa nối mobile route | Ngoài scope hiện tại. |

## 4. Tầng kiểm thử

| Tầng | Người thực hiện | Câu hỏi cần trả lời | Bằng chứng |
| --- | --- | --- | --- |
| Unit/component | FE/BE developer | Validation, parser, mapping, reducer và logic biên có đúng? | Báo cáo runner và test ID. |
| API contract | BE + QA | Method/path/auth/schema/status/error/idempotency có khớp OpenAPI và handoff? | Collection API đã version hóa, response đã khử dữ liệu nhạy cảm. |
| Integration | FE + BE | FE staging gọi đúng server; proxy, CORS, refresh, persistence và SSE chạy end-to-end? | Network trace, request ID, ảnh UI. |
| E2E mobile | QA | Người học hoàn thành tác vụ trên điện thoại, kể cả reload/lỗi? | Video/ảnh, fixture, bước tái hiện. |
| Security/privacy | BE/security + QA | Role, consent, suppression, export và log có lộ dữ liệu? | Access matrix, audit/log đã khử định danh. |
| Reliability/performance | BE/SRE | Retry, timeout, tải đồng thời, SSE disconnect ảnh hưởng ra sao? | Báo cáo tải, p95/p99, lỗi, resource usage. |

## 5. Môi trường và dữ liệu

### 5.1 Môi trường

| Môi trường | Mục tiêu | Quy tắc |
| --- | --- | --- |
| Local | Phát triển contract/debug | FE chạy tại 127.0.0.1:5190. Đặt BACKEND_URL trong .env.local, ví dụ http://127.0.0.1:8000. Browser gọi /api/v1/...; Vite proxy thành BACKEND_URL + /v1/.... |
| Staging | Tích hợp/QA | FE và BE cùng release contract; dữ liệu tổng hợp; có correlation ID; SSE không buffer. |
| Production | Smoke sau deploy | Không brute-force, import/xóa dữ liệu, hoặc tạo attempt phá hủy; chỉ dùng tài khoản QA được cấp phép. |

Đầu mỗi lượt chạy, xác nhận FE URL, BE URL, commit/build, API schema version, mode live, timezone, fixture, role, feature flags. Gọi một GET protected bằng token QA: response phải là JSON đúng schema, không phải trang HTML SPA. Không ghi access/refresh token vào ticket.

### 5.2 Tài khoản/fixture tổng hợp

| Mã fixture | Trạng thái | Dữ liệu cần có | Dùng cho |
| --- | --- | --- | --- |
| L-FRESH | Learner mới | Activation code hợp lệ, chưa consent, chưa focus module | Login lần đầu, consent gate. |
| L-READY | Learner hoạt động | Service consent hợp lệ, research false, có focus | Home, học, AI, progress. |
| L-PROGRESS | Learner có lịch sử | Unit dở, response đã lưu, due/suspended cards, attempt đã nộp, activity | Resume, analytics, due queue, results. |
| L-EMPTY | Learner chưa có hoạt động | Hồ sơ hợp lệ, không session/attempt/card/activity | Empty state, null/zero. |
| L-EXPIRED | Access hết hạn | Refresh token hợp lệ hoặc revoked theo case | Refresh/retry. |
| L-REVOKED | Refresh hết hiệu lực | Refresh token đã revoke | Logout an toàn. |
| S-ADMIN | Staff có quyền | Dashboard tổng hợp gồm nhóm đủ ngưỡng và nhóm bị suppression | Dashboard, import/export. |
| S-READONLY | Staff chỉ xem | Role read-only theo policy | Mutation bị từ chối. |
| R-OTHER | Role ngoài mobile scope | Ví dụ reviewer hoặc role không được FE hỗ trợ | Deny-by-default, chống truy cập trái quyền. |

Pseudonym, câu hỏi, citation, tổ chức, file CSV và activation code phải là dữ liệu giả. Chuẩn bị trạng thái chưa trả lời/đúng/sai/hoàn thành, card chưa đến hạn/đến hạn/suspended, attempt mở/đã nộp/hết hạn, nhóm nhỏ bị suppression và timestamp sát nửa đêm Việt Nam.

## 6. Quy tắc đánh giá chung

1. **Idempotency:** retry cùng Idempotency-Key và cùng payload chỉ tạo một kết quả nghiệp vụ. Cùng key nhưng payload khác phải bị xử lý theo policy đã chốt, không âm thầm ghi đè.
2. **Answer bài thi:** PUT cùng attempt/question là upsert idempotent; không tạo response hay event chấm điểm trùng.
3. **Nguồn sự thật:** sau khi server xác nhận, reload/thiết bị khác phải thấy trạng thái đã lưu; local cache không ghi đè server.
4. **Thời gian:** ngày nghiệp vụ dùng Asia/Ho_Chi_Minh; timestamp ISO-8601 có timezone; kiểm tra ngày bằng clock/fixture chủ động.
5. **null và 0:** null là chưa có/không áp dụng; 0 là giá trị thật. Không đổi null thành 0%, không chia mẫu số 0.
6. **Bảo mật:** mọi route protected kiểm tra auth và role ở server; ẩn nút trên UI không thay thế authorize API.
7. **Lỗi:** xác nhận HTTP status và error.code; message_vi chỉ hiển thị cho người dùng, không làm logic máy.
8. **Bằng chứng:** request/response phải xóa Authorization, cookie, mật khẩu, activation code và thông tin định danh; giữ request/correlation ID.

## 7. Ca kiểm thử API và tích hợp

Ưu tiên: P0 chặn phát hành luồng cốt lõi; P1 cần pass trước khi bật feature; P2 là regression bổ sung.

### 7.1 Kết nối, proxy và error contract

| ID | Ưu tiên | Tiền điều kiện và thao tác | Kết quả mong đợi |
| --- | --- | --- | --- |
| NET-001 | P0 | FE staging gọi GET /api/v1/me | Request tới đúng /v1/me, trả JSON đúng schema; không trả HTML SPA/mock. |
| NET-002 | P0 | Backend ngừng phản hồi; mở màn cần API và retry | UI báo lỗi kết nối tiếng Việt, không treo vô hạn hoặc giả báo thành công. |
| NET-003 | P0 | Gửi cross-origin request có Authorization, Content-Type, Idempotency-Key | Preflight cho phép đúng origin/header/method; không dùng wildcard credentials. |
| NET-004 | P0 | Gửi POST SSE chat qua proxy | Content-Type text/event-stream; proxy không buffer; event tới browser khi server phát. |
| NET-005 | P0 | Gọi API trả error envelope | Client xử lý {error:{code,message_vi}}; không crash khi body rỗng hoặc không JSON. |
| NET-006 | P1 | Gọi today practice không có set; gọi reports/import chưa hỗ trợ | 404/501 theo contract được phân biệt; không biến thành 0 câu hoặc success giả. |
| NET-007 | P0 | Nhiều protected request cùng gặp 401 token_expired | Refresh được serialize; request gốc retry tối đa một lần; không loop/nhân đôi mutation. |

### 7.2 Identity, session, consent và profile

| ID | Ưu tiên | Tiền điều kiện và thao tác | Kết quả mong đợi |
| --- | --- | --- | --- |
| AUTH-001 | P0 | L-FRESH activate bằng code hợp lệ | Trả token pair, expires_in, role và consent state; không lộ secret ngoài contract. |
| AUTH-002 | P0 | Activate với code sai, hết hạn, đã thu hồi | Trả 4xx/error code ổn định; không tạo phiên; message không tiết lộ code nào đang tồn tại. |
| AUTH-003 | P0 | L-FRESH login, mở protected route khi chưa consent | Bắt buộc tới consent; không render dữ liệu học trước khi service consent hợp lệ. |
| AUTH-004 | P0 | Consent version đổi v1 sang v2 khi màn hình đang mở; submit v1 | Trả 409; client tải text/version mới, xóa lựa chọn cũ và yêu cầu người dùng chọn lại. |
| AUTH-005 | P0 | L-READY login và GET /v1/me | Hồ sơ, audience, focus module, consent thuộc đúng account. |
| AUTH-006 | P0 | Access hết hạn, refresh còn hiệu lực; gọi protected API | Refresh một lần, lưu token mới, retry request gốc một lần; mutation không bị ghi hai lần. |
| AUTH-007 | P0 | Refresh token đã rotate/revoke | Refresh bị từ chối thì xóa session phù hợp và về login; không retry vô hạn. |
| AUTH-008 | P0 | POST /v1/auth/logout rồi gọi protected API bằng token cũ | Server revoke theo policy; client xóa token kể cả logout request lỗi; phiên cũ không còn dùng được. |
| AUTH-009 | P0 | Staff login S-ADMIN và thử role R-OTHER | Role được phép mới vào app/API; role không hỗ trợ bị từ chối theo contract. |
| AUTH-010 | P0 | Dùng learner token gọi admin overview/import | Server trả 403/status đã chốt; quyền được kiểm tra ở backend. |
| CONSENT-001 | P0 | GET /v1/consent/current; submit service=true, research=false | Lưu đúng version/lựa chọn/timestamp; service bắt buộc, research độc lập. |
| CONSENT-002 | P1 | User có cả hai loại consent; rút research | Chỉ research bị rút; service vẫn hoạt động; audit ghi đúng event. |
| CONSENT-003 | P1 | User rút service consent | Hành vi access/data đúng semantics product đã chốt; app về gate; không tự giả định dữ liệu đã xóa. |
| PROFILE-001 | P1 | PATCH profile hợp lệ rồi GET /me | Field gửi được lưu; field không gửi giữ nguyên; không sửa user khác. |
| PROFILE-002 | P1 | Gửi display name >80 ký tự, focus rỗng, target ngoài enum, count vượt giới hạn | Server validate độc lập FE, trả lỗi rõ; không lưu một phần. |
| DATA-001 | P1 | L-READY gọi GET /v1/me/data và export | Chỉ xuất dữ liệu chính chủ, file parse được, không chứa token/secret. |
| DATA-002 | P1 | Chạy DELETE /v1/me với fixture đã được phép | Kết quả đúng semantics đã chốt: request hay xóa ngay; audit/phiên/UI nhất quán; không báo thành công giả. |

### 7.3 Home, session, modules và unit

| ID | Ưu tiên | Tiền điều kiện và thao tác | Kết quả mong đợi |
| --- | --- | --- | --- |
| HOME-001 | P0 | L-READY tải /v1/home và /v1/session/today | Name, due count, suggestion, recent, steps đúng account; cùng local_date. |
| HOME-002 | P1 | L-EMPTY tải home/session | Empty/zero state đúng; không sinh step hoặc hoạt động mẫu. |
| HOME-003 | P1 | Session có 0, 1, 3 step với trạng thái done khác nhau; hoàn tất và refresh | Điều phối theo step chưa hoàn tất server trả; không tạo/đảo step. |
| MOD-001 | P1 | Tải modules/detail với status/group/level/q | Query/filter cho kết quả đúng; coming_soon/no-unit không cộng completion giả. |
| UNIT-001 | P0 | Unit có content, quiz, remediation; GET next, đọc rồi advance | Item/citation/position đúng; advance không skip hoặc nhân đôi. |
| UNIT-002 | P0 | Gửi đáp án đúng ở quiz chưa làm | Feedback đúng gồm correct key, explanation, rationales, citations; câu chưa trả lời không lộ đáp án. |
| UNIT-003 | P0 | Gửi đáp án sai rồi reload unit | Feedback/remediation đúng; chosen và feedback được restore từ server. |
| UNIT-004 | P0 | Gửi response với key K; làm mất response; retry key K/payload cũ | Chấm một lần, side effect/card một lần; retry nhận feedback đã lưu. |
| UNIT-005 | P1 | Gửi cùng key nhưng lựa chọn khác hoặc advance sai item id | Server từ chối conflict/invalid state; kết quả đã lưu không bị đổi. |
| UNIT-006 | P1 | Hoàn tất item cuối khi học trong session và học độc lập | Session quay về flow coordinator; học độc lập hiện kết thúc; null/done không gây crash. |
| UNIT-007 | P1 | Learner B dùng ID unit của learner A | 403/404 theo policy; không lộ câu, feedback, nội dung hoặc tiến độ. |

### 7.4 Practice sets

| ID | Ưu tiên | Tiền điều kiện và thao tác | Kết quả mong đợi |
| --- | --- | --- | --- |
| PRACT-001 | P1 | Có session practice; GET /v1/session/today/practice | Set/order ổn định; nếu không có set thì 404 đúng code và FE về /phien. |
| PRACT-002 | P1 | Trả lời một câu rồi reload và GET set | answered/chosen/feedback khớp server; mở câu đầu tiên chưa có feedback. |
| PRACT-003 | P1 | Gửi response với Idempotency-Key rồi retry cùng key | Không nhân đôi đáp án, mastery hoặc card; response ổn định. |
| PRACT-004 | P1 | Trả lời câu cuối; gọi /complete hai lần | Summary không đổi; completion side effect một lần; không sinh set trùng. |
| PRACT-005 | P1 | PracticeHub live button đang disabled | Contract-test API độc lập nếu được cấp phép; không coi UI live flow là pass trước khi feature được bật. |

### 7.5 Cards và spaced repetition

| ID | Ưu tiên | Tiền điều kiện và thao tác | Kết quả mong đợi |
| --- | --- | --- | --- |
| CARD-001 | P0 | L-PROGRESS có due cards; tải /v1/decks và /v1/cards/due có/không limit | Chỉ card được phép; count/limit khớp step; không lộ account khác. |
| CARD-002 | P0 | Review card và gửi từng rating 1–4 | Ghi một review; due_at/remaining_due do server tính; mapping rating đúng. |
| CARD-003 | P0 | Review timeout; retry cùng Idempotency-Key | Không tăng review/reschedule hai lần; trả lịch đã lưu. |
| CARD-004 | P1 | Card chưa due hoặc suspended; thử review | Backend xử lý theo policy; không làm state mâu thuẫn với due/suspended. |
| CARD-005 | P1 | PATCH suspended true rồi false; GET lại | State bền vững/idempotent và due queue cập nhật đúng. |
| CARD-006 | P1 | Session có card step count N | FE chỉ lấy N card; remaining_due/session nhất quán. |

### 7.6 Mock exam và attempt

| ID | Ưu tiên | Tiền điều kiện và thao tác | Kết quả mong đợi |
| --- | --- | --- | --- |
| EXAM-001 | P0 | Có exam chưa làm; POST attempts với body rỗng | Tạo attempt đúng user; deadline từ server; order câu ổn định. |
| EXAM-002 | P0 | Attempt đang mở; gọi start lại hoặc refresh | Trả attempt mở theo contract; không tạo attempt trùng. |
| EXAM-003 | P0 | PUT answer rồi GET attempt | Answer map và selected/flag state lưu bền vững. |
| EXAM-004 | P0 | PUT answer bị timeout; retry cùng attempt/question/payload | Upsert idempotent; không tạo response trùng; answer không mất. |
| EXAM-005 | P0 | Có answer đang pending local; bấm submit | UI chờ server xác nhận answer trước khi submit; attempt chỉ đóng sau server response. |
| EXAM-006 | P0 | Submit hai lần hoặc reload sau submit | Result idempotent; không chấm/tạo kết quả trùng. |
| EXAM-007 | P0 | Client clock lệch; để server deadline hết | Server quyết định auto-submit/closed; client resync, không kéo dài giờ. |
| EXAM-008 | P0 | Attempt đã đóng; PUT answer hoặc submit tiếp | Nhận attempt_closed/status đã chốt; result/answer không thay đổi. |
| EXAM-009 | P1 | Attempt cũ có answer; start fresh=true | Attempt cũ xử lý theo policy chốt trước attempt mới; không mất answer đã xác nhận. |
| EXAM-010 | P1 | Result có đúng/sai/bỏ trống; fixture total=0 | Tỷ lệ đúng; blank khác wrong; total 0 là no-data; review không lộ đáp án trước submit. |
| EXAM-011 | P1 | Learner B dùng attempt ID của learner A | Backend chặn IDOR; không lộ đề, answer, score, review. |

### 7.7 AI, citations và SSE

| ID | Ưu tiên | Tiền điều kiện và thao tác | Kết quả mong đợi |
| --- | --- | --- | --- |
| AI-001 | P0 | L-READY không có attempt mở; tạo chat rồi gửi POST SSE | Event status/step/answer/final theo contract; UI cập nhật dần. |
| AI-002 | P0 | Fixture answered có citations | Marker [n] khớp citations[n]; final.state answered; citation mở được. |
| AI-003 | P0 | Fixture insufficient evidence; hỏi ngoài corpus | Có notice và final state phù hợp; không tạo citation/answer giả. |
| AI-004 | P0 | Fixture declined và needs_clarification | Mỗi nhánh đều phát final; clarify options dùng được; không kẹt loading. |
| AI-005 | P0 | Ngắt mạng giữa stream | UI báo gián đoạn; câu chưa final không bị coi hoàn chỉnh; server không ghi message nửa chừng thành final. |
| AI-006 | P0 | Server đóng stream không có final | FE kết thúc loading với lỗi có thể hiểu; không spinner vô hạn. |
| AI-007 | P0 | Chạm citation; GET /v1/passages/{id} | Passage/excerpt đúng nguồn, tồn tại và được phép truy cập. |
| AI-008 | P1 | Session nhiều trang messages; tải cursor kế tiếp | Không lặp/bỏ message; thứ tự ổn định; cuối danh sách cursor null. |
| AI-009 | P1 | Quiz hint rồi explain | Hint có text/citations/generated; explain SSE có answer/final; hint_unavailable không auto-retry. |
| AI-010 | P1 | Gửi helpful rating và accept suggestion | Rating gắn đúng message; accept chỉ tạo một side effect; kind/for_date/practice_set_id hợp lệ. |
| AI-011 | P0 | Có attempt mở; gọi chat API bỏ qua kiểm tra UI | Nếu policy cấm chat lúc thi, server chặn; không chỉ dựa vào client. |
| AI-012 | P1 | Theo dõi event timestamps ở server/proxy/browser | Stream đến theo thời gian thực trong SLO đã chốt, không dồn thành response cuối. |

### 7.8 Progress skills/rhythm

| ID | Ưu tiên | Tiền điều kiện và thao tác | Kết quả mong đợi |
| --- | --- | --- | --- |
| PROG-001 | P0 | Learner có attempts; GET /v1/progress/skills?scope=latest3 | Coverage/priorities/scores chỉ từ attempts phù hợp; account đúng. |
| PROG-002 | P1 | Có hơn 3 attempts; gọi latest3 và all | Scope khác nhau đúng; attempt chưa submit không tính. |
| PROG-003 | P0 | Có specialty/level chưa được đánh giá | total=0 hiển thị chưa có dữ liệu; không thành 0% giả/NaN. |
| PROG-004 | P0 | L-EMPTY tải skills/rhythm | Empty state; nullable recall/curve không đổi thành 0; không dùng seed. |
| PROG-005 | P0 | Chuẩn bị 56 ngày hoạt động; GET rhythm | Heatmap đủ 56 ngày, tuần bắt đầu thứ Hai, gồm ngày 0 phút. |
| PROG-006 | P0 | Events lúc 23:59 và 00:01 giờ VN | local_date/week/heatmap/home gán theo Asia/Ho_Chi_Minh nhất quán. |
| PROG-007 | P1 | Có current/previous week, ngày học 0/đủ | minutes, previous_minutes, study_days, days_elapsed không âm và cùng định nghĩa tuần. |
| PROG-008 | P1 | Có review/decay/projected curve | Recall trong 0–1; kind đúng; actual/projected phân biệt; đơn vị không bị nhân/chia sai. |
| PROG-009 | P1 | Có due forecast 7 ngày; mở nhịp học/lịch ôn | Horizon được chốt; ngày thiếu record không bị hiểu nhầm với API đã báo 0. |
| PROG-010 | P0 | Learner A/B có số liệu khác | Token A/B chỉ trả aggregates tương ứng; không phụ thuộc localStorage. |
| PROG-011 | P1 | Hoàn tất unit/practice/card/exam rồi tải progress thiết bị khác | Dữ liệu server đã commit phản ánh đồng bộ; cache thiết bị cũ không phải nguồn chính. |

### 7.9 Staff dashboard, export, CSV và reports

| ID | Ưu tiên | Tiền điều kiện và thao tác | Kết quả mong đợi |
| --- | --- | --- | --- |
| STAFF-001 | P1 | S-ADMIN tải overview không filter và theo period/school/audience/region | selected filter, options và KPI đúng dataset/quyền. |
| STAFF-002 | P1 | Có cohort nhỏ dưới ngưỡng; đổi filter/query | Số liệu bị suppression không thể suy ngược; suppression server-side. |
| STAFF-003 | P1 | Export XLSX cùng filter dashboard đã suppression | MIME/filename/file hợp lệ; không có dữ liệu nhạy hơn dashboard. |
| STAFF-004 | P1 | S-READONLY thử import/confirm/export | Chỉ action được cấp mới thành công; authorize backend từng route. |
| STAFF-005 | P1 | Preview CSV hợp lệ và có lỗi, multipart field file | rows_total/valid/sample/lỗi theo dòng đúng; preview chưa phát activation codes. |
| STAFF-006 | P1 | CSV sai header, audience lạ, thiếu dòng, duplicate, file quá lớn | Lỗi được chỉ rõ; không import một phần mơ hồ; size/encoding theo policy. |
| STAFF-007 | P1 | Confirm batch hợp lệ lần đầu | Chỉ phát code sau confirm; số code khớp row valid; audit/batch state đúng. |
| STAFF-008 | P1 | Mất response confirm sau khi server đã xử lý; retry | Không phát code trùng; recovery theo semantics one-time visibility đã chốt. |
| STAFF-009 | P1 | Batch hết hạn hoặc staff khác confirm | Backend kiểm tra expiry/ownership/role; không phát code. |
| STAFF-010 | P1 | Reports chưa bật hoặc đã bật; gửi payload hợp lệ/sai | Chưa bật: thông báo chưa hỗ trợ, không giả success. Đã bật: validate target/reason/note và trả receipt ID. |

## 8. Kiểm thử UI trên mobile

| ID | Ưu tiên | Thao tác | Kết quả mong đợi |
| --- | --- | --- | --- |
| UI-001 | P0 | Mở login/home/progress/chat ở 320, 360, 390, 430 CSS px | Không tràn ngang/chồng chữ; CTA không bị bottom nav che. |
| UI-002 | P0 | Mạng chậm khi mở màn có GET | Loading rõ; không hiện số 0 như dữ liệu thật trước response. |
| UI-003 | P0 | API trả empty/null/partial data | Các khối độc lập vẫn dùng được; không NaN, crash hoặc biểu đồ giả. |
| UI-004 | P0 | API trả 401/403/409/404/501/5xx | Hành động tiếp theo rõ: login, consent, retry, quay lại; không raw stack/HTML. |
| UI-005 | P0 | Tap liên tục submit answer/review/submit exam | Pending guard; không tạo mutation trùng; người dùng thấy kết quả gửi. |
| UI-006 | P1 | Reload/back/forward giữa unit/practice/chat/exam | Khôi phục trạng thái server đã lưu; không hiển thị stale result. |
| UI-007 | P1 | Dùng bàn phím ảo tại login/chat/report | Input/CTA không bị che; focus và validation thao tác được. |
| UI-008 | P1 | Tăng system text/zoom browser | Consent, feedback, chart và CTA chính vẫn đọc được. |
| UI-009 | P1 | Chạm heatmap/điểm chart theo thiết kế hiện hành | Trạng thái selected rõ; chi tiết cùng ngày/chuyên khoa khớp response; không sinh chart thừa. |
| UI-010 | P2 | SSE status/step/answer cập nhật dần | Step/loading đúng; final dừng loading; reduced-motion không làm mất thông tin. |

## 9. Security, privacy, reliability và performance

### 9.1 Security/privacy checklist

- **IDOR:** đổi user_id, unit_id, attempt_id, card_id, session_id, message_id, batch_id, passage_id thành ID fixture khác; không trả dữ liệu trái quyền.
- **Authentication:** thiếu/sai/expired/revoked token và role sai được xử lý nhất quán.
- **Authorization:** learner không gọi admin; staff read-only không mutation nếu policy cấm; quyền kiểm tra server-side.
- **Validation/injection:** payload dài, field lạ, HTML/Markdown độc hại, CSV formula, MIME/encoding sai được validate/escape; export không làm spreadsheet chạy công thức từ dữ liệu user.
- **Abuse limits:** login, activation, AI, report, import có rate/size limit đã chốt; không tiết lộ account nào tồn tại.
- **Logging:** không ghi token, mật khẩu, activation code hoặc nội dung nhạy cảm; correlation ID đủ debug.
- **Suppression:** thử filter kết hợp, tổng phụ, export và thời điểm khác; không suy ra cohort bị ẩn bằng phép trừ.
- **Retries:** timeout trước/sau commit, reset connection, submit đồng thời; không lặp side effect.
- **SSE:** disconnect, restart, malformed event, missing final; không giữ stream/tác vụ vô hạn ngoài policy.
- **Recovery:** backend xác nhận RPO/RTO cho dữ liệu học/attempt; kiểm thử restore theo quy trình staging, không destructive trên production.

### 9.2 Đo hiệu năng và tải

Product/backend/SRE cần chốt SLO trước khi chạy load test. Các mục dưới đây là chỉ số cần đo, không phải cam kết hiện tại.

| Luồng | Chỉ số | Target được duyệt | Workload |
| --- | --- | --- | --- |
| GET home/session/progress | p50/p95/p99, error rate, DB time | Cần chốt | Tải thường, burst đầu giờ học. |
| POST answer/review/submit | latency, commit, duplicate rate | Cần chốt | Request thường, retry, cùng key đồng thời. |
| Chat SSE | thời gian event đầu, inter-event delay, duration, disconnect | Cần chốt | Queue, câu ngắn/dài, client disconnect. |
| Dashboard/export | latency, memory, file size, query cost | Cần chốt | Filter toàn quốc và cohort suppression. |
| CSV preview/confirm | latency, memory, rows/second, duplicate issuance | Cần chốt | File nhỏ, file max, batch đồng thời. |

## 10. Release gate

### Gate 0 — Contract/môi trường

- OpenAPI có version và khớp method/path/schema/status/header/error code.
- Proxy Vite/staging/Vercel đưa /api/v1 tới backend trước SPA fallback; JSON/SSE không rewrite/buffer sai.
- Fixture, role, timezone và feature flags đã được QA xác nhận.
- Không còn P0 contract mismatch.

### Gate 1 — Identity và đường học chính

- P0 NET, AUTH, consent, home/session, unit, card due, exam deadline/save/submit pass.
- Không mất dữ liệu đã được server xác nhận khi reload/retry.
- Không có truy cập chéo account.

### Gate 2 — AI và progress

- SSE luôn kết thúc final ở mọi nhánh; disconnect/missing final xử lý an toàn; citation mở đúng nguồn.
- Progress dùng server data; heatmap/ngày/timezone đúng; null/zero không sai nghĩa.
- Tính năng local/demo không được trình bày như đã đồng bộ live.

### Gate 3 — Staff/privacy

- Role và suppression áp dụng ở API/export; CSV chỉ phát code lúc confirm theo semantics đã chốt.
- Reports/import không được coi là ready nếu còn 501 hoặc chưa có quyền/contract.
- Consent withdrawal, export/delete, audit/retention có quyết định product/backend bằng văn bản.

### Gate 4 — Release

- Không còn Sev-1/Sev-2; Sev-3 có owner, workaround, hạn xử lý và product chấp thuận.
- Smoke staging sau release build pass; rollback/migration/recovery có owner xác nhận.
- SLO, alert, redaction, support contact và feature flags sẵn sàng.

**Quy tắc:** P0 fail hoặc security/privacy blocker thì không phát hành luồng liên quan. Feature chưa bật chỉ có thể ghi NOT APPLICABLE khi flag/API chưa phát hành và scope release ghi rõ; không đổi FAIL thành PASS.

## 11. Thứ tự chạy khuyến nghị

1. **Smoke mỗi build staging, khoảng 15–30 phút:** NET-001, AUTH-001, AUTH-005, HOME-001, một unit answer, một card review, một attempt start/save/submit, một chat stream, PROG-004 và AUTH-010.
2. **Regression learner:** toàn bộ P0 NET/AUTH/CONSENT/UNIT/CARD/EXAM/AI/PROG.
3. **Feature regression:** PRACT, staff, export, CSV, report theo feature flags.
4. **Mobile/resilience:** viewport, network throttling/offline, reload, timezone/date boundary.
5. **Security/performance:** chỉ chạy trên staging được phép; lưu báo cáo riêng; không destructive trên production.

## 12. Ma trận thiết bị và mạng

| Ma trận | Tối thiểu | Ghi chú |
| --- | --- | --- |
| Viewport | 320×568, 360×800, 390×844, 430×932 CSS px | Portrait là chính. |
| Browser | Chrome Android hiện hành, Safari iOS hiện hành, Chrome desktop responsive | Ghi OS/browser version khi tạo bug. |
| Network | Wi-Fi; 4G chậm/latency cao; offline trước request; offline giữa response/SSE | Throttling không dùng để khẳng định SLO BE. |
| Session | Tab đơn/hai tab, reload, tab background rồi quay lại | Chú ý refresh rotation, exam timer, SSE. |
| Clock | Giờ đúng, client lệch, qua nửa đêm VN, đầu/cuối tuần | Server là nguồn deadline/ngày nghiệp vụ. |

## 13. Mẫu ghi nhận kết quả

Mỗi test run ghi đủ:

- Test run ID và thời gian kèm timezone.
- Môi trường, FE commit, BE build, OpenAPI version.
- Thiết bị, OS, browser, account fixture, role, mode và feature flags.
- Test case ID và kết quả PASS/FAIL/BLOCKED/NOT RUN.
- Bước chạy, kết quả mong đợi, thực tế.
- Request/correlation ID; ảnh/video/log đã khử dữ liệu nhạy cảm.
- Bug ID và người phụ trách nếu có.

### Phân mức lỗi

| Mức | Định nghĩa | Ví dụ |
| --- | --- | --- |
| Sev-1 | Lộ dữ liệu, sai quyền, mất dữ liệu diện rộng, hoặc luồng chính không dùng được | Learner đọc attempt của người khác; refresh làm mất đáp án đã lưu. |
| Sev-2 | Chặn luồng chính hoặc làm kết quả học/thi sai đáng kể, chưa có workaround | Attempt bị đóng sớm; AI stream không final và không gửi tiếp được. |
| Sev-3 | Lỗi một phần, có workaround, không lộ/sai dữ liệu lõi | Filter phụ sai hoặc status chưa rõ. |
| Sev-4 | Cosmetic/cải thiện nhỏ | Spacing/icon lệch nhưng nội dung và thao tác vẫn rõ. |

## 14. Quyết định cần chốt trước khi coi expected result là bắt buộc

1. Refresh rotation, logout revoke và nhiều tab.
2. Role matrix cụ thể cho admin, ministry_viewer và route staff.
3. Semantics DELETE /me, consent withdrawal, retention, audit và restore.
4. Attempt fresh=true, auto-submit, clock authority và answer pending.
5. Idempotency TTL, key/payload conflict và retry sau khi mất response commit.
6. Due forecast horizon, 56-day heatmap, tuần bắt đầu thứ Hai, ngày/timezone.
7. Chính sách chat khi attempt mở; rate limit, SSE timeout và retry.
8. Suppression threshold, quyền export/import, preview expiry và confirm recovery.
9. SLO latency/availability/error rate cho JSON, SSE, dashboard, import.
10. Feature flags/release scope cho practice create, card library, reports, CSV.

Khi các mục trên chưa chốt, ca kiểm thử tương ứng vẫn dùng để khám phá hành vi nhưng expected result ghi **BLOCKED — chờ quyết định**; không tự thay product/backend chọn semantics.

