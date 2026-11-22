# Retrieval trên bộ silver

50 câu trong phạm vi, 0 câu ngoài phạm vi. Nhãn do model gắn (pooling), chưa có người duyệt.

## Câu trong phạm vi

| Cách tìm | Hit@1 | Hit@5 (chat gửi 5) | Hit@30 (trần cho reranker) | MRR@10 |
|---|---|---|---|---|
| Kết hợp (bge-m3 + full text, RRF) | 48% | 84% | 100% | 0.65 |
| Chỉ từ khoá (xếp hạng, không ngưỡng) | 70% | 90% | 98% | 0.79 |

Đường chỉ từ khoá với ngưỡng min_score (khi không có model): gửi đúng đoạn ở 74% câu; không gửi gì ở 16% câu.

### Theo kiểu câu hỏi (kết hợp)

| Nhóm | Số câu | Hit@5 | Hit@30 |
|---|---|---|---|
| dong_nghia | 10 | 90% | 100% |
| gian_tiep | 11 | 55% | 100% |
| khong_dau | 10 | 90% | 100% |
| tu_khoa | 8 | 100% | 100% |
| viet_tat | 11 | 91% | 100% |

### Theo tài liệu (kết hợp)

| Nhóm | Số câu | Hit@5 | Hit@30 |
|---|---|---|---|
| Hướng dẫn chẩn đoán và điều trị một số bệnh truyền nhiễm | 17 | 94% | 100% |
| Hướng dẫn chẩn đoán, điều trị sốt xuất huyết Dengue | 17 | 71% | 100% |
| Hướng dẫn chẩn đoán, điều trị và quản lý một số bệnh không lây nhiễm tại trạm y tế xã | 16 | 88% | 100% |

## Câu ngoài phạm vi

- Kết hợp: gửi 5 đoạn sang model ở — câu (chưa có cổng đủ bằng chứng).
- Chỉ từ khoá: gửi ít nhất 1 đoạn ở — câu.
- Bị chặn trước khi tìm (pregate / hỏi lại): 0 câu.

## Dữ liệu cho cổng đủ bằng chứng

Một ngưỡng duy nhất trên điểm này tách câu trong và ngoài phạm vi tốt đến đâu (chưa có reranker).

| Điểm | TB trong phạm vi | TB ngoài phạm vi | AUC | Ngưỡng tốt nhất | Đúng ở ngưỡng đó |
|---|---|---|---|---|---|
| Cosine bge-m3 cao nhất | — | — | — | — | — |
| Điểm RRF cao nhất | — | — | — | — | — |

## Câu trong phạm vi mà kết hợp không đưa đoạn đúng vào top 5 (8)

- `HARD-005` [gian_tiep] Sốt xuất huyết dengue sang ngày thứ 3-7, hematocrit tăng bao nhiêu phần trăm so với lúc đầu thì được coi là máu đặc lại, cần lo? → hạng 11
- `HARD-015` [gian_tiep] Người vừa bị tăng huyết áp vừa đái tháo đường mà nước tiểu có protein thì nên chọn nhóm thuốc nào để bảo vệ thận lâu dài? → hạng 6
- `HARD-023` [gian_tiep] Phụ nữ đang mang thai bị sốt rét kháng thuốc thì trong 3 tháng đầu nên tránh dùng thuốc nào? → hạng 6
- `HARD-024` [viet_tat] SXHD sốc có xuất huyết, khi nào nên cân nhắc dùng Vit K? → hạng 12
- `HARD-028` [gian_tiep] Ở trạm y tế xã, người tăng huyết áp còn trẻ hoặc đang mang thai thì có cần đưa lên tuyến trên không? → hạng 7
- `HARD-030` [khong_dau] sxh dengue giai doan hoi phuc tieu cau va bach cau cai nao ve binh thuong truoc → hạng 6
- `HARD-033` [gian_tiep] Người lớn đang bị sốt xuất huyết Dengue nên ăn mấy lần trong ngày để dạ dày đỡ phải làm việc nặng? → hạng 13
- `HARD-048` [dong_nghia] dengue neonate, mẹ bị dengue thì con hay sốt vào ngày thứ mấy sau đẻ, cần theo dõi kiểu gì? → hạng 7
