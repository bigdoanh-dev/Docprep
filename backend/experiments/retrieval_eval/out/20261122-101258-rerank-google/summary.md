# Rerank bằng LLM (google)

79 câu trong phạm vi, 24 ngoài phạm vi; 8 lượt chấm lỗi.

| Thứ tự | Hit@1 | Hit@5 | MRR@10 |
|---|---|---|---|
| RRF hiện tại | 37% | 80% | 0.54 |
| Sau rerank | 96% | 100% | 0.98 |

## Cổng theo điểm cao nhất (0–3)

AUC 1.00.

| Cho qua khi điểm cao nhất ≥ | Câu hợp lệ bị chặn nhầm | Câu ngoài phạm vi bị chặn đúng |
|---|---|---|
| 1 | 0/79 | 23/24 |
| 2 | 0/79 | 24/24 |
| 3 | 0/79 | 24/24 |

Thời gian mỗi lượt rerank: trung vị 4.8 giây, chậm nhất 37.9 giây.

Câu RRF có đoạn đúng trong top 5 nhưng rerank làm rớt: 0
