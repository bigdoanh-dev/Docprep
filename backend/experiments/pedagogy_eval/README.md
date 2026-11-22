# Đánh giá sư phạm và kiểm tra bộ kiểm tầng B

Trả lời hai nhận xét của reviewer:
- cách giảng dạy chưa thuyết phục;
- bước 15 (kiểm tầng B) chưa rõ.

Cả hai chỉ cần API key.

## Thiết kế

Mỗi câu hỏi trong `cases.yaml` đi qua 3 bước:
1. Chạy tìm kiếm như trong chat: kết hợp, rồi rerank.
2. Chạy tầng A một lần.
3. Với mỗi hồ sơ người học giả lập, tầng B trình bày **cùng các ý đã kiểm** theo 4 điều kiện:

| Điều kiện | Là gì |
|---|---|
| C0 | Không cá nhân hoá (tầng A) |
| C1 | Bản cũ: mastery 0–1 chia 3 mức. Bản sao đóng băng nằm ở `legacy/` |
| C2 | Bản mới, **chỉ Bloom**: hồ sơ Bloom theo năng lực và cách giảng theo mức cần hướng tới |
| C3 | Bản mới, **Bloom + scaffolding**: nối kiến thức tiên quyết, chỉ ra chỗ nhầm, câu tự kiểm tra |

Vì tầng A dùng chung, mọi khác biệt giữa các điều kiện đều đến từ tầng B. Riêng C2 so với C3 cho biết scaffolding đóng góp bao nhiêu.

Bốn hồ sơ người học:

| Hồ sơ | Mô tả |
|---|---|
| P1 | Vững Nhớ, kẹt ở Hiểu; yếu kiến thức nền; có một chỗ từng nhầm |
| P2 | Đang ở Vận dụng; có một chỗ từng nhầm |
| P3 | Đang ở Phân tích; có một chỗ từng nhầm |
| P4 | Vững tới Đánh giá |

Ngân hàng câu hỏi thật chưa có câu nào thuộc các chương này. Vì vậy chỗ nhầm của mỗi câu hỏi được model viết thành một câu trắc nghiệm kiểu ngân hàng (một phương án sai và lý do nó sai), dựa trên chính các đoạn tài liệu.

## Rubric (`judge.py`)

Điểm từ 1 đến 5, để trống khi không áp dụng:

| Chiều | Đo gì |
|---|---|
| bloom_target | Giảng đúng mức cần hướng tới: khái niệm, ý nghĩa, các bước, cách phân biệt, hay tiêu chí |
| scaffolding | Hỗ trợ phù hợp với hồ sơ. Với người học giỏi mà hỗ trợ quá nhiều thì bị trừ điểm (tức là có giảm dần hỗ trợ) |
| prerequisite | Có nối với kiến thức nền còn yếu không (chỉ khi hồ sơ có nêu) |
| misconception | Có chỉ ra chỗ nhầm và điều đúng không (chỉ khi hồ sơ có nêu) |
| actionability, coherence, tone | Lấy từ MRBench (Maurya và cộng sự, 2025) |
| faithfulness | Mọi thông tin đều có trong đoạn tài liệu |

Giám khảo không biết câu trả lời thuộc điều kiện nào.
- **Gemini Flash-Lite** khác họ với model viết câu trả lời (Haiku), nên ít thiên vị hơn. Đây là giám khảo chính.
- **Haiku** cũng chấm để so sánh.

Cả hai đều không phải chuẩn cuối cùng. `human.py sheet` xuất 20 câu trả lời (5 câu mỗi điều kiện, đã ẩn điều kiện) để người trong nhóm tự chấm theo cùng rubric. `human.py agree` tính mức khớp giữa người chấm và từng giám khảo.

## Kiểm bước 15 (`faults.py`)

Lấy các câu trả lời tầng B thật đã được chấp nhận, rồi trong mỗi câu cài **một** lỗi. Sau đó chạy lại bộ kiểm thật:

| Loại lỗi | Bộ phận phải bắt |
|---|---|
| clean (không cài lỗi) | Phải cho qua. Dùng để đo tỉ lệ chặn nhầm |
| drop_claim, number_changed, answer_not_first | Code |
| fabricated_addition (trích dẫn không có trong tài liệu) | Code, ở bước kiểm trích dẫn |
| meaning_flip (đổi nghĩa tinh vi, giữ nguyên số) | NLI |
| misquoted_addition (trích dẫn có thật nhưng câu nói điều khác) | NLI |

Các lỗi do model viết thì dùng Gemini, khác họ với Haiku là model làm NLI.

## Chạy

Chạy trong container chat. Gửi code bằng tar giống `../retrieval_eval/README.md`. Trên Git Bash thêm `MSYS_NO_PATHCONV=1`.

```sh
python run.py --out /tmp/re/out            # sinh câu trả lời 4 điều kiện
python judge.py /tmp/re/out/<lượt>         # Gemini và Haiku chấm
python faults.py /tmp/re/out/<lượt>        # kiểm bước 15
python summarize.py /tmp/re/out/<lượt>     # tóm tắt, ra summary.md
python human.py sheet /tmp/re/out/<lượt>   # bảng 20 câu cho người chấm
python human.py agree /tmp/re/out/<lượt>   # sau khi người chấm đã điền
```

Mọi nhãn đầu vào đều do máy làm và **chưa được chuyên gia duyệt** (quyết định ngày 2026-11-23):
- Bloom 6 mức: `../bloom_labels/`
- Bản đồ tiên quyết: `../prerequisites/`, `config/prerequisites.yaml`

## Kết quả (2026-11-23, lượt `out/20261122-174846`)

7 câu hỏi × 4 hồ sơ giả lập × 4 điều kiện = 112 câu trả lời. Câu Q6 (viêm màng não) bị bỏ vì tầng A không trả lời được.
Mô hình viết câu trả lời: Claude Haiku. Giám khảo: Gemini Flash-Lite (102/112 câu chấm được, 10 câu lỗi giới hạn tốc độ) và Haiku (112/112).

**Tầng B có chạy được không** (số câu dùng bản cá nhân hoá, trên 28 lượt mỗi điều kiện): C1 23, C2 25, C3 26. Các lượt còn lại quay về tầng A vì `number_changed` hoặc `not_entailed`.

**Điểm rubric** (1–5, trung bình, cả hai giám khảo cho cùng thứ tự):

| | bloom_target | scaffolding | actionability | misconception | coherence | faithfulness |
|---|---|---|---|---|---|---|
| Gemini: C0 không cá nhân hoá | 2.56 | 3.30 | 3.41 | 4.00 | 4.52 | 4.96 |
| Gemini: C1 bản cũ | 2.65 | 3.38 | 3.62 | 4.37 | 4.54 | 5.00 |
| Gemini: C2 chỉ Bloom | 3.48 | 3.96 | 4.22 | 4.17 | 4.57 | 5.00 |
| Gemini: C3 Bloom + scaffolding | **3.85** | **4.31** | **4.46** | **4.74** | 4.77 | 4.96 |
| Haiku: C0 | 1.89 | 2.07 | 2.11 | 1.95 | 3.89 | 4.75 |
| Haiku: C1 | 2.04 | 2.04 | 2.07 | 2.05 | 3.82 | 4.79 |
| Haiku: C2 | 2.39 | 2.57 | 2.36 | 2.10 | 3.32 | 4.79 |
| Haiku: C3 | **2.54** | **3.00** | **3.14** | **3.24** | 3.46 | 4.71 |

Đọc kết quả:
- Bản cũ (C1) gần như không khác không cá nhân hoá (C0). Đây là điều reviewer nói.
- Thêm Bloom (C2) làm tăng rõ `bloom_target`, `scaffolding`, `actionability`.
- Thêm scaffolding (C3) tăng thêm trên cả 4 chiều đó, rõ nhất ở `misconception`.
- `faithfulness` giữ nguyên: thêm dạy không làm sai nội dung.
- Haiku chấm `coherence` của C2 và C3 thấp hơn C0 (3.32 và 3.46 so với 3.89): bản có cấu trúc dạy đọc kém liền mạch hơn. Gemini không thấy chênh lệch này.
- Hồ sơ người học vững (P4): lợi ích nhỏ nhất. `bloom_target` vẫn là chiều thấp nhất (Gemini C3 2.57).

**Giới hạn, cần nói rõ:**
- Rubric hỏi "có giảng đúng mức Bloom cần hướng tới không", mà C0 và C1 không được biết mức đó. So sánh này cho thấy hệ thống **làm đúng điều nó được thiết kế để làm**. Nó chưa chứng minh người học **học tốt hơn**. Chỉ số kết quả học ("làm đúng câu cùng năng lực ở lần sau") cần người học thật.
- Hồ sơ là giả lập, chỉ 7 câu hỏi, và chiều `prerequisite` chỉ áp dụng cho 7 câu của P1. Các con số ở chiều này không đáng tin.
- Cả hai giám khảo đều là model. Chưa ai chấm tay: `out/20261122-174846/human_sheet.csv` có 20 câu (5 câu mỗi điều kiện, ẩn điều kiện) chờ người trong nhóm chấm, rồi chạy `human.py agree` để so với giám khảo.
- Nhãn Bloom 6 mức và bản đồ tiên quyết đều do máy làm, chưa chuyên gia duyệt.

## Kiểm bước 15 bằng cách cài lỗi (`faults.md`)

26 câu trả lời tầng B thật được chấp nhận, mỗi câu cài một loại lỗi rồi chạy lại bộ kiểm thật (code + NLI bằng Haiku):

| Loại lỗi | Ai bắt | Bắt được |
|---|---|---|
| Bỏ một ý | code | 26/26 |
| Đổi một con số | code hoặc NLI | 26/26 |
| Ý trả lời trực tiếp không đứng đầu | code | 20/20 |
| Thêm câu bịa kèm trích dẫn không có trong tài liệu | code | 26/26 |
| Thêm câu có trích dẫn thật nhưng câu nói điều khác | NLI | 10/10 |
| Đổi nghĩa tinh vi, giữ nguyên số | NLI | 8/11 |
| Không cài lỗi (phải cho qua) | — | chặn nhầm 4/26 câu |

Ba ca đổi nghĩa lọt qua. Theo cách đọc của tôi, cả ba gần như không đổi nghĩa so với ý gốc (ví dụ thêm "luôn luôn" vào một quy tắc vốn luôn đúng), nên có thể không phải lỗi thật; tôi chưa đối chiếu từng ca với tài liệu gốc.
Hạn chế: chỉ 11 ca đổi nghĩa hợp lệ (15 ca khác bị loại vì model sinh lỗi tự báo không đổi được nghĩa, hoặc gọi lỗi), và chính model đó tự báo nghĩa có đổi hay không. Con số này cho thấy bộ kiểm không yếu đến mức vô dụng, chứ không chứng minh nó bắt được mọi lỗi.

Kết quả này dẫn tới một thay đổi trong `adapt.py`: câu nhắc lại bị NLI từ chối được thay bằng chính ý đã kiểm của nó, thay vì bỏ cả bản trình bày. Khi quá nửa số câu bị từ chối thì dùng bản tầng A.
