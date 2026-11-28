# Báo cáo đánh giá rechunk, gắn nhãn và Chat (27/11/2026)

Người thực hiện: Nguyễn Hoàng Dũng, với hỗ trợ của AI (Claude Code). Môi trường: máy local, Phase 1 dev.
Dữ liệu chỉ gồm corpus công khai (hướng dẫn Bộ Y tế, sách dịch tễ) và câu hỏi đánh giá do model tạo; không có dữ liệu người học thật.

## 1. Tình trạng theo các yêu cầu của anh Khanh (25/11)

| Yêu cầu | Trạng thái | Ghi chú ngắn |
|---|---|---|
| Chuẩn hóa OCR → văn bản có cấu trúc → gắn heading | ✅ Xong | 0/1.369 chunk còn "Ảnh trang N"; 100% chunk đã duyệt có `section_path` và `contextual_header` theo chương/mục. Sách ngộ độc khớp 35/35 chủ đề trong mục lục. |
| Phân biệt "đã import" với "đủ điều kiện cho Chat" | ✅ Xong | Chat chỉ dùng chunk đã xác nhận nhãn, đã duyệt nội dung và nằm trong release. Release `yhdp-rechunk-demo-v1` có 942 chunk, đang bật trên kênh `local`. |
| Automated tagging (nhãn cũ + API free bậc cao + local fallback) | ✅ Xong về kết quả, có giới hạn | Mọi chunk nội dung đều có nhãn đề xuất; 119 chunk không phải nội dung (mục lục, tài liệu tham khảo…) bị loại. Nguồn nhãn: 403 nhãn cũ, 919 Gemini 4 Neon, phần còn lại Claude bổ sung hoặc sửa. Gemini chạy theo lô qua Antigravity vì API free chỉ cho 20 lượt/ngày. Fallback Ollama có trong code nhưng chưa chạy thật. |
| Đo Cohen's kappa | 🟡 Tạm: đo giữa hai model | κ = **0,875** giữa Gemini và Claude trên 100 chunk (mục 2). Chưa có nhãn chuyên gia làm ground truth. |
| Đánh giá trên Chat pipeline thật (hybrid + rerank) | 🟡 Bản sơ bộ đã chạy | Chạy 146 câu qua API Chat thật: bge-m3 chạy tạm trên máy, Gemini lo rerank và sinh câu trả lời (mục 3). Cần chạy lại khi server lab hoạt động, và cần thêm câu hỏi cho tài liệu OCR. |

Ngoài 5 yêu cầu trên, đã làm thêm:
- Mở học phần G2, G4, G6 với 4 bài học và 20 câu hỏi, trích từ hướng dẫn Bộ Y tế. Nội dung do AI soạn để trình diễn, chưa thẩm định chuyên môn.
- Thêm 6 vấn đề nội bộ 55–60 ngoài QĐ 51.

## 2. Độ đồng thuận nhãn: Gemini và Claude

**Cách làm**
- Lấy ngẫu nhiên 100 chunk đã có nhãn Gemini 4 Neon (seed 20261128), chia theo tài liệu: ngộ độc 27, dịch tễ 27, SXHD 20, bệnh truyền nhiễm 20, THA/ĐTĐ 6. Chỉ lấy chunk văn bản dài 150–1.500 ký tự.
- Claude gắn nhãn mù, chỉ nhìn nội dung và vị trí chunk, không xem nhãn Gemini. Sau đó mới so sánh.
- So trên vấn đề chính (60 lựa chọn) và trên đề mục.

**Kết quả**

| Chỉ số | Giá trị |
|---|---|
| Vấn đề chính: tỷ lệ đồng ý | 89/100 |
| Vấn đề chính: Cohen's κ | **0,875** (mức đồng thuận ngẫu nhiên kỳ vọng 0,12) |
| Đề mục: tỷ lệ đồng ý / κ | 95/100 · κ = 0,93 |
| Nhãn chính của Claude nằm trong nhãn chính hoặc phụ của Gemini | 97/100 |

Theo tài liệu: ngộ độc 26/27, dịch tễ 25/27, SXHD 19/20, bệnh truyền nhiễm 15/20, THA/ĐTĐ 4/6.

**Chỗ hai model lệch nhau (11 chunk)**
- **"21 Sốt" và "22 Sốt và phát ban"** (3 chunk sốt mò): Gemini chọn 22, Claude chọn 21. Ranh giới giữa hai vấn đề này cần chuyên gia quyết.
- **"55 Đo lường bệnh tật" và "58 Suy luận nhân quả"** (2 chunk sách dịch tễ).
- Các cặp còn lại, mỗi cặp 1 chunk:
  - ngộ độc cấp (6) / ngộ độc thực phẩm (17);
  - THA (39) / ĐTĐ (38) / bệnh không lây nhiễm (2);
  - SXHD (22) / suy hô hấp (8) cho phụ lục suy hô hấp của QĐ 2760;
  - cúm: chuyên mục bệnh dịch (1) / viêm hô hấp trên (24).
- 1 chunk uốn ván: Gemini gắn lúc chưa có vấn đề 59 nên không thể chọn 59. Bỏ chunk này ra thì kết quả gần như không đổi (89/99).

**Giới hạn: không được coi đây là độ chính xác**
- Đây là đồng thuận **giữa hai model**, không phải so với ground truth của con người. Hai model có thể cùng sai.
- Hai bên dùng cùng danh mục và rubric. Rubric do Claude soạn, nên hai bên không hoàn toàn độc lập.
- Bước tiếp theo đúng nghĩa: nhờ sinh viên y hoặc giảng viên gắn nhãn mù khoảng 100 chunk. File Excel mẫu đã có ở `ALPHAV1/kappa-thu/`.

## 3. Đánh giá sơ bộ trên Chat pipeline thật

**Cấu hình (tạm thời, chỉ dev)**
- Provider: `google`, model `gemini-3.5-flash-lite`, dùng cho cả rerank và sinh câu trả lời.
- Embedding: bge-m3 chạy trong container Ollama tạm trên GPU GTX 1650 của máy, vì server lab (192.168.88.15) không truy cập được.
- Đã embed 942/942 passage của release `yhdp-rechunk-demo-v1`.
- Retrieval theo cấu hình hiện tại: hybrid (từ khóa + vector, RRF) lấy 30 đoạn → Gemini chấm 0–3 → giữ 5 đoạn tốt nhất. Đoạn tốt nhất dưới 2 điểm thì từ chối vì không đủ bằng chứng.
- Câu hỏi gửi qua API Chat thật (SSE) bằng tài khoản đánh giá riêng `eval.chat`. Kết quả đọc từ trace lưu trong DB.
- Script chấm là `experiments/retrieval_eval/chat_release_eval.py` (đã commit), thêm phần tự đăng nhập lại khi token hết hạn.

**Bộ câu hỏi**
- Gồm 146 câu: 121 câu trong phạm vi (76 câu silver, 45 câu khó) và 25 câu ngoài phạm vi.
- Đáp án đúng được gắn lại sang release mới bằng câu trích dẫn nguyên văn. Có 15 câu bị bỏ: 10 câu vì câu trích quá ngắn, 5 câu vì câu trích không còn khớp nguyên văn sau khi chunk lại.
- Câu hỏi và nhãn do model tạo (bộ silver), chỉ thuộc **3 văn bản Word**. Bộ này chưa có câu nào về 2 tài liệu OCR.

**Kết quả** (tính trên các lượt hoàn thành; 9 lượt lỗi được nêu riêng ở dưới)

| Chỉ số | Trong phạm vi (n=116) | Silver | Câu khó |
|---|---|---|---|
| Đoạn đúng có trong 30 ứng viên | 98,3% | 98,6% | 97,6% |
| Đoạn đúng trong top 5 **trước** rerank (hybrid) | 75,9% | 73,0% | 81,0% |
| Đoạn đúng trong top 5 **sau** rerank | **98,3%** | 98,6% | 97,6% |
| Câu trả lời trích đúng đoạn nguồn | **94,0%** | 95,9% | 90,5% |
| Độ chính xác trích dẫn (tỷ lệ trích dẫn đúng) | 88,2% | 87,9% | 88,8% |
| Trạng thái đúng (trả lời / từ chối) | 97,4% | 98,6% | 95,2% |

- Câu ngoài phạm vi: 21/21 lượt hoàn thành bị từ chối đúng. Trong đó 20 lượt trả "không đủ bằng chứng", 1 lượt bị từ chối theo quy tắc an toàn.
- Mỗi lượt gọi model khoảng 3 lần. Thời gian trung vị 4,4 giây, p90 5,8 giây.

**So với số đo trước đây**
- Đo từ vựng offline (25/11, 80 câu, không qua Chat): bộ cũ 45/80 (56%), bộ mới 54/80 (68%), thêm từ khóa 55/80 (69%).
- Trên Chat thật với hybrid và rerank, bản mới đạt 98% ở top 5. Phần lớn mức tăng đến từ tìm theo nghĩa và rerank, không chỉ từ chunk mới.
- Chưa có A/B trên Chat thật với bộ chunk cũ, vì runtime chưa từng có release của bộ cũ để chạy cùng cấu hình. Muốn A/B đúng nghĩa cần publish bộ cũ thành một release riêng.

**Vấn đề phát hiện khi đánh giá**
1. **Bộ lọc quyền riêng tư chặn nhầm 9/146 lượt (6%).** Có 3/942 passage chứa chuỗi giống thông tin định danh:
   - "phần 4.1.2.1" bị nhận như địa chỉ IP;
   - "300.000-1000.000 đơn vị" bị nhận như số điện thoại;
   - một dãy năm trong sách dịch tễ.

   Chỉ cần một đoạn như vậy lọt vào 30 ứng viên là cả lượt bị chặn (`prompt_identifiers_blocked`), và người học chỉ thấy báo lỗi. Hướng sửa (cần nhóm thống nhất vì là module bảo mật):
   - (a) loại hoặc che riêng đoạn corpus vi phạm thay vì chặn cả lượt;
   - (b) thu hẹp mẫu IP/số điện thoại để không khớp số mục và liều thuốc.
2. **Chưa có số trang** (lúc đánh giá). 0/1.369 chunk có `printed_pages`, nên Chat chưa trích được số trang cho 2 tài liệu OCR. *Cập nhật 28/11: đã xong. Release `yhdp-rechunk-demo-v2` có số trang cho cả 455 chunk OCR (xem `tagging-and-demo-release.md`).*
3. **Khoảng trống trong bộ câu hỏi:** chưa có câu cho tài liệu OCR, nên đánh giá này chưa đo được phần anh Khanh lo nhất.

**Giới hạn của bản sơ bộ**
- Model sinh câu trả lời là Gemini Flash-Lite, không phải Qwen trên server lab. Kết quả có thể khác khi đổi model.
- Mới chấm khả năng tìm nguồn, trích dẫn và trả lời/từ chối. **Chưa chấm độ đúng nội dung câu trả lời**; việc đó cần người có chuyên môn.
- bge-m3 chạy trên máy cá nhân, đúng model và revision với server, nhưng đây không phải môi trường triển khai.

**Chạy lại khi server lab hoạt động**
1. Bật provider `ollama`, giữ `PHASE_ALLOW_UNVERIFIED_CORPUS=1` cho bản dev, rồi chạy `python -m app.phase_cli index --corpus-version yhdp-rechunk-demo-v1` trong container chat.
2. Chạy cùng `cases.json` bằng `chat_release_eval.py run` (hoặc `drive.py`), rồi so với `run-candidate.json` của lần này.
3. Bổ sung câu hỏi cho tài liệu ngộ độc và dịch tễ, và publish bộ chunk cũ thành release để chạy A/B.

## 4. Kiểm tra lại toàn bộ

| Hạng mục | Kết quả |
|---|---|
| Test backend đầy đủ (`backend/tests`, Postgres + pgvector) | **1.252 passed, 0 failed**, 97 skipped |
| Test rechunk (`tests_phase1/test_rechunk*.py`) | 20/20 passed |
| Frontend `tsc` và `oxlint` | Sạch |
| DB biên tập `content_rechunk_review` | 1.495 chunk: 1.369 đã xác nhận nhãn và duyệt, 126 bị loại, 0 chờ |
| Runtime Phase 1 | Release `yhdp-rechunk-demo-v1` ở trạng thái `ready`, đang bật kênh `local`, 942 passage hiển thị. Mở 4/8 học phần (G1, G2, G4, G6). Đã có chỉ mục bge-m3 942/942. |
| Git | Nhánh `feat/yhdp-corpus-rechunk`, commit mới nhất `0329af1`, khớp với remote |

Một test về pool kết nối (`test_review_fixes_4a`) từng lỗi một lần do canh thời gian. Chạy lại thì đạt.

*Cập nhật 28/11:* bộ `tests_phase1` (chạy trong stack Phase 1) đạt 118/119. Test lỗi là `test_ollama.py::test_index_and_hybrid_chat_are_durable_scoped_and_hash_pinned`: câu hỏi seed trả "không đủ bằng chứng" thay vì "đã trả lời". Test này lỗi y hệt trên commit `2d9dd7a` và `cb07326`, tức trước phần số trang, nên là lỗi có sẵn và cần tìm nguyên nhân riêng.

## 5. Việc còn lại, theo thứ tự ưu tiên

1. Sửa lỗi bộ lọc quyền riêng tư chặn nhầm (mục 3, vấn đề 1).
2. ~~Thêm số trang cho chunk OCR để trích dẫn theo trang.~~ Xong 28/11 (release v2).
3. Nhờ người có chuyên môn y gắn nhãn mù khoảng 100 chunk để có kappa đúng nghĩa. Đồng thời duyệt lại nội dung học phần G2/G4/G6 và các nhãn đã "duyệt với hỗ trợ AI".
4. Khi server lab hoạt động: chạy lại đánh giá Chat với Qwen và bge-m3 của server, thêm câu hỏi cho tài liệu OCR, và chạy A/B với bộ chunk cũ. Chạy thử luôn fallback Ollama của tagger.
5. Đưa vấn đề 55–60 vào runtime (core issue và competency node) để phát hành 427 chunk còn lại.
6. Đổi khóa Gemini, vì khóa hiện tại đã lộ trong chat.

## 6. Vị trí file (ngoài repo, không commit)

| File | Nội dung |
|---|---|
| `ALPHAV1/kappa-gemini-claude/mau-mu.json` | 100 chunk mẫu (không kèm nhãn) |
| `ALPHAV1/kappa-gemini-claude/gemini-nhan-goc.json`, `claude-nhan-mu.json` | Nhãn của hai model |
| `ALPHAV1/kappa-gemini-claude/ket-qua-kappa.json` | Kết quả kappa và danh sách chunk lệch |
| `ALPHAV1/chat-eval-gemini/cases.json` | 146 câu hỏi kèm đáp án trên release mới |
| `ALPHAV1/chat-eval-gemini/run-candidate.json` | Kết quả từng câu, kèm trace trước và sau rerank |
| `ALPHAV1/chat-eval-gemini/drive.py`, `compose.eval-gemini.yml` | Script chạy và cấu hình tạm để chạy lại |
| `ALPHAV1/kappa-thu/gan-nhan-thu-2-chunk.xlsx` | File Excel mẫu cho người gắn nhãn chuyên môn |
