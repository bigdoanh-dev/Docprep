# Kiểm tra bộ kiểm tầng B (bước 15) bằng cách cài lỗi

26 câu trả lời tầng B thật (C3) được chấp nhận, mỗi câu cài một loại lỗi; bộ kiểm thật (Haiku, check_v1) chạy lại.

| Loại lỗi | Ai phải bắt | Số ca | Bắt được |
|---|---|---|---|
| clean | không ai (phải cho qua) | 26 | chặn nhầm 4/26 |
| drop_claim | code | 26 | 26/26 |
| number_changed | code hoặc NLI | 26 | 26/26 |
| answer_not_first | code | 20 | 20/20 |
| meaning_flip | NLI | 11 | 8/11 |
| fabricated_addition | code (trích dẫn) | 26 | 26/26 |
| misquoted_addition | NLI | 10 | 10/10 |

## Lỗi lọt qua (3)

- [meaning_flip] Tiêu chí về gan và tiểu: gan to > 2cm dưới bờ sườn và tiểu ít luôn là dấu hiệu cảnh báo.
- [meaning_flip] Bước 2: Phân độ theo mức huyết áp đo được; khi huyết áp tâm thu và tâm trương ở các mức khác nhau, luôn luôn lấy mức cao hơn để phân độ.
- [meaning_flip] Chẩn đoán xác định thương hàn ở trẻ em dựa trên cả phần lâm sàng và phần xét nghiệm.
