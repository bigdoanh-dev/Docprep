# Rerank bằng LLM (anthropic)

86 câu trong phạm vi, 25 ngoài phạm vi; 0 lượt chấm lỗi. Nhãn silver do Claude Haiku gắn: reranker Haiku được lợi một phần.

| Thứ tự | Hit@1 | Hit@5 | MRR@10 |
|---|---|---|---|
| RRF hiện tại | 38% | 81% | 0.56 |
| Sau rerank | 92% | 100% | 0.96 |

## Cổng theo điểm cao nhất (0–3)

AUC 1.00.

| Cho qua khi điểm cao nhất ≥ | Câu hợp lệ bị chặn nhầm | Câu ngoài phạm vi bị chặn đúng |
|---|---|---|
| 1 | 0/86 | 13/25 |
| 2 | 0/86 | 25/25 |
| 3 | 1/86 | 25/25 |

Thời gian mỗi lượt rerank: trung vị 4.3 giây, chậm nhất 9.2 giây.

Câu RRF có đoạn đúng trong top 5 nhưng rerank làm rớt: 0
