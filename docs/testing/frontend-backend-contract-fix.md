# Đồng bộ hợp đồng frontend/backend — 07/11/2026

> Cập nhật 13/11/2026: phần Tiến độ đã chuyển sang contract 6 mức với số liệu nhóm cũ được giữ riêng. Xem [biên bản sửa lỗi](confirmed-bug-fixes-2026-11-13.md). Nội dung bên dưới là ghi nhận của đợt tích hợp trước.

Đã sửa các chỗ lệch trong [báo cáo audit trước khi sửa](frontend-backend-audit.md). Frontend gốc repo sử dụng dữ liệu thật từ backend Phase 1; các thống kê mới được tính từ bản ghi của người học.

## Thay đổi

| Phần                  | Hành vi sau khi sửa                                                                                                                                                                                                                                                              |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Thống kê nhận thức    | Biểu đồ, chú giải và ma trận dùng số mức và nhãn từ API: **Nhớ, Hiểu / Vận dụng / Phân tích, Đánh giá**. Bộ dữ liệu demo 6 mức vẫn hiển thị theo nhãn riêng của nó.                                                                                                              |
| Kết quả và tiến độ    | API trả `levels`, `specialties`, `bloom_by_specialty`, `issues_by_specialty`, gồm 8 nhóm và 54 vấn đề. Phạm vi tiến độ vẫn là `latest3` hoặc `all`, chỉ tính đề thi thử đã nộp.                                                                                                  |
| Độ chính xác thống kê | Join `item_response` với đúng `question_version`; chỉ tính câu đã trả lời. Câu bỏ trống vẫn có trong điểm và danh sách kết quả, không thành đánh giá nhận thức. Các nhóm/vấn đề chưa làm có `total=0`, hiển thị “Chưa có dữ liệu”. FND thuộc g1, không bị gán một mã vấn đề giả. |
| Phạm vi đề            | `/exams` có `module_id`/`module_name` nếu toàn bộ câu của đề cố định thuộc một học phần. Đề tự ráp hoặc đề nhiều học phần có phạm vi tổng hợp. Trong seed hiện tại: 2 đề g1 và 1 đề tổng hợp.                                                                                    |
| Phân loại câu         | Review và practice trả học phần, vấn đề, độ khó, `bloom_level` và `bloom_label` từ phiên bản câu đã phục vụ. Metadata chưa có giữ null. Frontend dùng nhãn backend.                                                                                                              |
| Giới hạn thẻ          | Hàng đợi khả dụng dùng cả `new_cards_per_day` và `max_reviews_per_day`. Home, Decks, tiến độ và phiên học đọc cùng quy tắc. Mỗi rating dùng một lượt; lần đầu ôn một thẻ dùng thêm một suất thẻ mới; đặt lại theo ngày Việt Nam. Tạm dừng thẻ không hoàn lại lượt đã dùng.       |
| Ghi lượt ôn           | Backend kiểm tra giới hạn trước khi ghi, khóa hàng learner để hai thiết bị không cùng tiêu suất cuối. Gửi lại cùng `Idempotency-Key` vẫn chỉ ghi một lượt. Hết ngân sách không giữ bước thẻ ở trạng thái không thể hoàn thành.                                                   |
| Phiên nhiều thẻ       | `/cards/due` thêm `offset`; mỗi request vẫn tối đa 200. Frontend tải đủ pass bằng các trang trước khi chấm thẻ; kiểm thử pass 250 thẻ với trang 200 và 50.                                                                                                                       |

Không cần migration và không đổi công thức chấm điểm. Kết quả thi cũ đọc được thống kê bổ sung từ các response đã lưu. `openapi.yaml` đã được sinh lại từ code.

Kiểm tra lại phát hiện và sửa thêm lỗi giới hạn ôn khi hai request xử lý ngược thứ tự thời gian nhận. `Now` được lấy trước khi chờ khóa learner; điều kiện cũ `reviewed_at <= Now` có thể bỏ sót lượt đã commit từ request nhận sau. Backend hiện đếm trong khoảng từ đầu ngày đến trước đầu ngày kế tiếp theo múi giờ Việt Nam. Hai ca regression kiểm tra riêng giới hạn lượt ôn và thẻ mới đã tái hiện được lỗi trước sửa.

## Kiểm chứng

- `npm.cmd run build`, `npm.cmd run lint`: đạt; **116/116** test frontend đạt.
- Regression backend sau kiểm tra lại: **174/174 đạt**, không bỏ qua ca nào, sử dụng database riêng `phase1_test`. Gồm API learner, phân loại/phiên bản câu, phạm vi thống kê, giới hạn ngày, gửi lại, hai lượt ôn đồng thời, xử lý ngược thứ tự request, phân trang, OpenAPI và bộ test Phase 1. XML mới nằm tại `.local/recheck-backend.xml`; OpenAPI trong workspace được mount chỉ đọc để đối chiếu với code, không sinh đè trước kiểm tra.
- Đối chiếu live: **69 request**, **42 response** kiểm tra bằng kiểu TypeScript, không thiếu trường bắt buộc hoặc sai kiểu. Các danh sách `missingResultsFields`, `missingProgressFields`, `missingQuestionMetadata`, `practiceMissingMetadata` đều rỗng.
- Kiểm thử live với `new_cards_per_day=1`, `max_reviews_per_day=1`: queue trả **1 thẻ**, `total_due=1`, thay cho 11 thẻ trước sửa.
- Edge desktop/mobile qua Vite: **8/8** ca live đạt; **2/2** ca đối chiếu số liệu/nhãn và **4/4** ca demo/tương thích response cũ đạt.
- Bản build Docker qua Caddy: **8/8** ca live desktop/mobile đạt, không bỏ qua ca nào.
- Lượt kiểm tra lại qua Vite/Caddy: **16/16** ca tích hợp và **2/2** ca đối chiếu giao diện đạt; kết quả mới trong `.local/live-integration/recheck-vite-results.json`, `recheck-caddy-results.json` và `.local/frontend-api-audit/ui-results.json`. Cả 4 instance API/Chat đã xác minh hash file sửa khớp workspace.
- Ảnh xác nhận nhãn Bloom, danh sách đề và phân loại câu nằm trong `.local/frontend-api-audit/ui-results/`; dữ liệu audit trong cùng thư mục cha. Các artifact local được Git bỏ qua.

## Trạng thái chạy local

Frontend phát triển: `http://127.0.0.1:5190`. Bản build và API gateway: `http://127.0.0.1:18880`. Backend, Caddy và dữ liệu phát triển đã được giữ lại; database test tách riêng.

Provider AI giữ `disabled`: chat gọi đúng API và hiển thị lỗi `503 ai_disabled` khi yêu cầu sinh câu trả lời. Đợt sửa này chưa cấu hình model thật. Các chức năng CSV/review/reports hoặc tạo practice tự chọn còn thiếu API live vẫn được giữ giới hạn đã nêu trong audit; không coi là đã triển khai những chức năng đó.

Các thay đổi được tích hợp trên nhánh `feat/alpha-v1-backend-2`; nhánh `feat/alpha-v1-backend` giữ nguyên. Bộ test bổ sung theo yêu cầu không ghi vào repo được lưu riêng ngoài repository và không đưa vào commit.
