# Mẫu chia chunk lại — QĐ 2760, Phụ lục 9

Phạm vi gồm **mục 1 (trẻ em)** và **mục 2 (người lớn)** của Phụ lục 9 — Cân nặng hiệu chỉnh. Mẫu có 4 chunk con tương ứng với 4 chunk cũ và 2 mục cha dùng để bổ sung ngữ cảnh khi truy xuất.

- **Nguồn đối chiếu:** [Bản Word QĐ 2760 trên Drive](https://docs.google.com/document/d/168L0_UWGIj0-4bqcg5XPRwhnavK32Sir/edit), Phụ lục 9, mục 1 và 2.
- **Bộ chunk hiện tại:** `data/derived/qd2760/chunks.jsonl` và thư mục `figures/` trong `data.zip`.
- **Kết quả kiểm tra:** Đã đối chiếu đề mục và đoạn lưu ý. Bảng Word khớp 48/48 ô với bảng trong ZIP, gồm 3 ô tiêu đề và 45 ô dữ liệu. Hai ảnh trong Word khớp tệp trong ZIP theo mã băm SHA-256 và thứ tự xuất hiện. Ảnh thứ nhất ghi **Nam**, ảnh thứ hai ghi **Nữ**.

## Bảng so sánh

**Contextual header** là tên tài liệu kèm đường dẫn đến mục chứa chunk. Khi lập chỉ mục, ghép header với nội dung để đoạn hoặc bảng có thể được tìm theo đúng mục và đối tượng.

| Chunk cũ | Hiện có | Chunk mẫu và cách chia | Contextual header | Mục cha | Từ khóa mẫu | Câu hỏi để kiểm tra tìm kiếm |
|---|---|---|---|---|---|---|
| `qd2760#pl9/1#c01` | Đoạn văn có dẫn chiếu CDC 2014 và lưu ý về phạm vi áp dụng. | `pl9-1-text` · **Đoạn hướng dẫn.** Giữ dẫn chiếu và lưu ý trong cùng một đoạn. | QĐ 2760 → Phụ lục 9: Cân nặng hiệu chỉnh → Mục 1: Trẻ em dư cân hoặc béo phì → Lưu ý áp dụng | `pl9-1` | cân nặng hiệu chỉnh, trẻ em, CDC 2014, lưu ý áp dụng | Phụ lục 9 ghi lưu ý gì về phạm vi áp dụng của bảng ở mục trẻ em? |
| `qd2760#pl9/1#c02` | Bảng đã giữ ba tiêu đề cột và đủ 15 dòng dữ liệu. | `pl9-1-table` · **Bảng tra.** Giữ nguyên bảng nhỏ thành một chunk. Dùng chung mục cha với phần lưu ý. | QĐ 2760 → Phụ lục 9: Cân nặng hiệu chỉnh → Mục 1: Trẻ em dư cân hoặc béo phì → Bảng tra theo tuổi và giới | `pl9-1` | bảng cân nặng, tuổi, giới, đơn vị kg | Bảng cân nặng hiệu chỉnh cho trẻ em có những cột và đơn vị nào? |
| `qd2760#pl9/2#c01` | Ảnh `figures/pl9_2-1.png` dùng chung chú thích mục 2 với ảnh còn lại. | `pl9-2-fig-01` · **Bảng dạng ảnh.** Giữ ảnh riêng và bổ sung nhãn **Nam** theo tiêu đề trong ảnh. | QĐ 2760 → Phụ lục 9: Cân nặng hiệu chỉnh → Mục 2: Cân nặng chống sốc ở người lớn → Bảng dành cho nam | `pl9-2` | người lớn, nam, chiều cao, cân nặng | Bảng dành cho nam ở mục người lớn nằm ở đâu trong Phụ lục 9? |
| `qd2760#pl9/2#c02` | Ảnh `figures/pl9_2-2.png` dùng chung chú thích mục 2 với ảnh đầu. | `pl9-2-fig-02` · **Bảng dạng ảnh.** Giữ ảnh riêng và bổ sung nhãn **Nữ** theo tiêu đề trong ảnh. | QĐ 2760 → Phụ lục 9: Cân nặng hiệu chỉnh → Mục 2: Cân nặng chống sốc ở người lớn → Bảng dành cho nữ | `pl9-2` | người lớn, nữ, chiều cao, cân nặng | Bảng dành cho nữ ở mục người lớn nằm ở đâu trong Phụ lục 9? |

Hai bảng ở mục 2 được giữ dưới dạng ảnh gốc. Câu hỏi mẫu kiểm tra khả năng tìm đúng ảnh theo tiêu đề. Việc truy vấn từng ô trong hai ảnh cần thêm bước nhận dạng cấu trúc bảng và kiểm tra kết quả trích xuất.

## Liên kết cha và con

```text
QĐ 2760 / Phụ lục 9
├── pl9-1 · Mục 1 / Trẻ em dư cân hoặc béo phì
│   ├── pl9-1-text  · Đoạn lưu ý
│   └── pl9-1-table · Bảng tra
└── pl9-2 · Mục 2 / Người lớn
    ├── pl9-2-fig-01 · Bảng dạng ảnh dành cho nam
    └── pl9-2-fig-02 · Bảng dạng ảnh dành cho nữ
```

Ví dụ, nếu tìm thấy bảng `pl9-1-table`, hệ thống có thể dùng mục cha `pl9-1` để lấy thêm đoạn lưu ý `pl9-1-text`. Hai mục cha lưu mã tài liệu, đường dẫn đề mục và liên kết đến chunk con. Mẫu trích dẫn theo phụ lục và mục. Chưa xác nhận số trang in.

## Các điểm cần chốt trước khi chạy cả bộ

1. Với bảng nhỏ, giữ nguyên bảng cùng tiêu đề cột. Khi bảng dài cần chia, lặp tiêu đề cột và giữ từng dòng nguyên vẹn.
2. Chốt khi nào truy xuất kèm đoạn lưu ý qua liên kết mục cha và khi nào nên trích xuất từng ô từ bảng dạng ảnh.
3. Giữ riêng **loại dữ liệu** (đoạn văn, bảng, hình) và **trạng thái phân loại nội dung** (đã phân loại rõ hoặc chưa phân loại). Nhãn Nam/Nữ dùng để phân biệt nguồn ảnh. Phân loại nội dung theo danh mục chuyên môn cần được xác nhận riêng.
4. Duyệt bộ từ khóa và câu hỏi mẫu trước khi đưa vào pipeline tự động. Mẫu này dùng để duyệt cách chia và metadata, chưa nhập DB hoặc đánh giá chất lượng retrieval.
