# Rerank bằng LLM (anthropic)

50 câu trong phạm vi, 0 ngoài phạm vi; 0 lượt chấm lỗi. Nhãn silver do Claude Haiku gắn: reranker Haiku được lợi một phần.

| Thứ tự | Hit@1 | Hit@5 | MRR@10 |
|---|---|---|---|
| RRF hiện tại | 48% | 84% | 0.65 |
| Sau rerank | 98% | 100% | 0.99 |

## Theo kiểu câu hỏi

| Kiểu | Số câu | Đoạn đúng trong 30 đoạn lấy về | Hit@5 RRF | Hit@5 sau rerank | Bị cổng chặn nhầm (≥2) |
|---|---|---|---|---|---|
| dong_nghia | 10 | 100% | 90% | 100% | 0 |
| gian_tiep | 11 | 100% | 55% | 100% | 0 |
| khong_dau | 10 | 100% | 90% | 100% | 0 |
| tu_khoa | 8 | 100% | 100% | 100% | 0 |
| viet_tat | 11 | 100% | 91% | 100% | 0 |

## Cổng theo điểm cao nhất (0–3)

Bộ này không có câu ngoài phạm vi.

| Cho qua khi điểm cao nhất ≥ | Câu hợp lệ bị chặn nhầm | Câu ngoài phạm vi bị chặn đúng |
|---|---|---|
| 1 | 0/50 | 0/0 |
| 2 | 0/50 | 0/0 |
| 3 | 1/50 | 0/0 |

Thời gian mỗi lượt rerank: trung vị 5.6 giây, chậm nhất 9.4 giây.

Câu RRF có đoạn đúng trong top 5 nhưng rerank làm rớt: 0
