# Chia lại học liệu YHDP từ tài liệu gốc

Pipeline đọc 5 file Word gốc theo `data/sources.yaml`. Ba file có văn bản đi qua bộ đọc Word kế thừa YHDP, hai file scan đi qua OCR tiếng Việt. Lệnh nhập tạo phiên bản học liệu riêng trong PostgreSQL và tạo hai nhiệm vụ duyệt cho mỗi chunk. [Mẫu đối chiếu Phụ lục 9](qd2760-chunking-pilot.md) minh họa đoạn văn, bảng và ảnh đã so với Word.

| Yêu cầu | Cách triển khai |
|---|---|
| Chia lại từ nguồn | Đọc Word, gom đoạn cùng đề mục, chia bảng dài theo nhóm hàng và lặp tiêu đề. Giữ mỗi hình thành tài sản riêng. Nếu một câu hoặc dòng không thể tách an toàn, giữ nguyên và gắn cờ quá kích thước. |
| Contextual header | Ghép tên tài liệu, đường dẫn đề mục và chú thích khi có. Gắn lý thuyết, ví dụ hoặc bài tập khi đề mục nêu rõ. Vai trò chưa xác định lưu `unknown`. Vai trò này tách riêng với loại khối và nhãn chuyên môn. |
| Liên kết cha và con | Chunk lưu ID mục cha. Bảng có thể trỏ đến đoạn văn ngắn gần nhất đứng trước trong cùng mục. Runtime lấy thêm tối đa một đoạn thuộc cùng release, phiên bản, mục cha và năng lực. Đoạn bổ sung giữ ID trích dẫn riêng. |
| Từ khóa và câu hỏi | Từ khóa lấy từ nội dung. Câu hỏi đi kèm trích đoạn nguyên văn để đối soát. Khi chưa tạo được câu hỏi có bằng chứng, gắn `needs_review`. Metadata chỉ cộng điểm nhẹ cho ứng viên đã đạt ngưỡng bằng chứng. |

## Kiểm tra trước khi phát hành

- Dùng số thứ tự ảnh gốc để định vị bản scan. Số trang in chỉ ghi khi đã xác nhận. OCR giữ báo cáo theo từng ảnh, gồm điểm tin cậy và trạng thái trang. Cần hiệu đính văn bản OCR, nhận dạng đề mục và kiểm tra bố cục bảng/hình trong scan.
- Bảng bị làm phẳng trong Word được gắn cờ riêng. Kiểm tra bảng dài và các phần bị gắn cờ trước khi duyệt nội dung.
- Phiên bản mới có trạng thái chuyên môn `unclassified` và nội dung `pending`. Người duyệt có thể chuyển các đoạn đã phân loại rõ sang `classified`. Việc duyệt và kích hoạt tiếp tục theo quy trình release hiện có.

## Kết quả chạy ngày 24/11/2026

| Nguồn | Chunk cũ | Chunk mới | Chunk có câu hỏi nháp | Đối soát nguồn |
|---|---:|---:|---:|---|
| QĐ 2760 | 180 | 208 | 207 | 635/637 khối khớp bản phân tích cũ. Hai khối còn lại được cập nhật chú thích Nam/Nữ theo ảnh. |
| QĐ 5642 | 187 | 204 | 189 | Bản Word được chọn khớp 1.032/1.032 khối theo thứ tự. Có 11 chunk từ bảng làm phẳng cần rà lại. |
| QĐ 5904 | 110 | 113 | 110 | 298/298 khối khớp bản phân tích cũ. |
| Xử trí ngộ độc | 0 | 408 | 403 | 228/228 ảnh trang khớp ZIP. OCR tìm thấy chữ ở cả 228 ảnh. |
| Dịch tễ học cơ bản | 0 | 523 | 520 | 234/234 ảnh trang khớp ZIP. OCR có chữ ở 226 ảnh, 8 ảnh được nhận diện là trống. |
| **Tổng** | **477** | **1.456** | **1.429** | **27 chunk** cần bổ sung hoặc rà câu hỏi. |

Đánh giá tìm kiếm offline trên **80 câu** có trích đoạn đáp án khớp với cả hai phiên bản:

| Cấu hình | Tìm đúng trong 5 kết quả đầu | MRR@5 |
|---|---:|---:|
| Bộ cũ có header | 45/80 (56,25%) | 0,3985 |
| Bộ mới có header | 54/80 (67,50%) | 0,4629 |
| Bộ mới có header, từ khóa và câu hỏi | 55/80 (68,75%) | 0,4708 |

Từ khóa và câu hỏi mang lại thêm 1 câu đúng trong top 5 trên bộ so sánh này. Kết quả chỉ đo ba văn bản có bản cũ để đối chiếu. Hai tài liệu OCR chưa có bộ câu hỏi đánh giá riêng, và số liệu trên chưa đo chất lượng câu trả lời của chatbot.

Thử nhập PostgreSQL trên database riêng `content_rechunk_review`: 477 chunk cũ và 1.456 chunk mới cùng tồn tại trong 8 phiên bản tài liệu. Chạy lại cùng bộ dữ liệu dùng lại cả 5 phiên bản mới. Các chunk mới đều chờ phân loại và duyệt nội dung. Đã chạy 16 ca kiểm tra bộ chia, metadata và truy xuất trên PostgreSQL 16 có pgvector, gồm ca ngữ cảnh bổ sung giữ ID trích dẫn riêng và không lấy nhầm phiên bản.

## Trình bày với lead

1. Mở Phụ lục 9. Chỉ ra đoạn lưu ý và bảng chung mục cha, cùng hai hình có chú thích Nam/Nữ đã được xác nhận trong Word.
2. Mở một dòng trong `chunks.jsonl`. Chỉ ra vị trí nguồn, header, ID mục cha và câu hỏi đi cùng trích đoạn bằng chứng.
3. Trình bày số liệu 80 câu. Nêu phần cải thiện từ chia lại/header và phần tăng thêm khi dùng từ khóa/câu hỏi.
4. Xin chốt mức chi tiết của metadata và thứ tự duyệt. Ưu tiên xác nhận số trang in, 11 chunk bảng làm phẳng và nội dung OCR trước khi phát hành.

## Chạy lại trên Windows

Lưu các file Word nguồn ngoài Git và đổi tên theo ID:

| ID | Tài liệu Word |
|---|---|
| `qd2760` | [Hướng dẫn sốt xuất huyết Dengue](https://docs.google.com/document/d/168L0_UWGIj0-4bqcg5XPRwhnavK32Sir/edit) |
| `qd5904` | [Hướng dẫn quản lý bệnh không lây nhiễm](https://docs.google.com/document/d/1IHKl33F55CS8c0uQ4rdzN-RKBzK2qMD6/edit) |
| `qd5642` | [Hướng dẫn một số bệnh truyền nhiễm](https://docs.google.com/document/d/1olYUkewoqReMGLborFrvivM3XAyy8Xcx/edit) |
| `ngodoc` | [Hướng dẫn xử trí ngộ độc](https://docs.google.com/document/d/1Jux7xm5OVxlwaQ_ut-N3ovSNzGIh9PEI/edit) |
| `dtch` | [Dịch tễ học cơ bản](https://docs.google.com/document/d/1l6ClZfGswY2jGFwqPk71W-_-IDiy-9M1/edit) |

Từ thư mục `backend`, cài dependency theo lockfile. Tesseract cần hai bộ ngôn ngữ `vie` và `eng`. Nếu chúng nằm ngoài thư mục cài đặt, trỏ `TESSDATA_PREFIX` vào thư mục chứa các file `.traineddata`.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
$env:OMP_THREAD_LIMIT = '1'
.\.venv\Scripts\python.exe -m app.content.cli rechunk 'D:\InternAIRC\AI_TuTor\data.zip' --sources 'D:\hoc-lieu-goc' --output 'D:\ket-qua-chunk-v1' --tesseract 'C:\Program Files\Tesseract-OCR\tesseract.exe' --ocr-workers 8
.\.venv\Scripts\python.exe experiments/retrieval_eval/rechunk_eval.py 'D:\InternAIRC\AI_TuTor\data.zip' 'D:\ket-qua-chunk-v1' --output 'D:\ket-qua-chunk-v1\retrieval-eval.json'
```

Lệnh tạo `parsed.json`, `chunks.jsonl`, `parents.json`, báo cáo và ảnh theo từng tài liệu. Dùng `--document qd2760` để chạy riêng một nguồn. Thêm `--apply` vào lần chạy với thư mục đầu ra mới để nhập vào DB tác giả bằng tài khoản **editor**, theo `CONTENT_DATABASE_URL` và `CONTENT_ASSET_ROOT`. Chạy lại cùng đầu vào và kết quả sẽ dùng lại phiên bản đã lưu.

Đánh giá tìm kiếm chạy offline trên các tài liệu có chunk cũ. Câu hỏi được ghép với chunk bằng trích đoạn đáp án và tên tài liệu. Báo cáo so sánh ba cấu hình gồm nội dung, thêm header và thêm từ khóa/câu hỏi.
