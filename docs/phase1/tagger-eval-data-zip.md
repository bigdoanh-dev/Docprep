# Bộ mẫu và tiêu chí đánh giá tagger YHDP

**Trạng thái ngày 25/11/2026:** Đã chọn mẫu từ `data.zip`. Mẫu đang chờ reviewer gán nhãn. Chưa có điểm Cohen’s kappa và chưa có kết quả chạy model trên các mẫu này.

## Nguồn mẫu

| Nguồn trong ZIP | Kết quả kiểm tra |
|---|---|
| `data/yhdp.db` → `chunks` | 477 chunk thuộc QĐ 2760, 5642 và 5904. |
| `chunk_tags` | Có 479 bản ghi nhãn. Khi đối chiếu bằng cả `chunk_id` và `content_hash`, 477 bản ghi khớp với chunk hiện có và 2 bản ghi lệch. |
| 477 bản ghi nhãn khớp | Tất cả có `source=auto`, thiếu người duyệt. Trong số đó, 171 có `review_status=auto` và 306 có `review_status=review`. |
| `review_items` | Có 306 tác vụ duyệt nhãn đang mở. Không tìm thấy nhãn chuyên môn đã được reviewer xác nhận trong ZIP. |
| Hai tài liệu OCR | *Xử trí ngộ độc* có 228 ảnh trang và *Dịch tễ học cơ bản* có 234 ảnh trang. Cả hai chưa có chunk gán nhãn trong SQLite. |

Nhãn cũ hữu ích để đề xuất nhãn và tham khảo cách phân loại. Trạng thái `review` của ZIP cho biết đoạn cần rà, chưa phải nhãn đã được reviewer duyệt.

## Bộ mẫu chờ duyệt

[Danh sách mẫu cố định](../../backend/experiments/tagger_eval/data-zip-pilot.json) có 60 chunk, mỗi quyết định 20. Trong mỗi tài liệu có 10 mẫu từ nhóm `auto` và 10 mẫu từ nhóm `review` của máy. Tổng cộng có 45 đoạn văn, 12 bảng, 2 hình và 1 công thức. Mỗi dòng mẫu lưu ID và hash của chunk để lấy đúng văn bản. Các hash được chọn đều khác nhau. Danh mục nhãn dùng `data/blueprint/qd51.yaml`, với SHA-256 đã lưu trong manifest.

Manifest còn có 8 ảnh tham chiếu cho mỗi tài liệu OCR để thử khôi phục bố cục. Đây là danh sách ảnh định vị nguồn. Sau khi dựng heading và rechunk, chọn chunk OCR từ các nguồn này theo độ đa dạng của mục, chất lượng OCR và cấu trúc bảng, rồi đưa reviewer duyệt riêng.

## Cách chuẩn bị nhãn đối chiếu

1. Reviewer mở nội dung và vị trí nguồn của từng mẫu, rồi gán nhãn theo cùng phiên bản danh mục. Bộ nhãn tối thiểu gồm mã vấn đề chính, tập mã miền năng lực và mức Bloom. Có trạng thái riêng cho trường hợp không đủ dữ liệu để gán nhãn.
2. Chốt kết quả reviewer trước khi chạy đánh giá. Với mẫu khó, lấy kết luận của reviewer sau khi đối chiếu nguồn. Reviewer gán độc lập với nhãn máy cũ và dự đoán của model.
3. Khi chạy tagger, chỉ đưa văn bản, ngữ cảnh cần thiết và danh mục cho model. Giữ nhãn reviewer riêng để chấm. Loại các mẫu đánh giá khỏi ví dụ dùng để xây prompt. Nếu chỉnh prompt dựa trên lỗi ở tập 60 mẫu, cần dùng mẫu giữ riêng để xác nhận cấu hình sau chỉnh sửa.
4. Đo riêng hai cách tạo đề xuất là kế thừa nhãn cũ và model dự đoán trực tiếp. Nhóm kế thừa cần đo độ chính xác của việc ghép chunk. Nhóm dự đoán đo với nhãn reviewer mà model chưa được thấy. Tách kết quả Word và OCR.

## Tiêu chí chấm

| Chỉ số | Cách tính và diễn giải |
|---|---|
| Vấn đề chính | Cohen’s kappa không trọng số trên mã vấn đề chính giữa tagger và reviewer. Kèm tỷ lệ khớp chính xác và các cặp nhãn hay nhầm. |
| Bloom | Cohen’s kappa có trọng số bậc hai. Báo thêm tỷ lệ khớp chính xác và tỷ lệ lệch từ hai mức trở lên. |
| Miền năng lực | Mỗi miền là một quyết định có hoặc không. Tính kappa theo miền có đủ hai lớp trong mẫu, kèm số mẫu dương, tỷ lệ khớp cả tập và micro-F1. Trường hợp hệ số không xác định phải ghi rõ. |
| Độ phủ và đầu ra hợp lệ | Báo số mẫu toàn bộ, số mẫu đánh giá được, số lần model bỏ qua, trả sai schema hoặc dùng mã ngoài danh mục. Tính kappa trên cặp nhãn hợp lệ và báo độ phủ riêng để thấy các ca bị bỏ lại. |

**Mốc đề xuất cho pilot**, cần lead xác nhận trước khi coi là tiêu chí nghiệm thu: đầu ra hợp lệ trên ít nhất 90% mẫu có thể gán nhãn, kappa vấn đề chính và kappa có trọng số của Bloom từ 0,60 trở lên. Đây là mốc để quyết định có mở rộng thử nghiệm. Báo kèm cỡ mẫu, kết quả OCR riêng và các lỗi điển hình. Chưa dùng điểm kappa để tự duyệt nhãn hay phát hành corpus.

## Model đã có

File `local-llm.md` mô tả Ollama trên mạng lab. Model sinh là `qwen3.5:9b-q4_K_M`, có thể dùng làm mốc local và phương án dự phòng. `bge-m3` dùng để tạo embedding cho tìm kiếm, không dùng để sinh nhãn. Theo cấu hình được cung cấp, chạy tagger qua API chat của Ollama với chế độ reasoning tắt và kiểm tra đầu ra theo danh mục. Lần kiểm tra từ workspace này chưa kết nối được tới endpoint lab. Cấu hình model API cấp cao và hạn mức miễn phí chưa được nêu trong file, nên đánh giá sẽ ghi riêng khi có cấu hình đó.
