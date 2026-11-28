# Gắn nhãn, mở rộng danh mục và release trình diễn (27/11/2026)

Tiếp theo [rechunk-followup.md](rechunk-followup.md). Môi trường: DB biên tập thử nghiệm `content_rechunk_review` và runtime Phase 1 local.

## 1. Gắn nhãn đề xuất

| Nguồn | Số chunk | Cách làm |
|---|---:|---|
| Kế thừa nhãn cũ (`legacy_exact`) | 403 | `app.content.tagger`, khớp đúng nội dung và hash với chunk trong `data.zip` |
| Gemini 4 Neon qua Antigravity (`manual_chat`) | 919 | `app.content.manual_tagging export` chia lô 40 chunk kèm prompt; người vận hành chạy trong ứng dụng chat; `import` kiểm tra từng nhãn như tagger API rồi lưu đề xuất |
| Claude hỗ trợ (`manual_review_assist`, `expert_assist_correction`) | 45 + 172 bản sửa | Gắn nốt chunk còn lại và sửa nhãn lệch theo quy tắc từng bài |

Prompt `yhdp-content-tags-v3` gồm danh mục vấn đề có mô tả và rubric YHDP (thiếu hai phần này, mô hình gắn 19/29 chunk lâm sàng vào vấn đề cộng đồng 1–2). `too_thin` bỏ qua chunk chỉ lặp tiêu đề hoặc ô biểu mẫu. Đánh giá sơ bộ so với 39 nhãn tham chiếu do AI gắn: vấn đề chính trùng 85%, Cohen's kappa 0,81. Đây không phải đánh giá bằng nhãn chuyên gia.

```powershell
# Từ backend, CONTENT_DATABASE_URL trỏ DB biên tập
.\.venv\Scripts\python.exe -m app.content.manual_tagging export <data.zip> --revision <id> ... --taxonomy <version> --output <thư mục mới>
.\.venv\Scripts\python.exe -m app.content.manual_tagging import <data.zip> --export <thư mục> --answers <thư mục>\answers --source "<model (công cụ)>" [--apply]
```

## 2. Vấn đề nội bộ ngoài QĐ 51

`app/content/taxonomy_ext.py`, áp dụng bằng `cli taxonomy-extend --base <version> --extension <id>` (tạo phiên bản danh mục mới, nhãn cũ giữ phiên bản cũ):

| Extension | Vấn đề | Đề mục |
|---|---|---|
| `noi-bo-dich-te-thong-ke-v1` | 55 Đo lường sức khỏe, 56 Thiết kế nghiên cứu, 57 Thống kê y sinh, 58 Suy luận nhân quả/sàng tuyển | 9 (mới) |
| `noi-bo-benh-truyen-nhiem-bo-sung-v1` | 59 Uốn ván, 60 Nhiễm trùng da và mô mềm nặng | 4 |

Các vấn đề này có `internal: true`, không thuộc QĐ 51, và chưa có mã năng lực trong runtime.

## 3. Duyệt và loại

Quyết định do người vận hành ghi bằng tài khoản reviewer, chính sách `human-v1`, lý do ghi rõ "duyệt với hỗ trợ của AI để trình diễn; chưa có thẩm định của chuyên gia y khoa". 1.369 chunk được xác nhận nhãn và duyệt nội dung; 126 chunk (mục lục, tài liệu tham khảo, OCR vỡ, danh mục chữ viết tắt) bị từ chối nội dung. Khi có chuyên gia, cần duyệt lại theo quy trình thật.

## 4. Mapping và release

- Mapping `yhdp-qd51-runtime-v1`: vấn đề 1–54 → `CI-01`…`CI-54`; miền 1.1…4.3 → thành phần năng lực 1…13.
- `publication.approved_mapping` tìm mapping đã duyệt theo payload danh mục (`sha256`), nên nhãn đã duyệt trên phiên bản danh mục chưa có mapping vẫn phát hành được; hai mapping đã duyệt khác nhau cho cùng payload bị từ chối.
- `cli taxonomy --mapping <file> --base <version>` gắn mapping cho đúng phiên bản; `cli export --chunks-file` nhận danh sách chunk dài.
- Release `yhdp-rechunk-demo-v1`: 942 chunk chỉ dùng vấn đề 1–54, đã publish và activate trên kênh `local`. Thu hồi bằng `publisher revoke --version yhdp-rechunk-demo-v1 --channel local --reason ...`.

Còn lại: mã năng lực runtime cho 55–60 (427 chunk), mở học phần G2/G4/G6 để trình diễn, provider sinh câu trả lời, chỉ mục embedding `bge-m3`. Số trang cho chunk OCR: xong ngày 28/11, xem mục "Số trang cho tài liệu OCR" bên dưới.

## Số trang cho tài liệu OCR (28/11/2026)

**Bảng trang.** `app/content_tools/page_maps.py` ánh xạ "ảnh thứ N trong file Word" sang số trang in. Bảng gắn theo sha256 của đúng file gốc.

| Tài liệu | Trang thân sách | Phần đầu sách |
|---|---|---|
| Ngộ độc (`ngodoc-pages-v1`) | ảnh 8–228 → tr. 1–221 (trừ 7) | ảnh 1–7 không có số |
| Dịch tễ (`dtch-pages-v1`) | ảnh 18–234 → tr. 1–217 (trừ 17) | ảnh 4–16 → iii–xv |

**Cách kiểm tra.**
- OCR phần đầu và chân của mọi ảnh. Mọi ảnh đọc được số đều khớp quy tắc: ngộ độc 218/221, dịch tễ 211/217.
- Các ảnh không đọc được số đã được xem bằng mắt: ngộ độc ảnh 54, 147, 149 in số 47, 140, 142; dịch tễ ảnh 33, 83, 123, 143, 161, 193 là trang trắng giữa các chương.
- Đã xem thêm vài trang mẫu để đối chiếu số trang với nội dung chunk.

**Áp dụng.**
- Rechunk từ pipeline `yhdp-original-rechunk.v4` tự điền `printed_pages` vào location.
- Với chunk đã duyệt trước đó, location nằm trong hash nội dung nên không được sửa. Khi xuất release, `export` thêm `page_map: {printed_pages, version}` bên cạnh chunk (manifest có hash). `publish` dùng nó để đặt `passage.page_start`.
- Chat trích "tr. N" qua `page_start` như sẵn có.

**Release.**
- `yhdp-rechunk-demo-v2` gồm đúng 942 chunk, nội dung và nhãn của v1, thêm số trang cho 455 chunk OCR (ngộ độc 381, dịch tễ 74).
- Đã publish và activate trên kênh `local` thay cho v1.
- Quay lại v1: `publisher activate --version yhdp-rechunk-demo-v1 --channel local --reason ...`.

