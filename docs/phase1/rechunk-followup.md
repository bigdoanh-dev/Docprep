# Chuẩn hóa OCR, đề xuất nhãn và kiểm tra trên Chat

Thực hiện tiếp từ [bản rechunk đầu tiên](rechunk-review.md). Học liệu vẫn đi qua hai bước xác nhận của người duyệt và quy trình release hiện có trước khi Chat sử dụng.

## Kết quả kiểm tra ngày 25/11/2026

- Chạy pipeline v2 trên 5 file gốc và nhập **1.453 chunk** vào PostgreSQL thử nghiệm. Hai nguồn scan tạo **928 chunk**. Có **361 chunk OCR** lấy nội dung từ nhiều ảnh trang và giữ vị trí của từng ảnh. OCR dựng được 4 chunk bảng và gắn cờ chưa xác định bố cục bảng cho 48 chunk.
- Chạy tagger ở chế độ kế thừa trên revision mới. Đã lưu **403 nhãn đề xuất** khớp nguồn cũ. **1.050 chunk** chưa có đề xuất, gồm 23 chunk phần đầu tài liệu được bỏ qua tự động và 1.027 chunk trong danh sách chờ. Chưa có nhãn nào được xác nhận trong các revision v2.
- Đạt 10 ca kiểm thử xử lý nội dung, gán nhãn và cách tính chỉ số, cùng 2 ca PostgreSQL cho nhập revision và lưu đề xuất không tự duyệt. Lệnh xuất gold từ các revision v2 xác nhận chưa có chunk được reviewer duyệt theo chính sách `human-v1`.
- Môi trường này chưa truy cập được Ollama lab và chưa có khóa Google trong cấu hình backend. Chưa chạy đánh giá kappa trên dữ liệu thật và chưa chạy so sánh A/B trên Chat. A/B cần hai release đã được duyệt, chỉ mục embedding sẵn sàng và model hoạt động.

## 1. Dựng lại cấu trúc OCR

Lệnh `rechunk` tạo phiên bản pipeline `yhdp-original-rechunk.v2`. Tesseract trả chữ và tọa độ. Bộ xử lý gom chữ thành dòng, dựng ngăn xếp heading qua các trang, giữ đoạn văn và thử nhận dạng bảng khi có chú thích, tiêu đề cột và các hàng căn thẳng. Các mốc chương của hai nguồn được lưu theo hash của file Word để tránh nhận nhầm tiêu đề chạy hoặc mục lục thành chương chính. Mốc chương và các đề mục phát hiện từ OCR cần được rà cùng ảnh gốc.

Output mỗi tài liệu scan có các file `formatted.md`, `parsed.json`, `chunks.jsonl` và `parents.json`. `section_path` và `parent_id` dùng cấu trúc heading. `image_indices` giữ ảnh trang nguồn, còn `printed_pages` để trống nếu chưa xác minh số in. Bảng chưa nhận dạng chắc chắn giữ văn bản OCR và được đánh dấu `ocr_table_unresolved`. Bảng dựng được cũng có cờ chờ rà vì căn tọa độ chưa bảo đảm từng ô chính xác. Các bảng phức tạp, ô gộp và bảng kéo qua nhiều trang cần đối chiếu thêm.

```powershell
# Từ thư mục backend. Dùng một thư mục đầu ra mới.
$env:OMP_THREAD_LIMIT = '1'
.\.venv\Scripts\python.exe -m app.content.cli rechunk 'D:\InternAIRC\AI_TuTor\data.zip' --sources '..\..\rechunk-sources-20261124' --output '..\..\rechunk-structured-new' --tesseract 'C:\Program Files\Tesseract-OCR\tesseract.exe' --tessdata '..\..\.tessdata' --ocr-cache '..\..\.ocr-cache'
```

`--tessdata` trỏ tới thư mục có `vie.traineddata` và `eng.traineddata`. Bản cài Tesseract mặc định chỉ có `eng`; khi thiếu `vie`, Tesseract vẫn chạy nhưng mất dấu tiếng Việt, nên lệnh `rechunk` dừng ngay nếu thiếu gói ngôn ngữ. `--ocr-cache` lưu TSV theo hash ảnh trang, ngôn ngữ và file mô hình; chạy lại chỉ OCR các trang đã thay đổi.

### Mục lục làm khung đề mục (26/11/2026)

Với tài liệu *Hướng dẫn chẩn đoán và xử trí ngộ độc*, danh sách bài trong [ocr_outline.py](../../backend/app/content_tools/ocr_outline.py) được chép từ mục lục và đối chiếu với dòng tiêu đề ở trang đầu mỗi bài. Pipeline chỉ mở bài mới khi gặp dòng khớp một bài chưa mở trong mục lục. Vì vậy dòng in hoa bị OCR sai không thể thành tên bài, và bài bị bỏ sót tiêu đề không còn bị gộp vào bài trước. Đề mục đánh số in hoa bị Tesseract dính vào đoạn văn ("4. DIEU TRI") được tách thành heading, và dấu của các đề mục chuẩn được khôi phục (cờ `ocr_heading_normalized`).

| Chỉ số `ngodoc` | v2 ngày 25/11 | Sau khi sửa |
|---|---:|---:|
| Bài nhận diện được (mục lục có 35) | 19 | **35** |
| Tiểu mục thiếu mục cha (ví dụ "3.2" không có "3.") | 32 | 3 |
| Đánh số quay ngược trong cùng bài | 12 | 1 |
| Đề mục mất dấu | 7 | 1 |

Ví dụ `section_path`: `Chương 2. Các trường hợp ngộ độc cụ thể › Phần 2.3. Các chất độc tự nhiên › RẮN CẠP NIA CẮN › 3. CHẨN ĐOÁN › 3.2. Cận lâm sàng`. Các chỗ còn lại vẫn mang cờ rà soát và cần đối chiếu ảnh gốc.

Thêm `--apply` khi cần tạo revision trong DB biên tập theo cấu hình hiện có. Lưu các `revision_id` trả về để chọn đúng lô ở bước kế tiếp.

## 2. Sinh nhãn đề xuất

Tagger đối chiếu theo tài liệu, loại chunk, đường dẫn đề mục và nội dung chuẩn hóa. Chỉ dùng nhãn cũ khi có đúng một đoạn khớp và nhãn gốc khớp hash của chunk cũ. Trường hợp không khớp có thể đề xuất qua model nếu operator chọn provider. Mã vấn đề và miền phải tồn tại trong taxonomy. Mỗi lần ghi có provenance và khóa kiểm tra phiên bản để giữ nhãn người duyệt đã tạo.

```powershell
# Mặc định chỉ xem trước các nhãn kế thừa. Dùng --apply để ghi đề xuất.
.\.venv\Scripts\python.exe -m app.content.tagger 'D:\InternAIRC\AI_TuTor\data.zip' --revision '<revision-uuid>' --taxonomy '<taxonomy-version>' --output '..\..\tagger-preview.json'
```

Có thể lặp `--revision`. Sau khi đã chốt model và hạn mức với team, dùng `--provider google --model-budget 20` với cấu hình Google hiện có. Thêm `--fallback-local` nếu được dùng Ollama dự phòng, hoặc chọn trực tiếp `--provider ollama`. Đầu ra chưa chắc chắn vẫn để chờ phân loại. Đề xuất đã ghi tiếp tục ở trạng thái `unclassified` cho tới khi reviewer xác nhận.

## 3. Đo Cohen’s kappa

Danh sách chờ duyệt lấy từ [data.zip](tagger-eval-data-zip.md). Chọn đúng revision, taxonomy và ID mẫu. Đối với scan, cho reviewer duyệt mẫu trên revision v2 sau khi đã đối chiếu bố cục. Lệnh chỉ trích xuất quyết định duyệt thật `human-v1`, bỏ qua nhãn máy và quyết định chấp nhận dữ liệu cũ tạm thời.

```powershell
.\.venv\Scripts\python.exe -m experiments.tagger_eval.evaluate export-gold --revision '<reviewed-revision-uuid>' --taxonomy '<taxonomy-version>' --output '..\..\gold.json'
.\.venv\Scripts\python.exe -m experiments.tagger_eval.evaluate predict --gold '..\..\gold.json' --provider ollama --limit 60 --output '..\..\predictions.json'
.\.venv\Scripts\python.exe -m experiments.tagger_eval.evaluate score --gold '..\..\gold.json' --predictions '..\..\predictions.json' --output '..\..\kappa.json'
```

Với mẫu 60 chunk từ ZIP, thêm `--pilot experiments/tagger_eval/data-zip-pilot.json` vào lệnh `export-gold` và chọn các revision cũ tương ứng. Mô hình chỉ nhận nội dung, ngữ cảnh và danh mục. File báo cáo ghi kappa vấn đề chính, kappa Bloom có trọng số, độ khớp miền, độ phủ và tách nhóm Word/OCR. Khi chưa có mẫu được duyệt, lệnh dừng với lý do cụ thể.

## 4. Đánh giá release trên Chat thật

Chuẩn bị hai release được duyệt cùng hai chỉ mục embedding hoàn chỉnh. Dùng kênh thử nghiệm riêng. Chạy tuần tự với đúng release được kích hoạt ở mỗi lượt. Giữ cùng provider, bản embedding, cấu hình rerank và bộ câu hỏi. Câu chung có danh sách passage chấp nhận được cho cả hai release. Câu OCR mới có thể chỉ điền nhánh `candidate` và được báo riêng.

File ca kiểm tra là một mảng JSON. Mỗi ca có `id`, `question`, `group` tùy chọn và `expected` chứa `baseline` và/hoặc `candidate`. Mỗi nhánh có `states` (chẳng hạn `["answered"]`) và `passages` là các ID đã xác nhận trong release đó. Ca thiếu bằng chứng dùng `["insufficient_evidence"]` và mảng passage rỗng.

```powershell
# CHAT_EVAL_TOKEN dùng tài khoản learner thử nghiệm.
# CHAT_EVAL_DATABASE_URL dùng kết nối chỉ đọc vào DB runtime thử nghiệm.
.\.venv\Scripts\python.exe -m experiments.retrieval_eval.chat_release_eval run --api http://127.0.0.1:18880/api/v1 --channel '<eval-channel>' --version '<old-release>' --embedding-model bge-m3 --embedding-revision '<digest>' --variant baseline --cases '..\..\cases.json' --output '..\..\chat-old.json'
.\.venv\Scripts\python.exe -m experiments.retrieval_eval.chat_release_eval run --api http://127.0.0.1:18880/api/v1 --channel '<eval-channel>' --version '<new-release>' --embedding-model bge-m3 --embedding-revision '<digest>' --variant candidate --cases '..\..\cases.json' --output '..\..\chat-new.json'
.\.venv\Scripts\python.exe -m experiments.retrieval_eval.chat_release_eval compare --baseline '..\..\chat-old.json' --candidate '..\..\chat-new.json' --output '..\..\chat-comparison.json'
```

Runner gửi câu hỏi qua Chat API và đợi sự kiện SSE cuối. Worker ở `APP_ENV=dev/test` lưu ID đoạn trước và sau rerank vào trace để runner đối chiếu. Báo cáo tách fallback, lỗi, ca không có bằng chứng hybrid và ca khác cấu hình. Kết quả so sánh chính chỉ dùng các cặp quan sát được hybrid với cấu hình tương thích. Lượt dùng sai phiên bản release hoặc index chưa sẵn sàng không được tính như lượt thành công.
