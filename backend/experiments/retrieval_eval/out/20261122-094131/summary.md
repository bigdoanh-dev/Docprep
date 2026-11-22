# Retrieval trên bộ silver

86 câu trong phạm vi, 25 câu ngoài phạm vi. Nhãn do model gắn (pooling), chưa có người duyệt.

## Câu trong phạm vi

| Cách tìm | Hit@1 | Hit@5 (chat gửi 5) | Hit@30 (trần cho reranker) | MRR@10 |
|---|---|---|---|---|
| Kết hợp (bge-m3 + full text, RRF) | 38% | 81% | 100% | 0.56 |
| Chỉ từ khoá (xếp hạng, không ngưỡng) | 45% | 80% | 95% | 0.61 |

Đường chỉ từ khoá với ngưỡng min_score (khi không có model): gửi đúng đoạn ở 69% câu; không gửi gì ở 10% câu.

### Theo kiểu câu hỏi (kết hợp)

| Nhóm | Số câu | Hit@5 | Hit@30 |
|---|---|---|---|
| dinh_nghia | 16 | 69% | 100% |
| ly_do | 16 | 81% | 100% |
| phan_biet | 18 | 83% | 100% |
| quy_trinh | 18 | 89% | 100% |
| so_lieu | 18 | 83% | 100% |

### Theo tài liệu (kết hợp)

| Nhóm | Số câu | Hit@5 | Hit@30 |
|---|---|---|---|
| Hướng dẫn chẩn đoán và điều trị một số bệnh truyền nhiễm | 27 | 85% | 100% |
| Hướng dẫn chẩn đoán, điều trị sốt xuất huyết Dengue | 30 | 70% | 100% |
| Hướng dẫn chẩn đoán, điều trị và quản lý một số bệnh không lây nhiễm tại trạm y tế xã | 29 | 90% | 100% |

## Câu ngoài phạm vi

- Kết hợp: gửi 5 đoạn sang model ở 100% câu (chưa có cổng đủ bằng chứng).
- Chỉ từ khoá: gửi ít nhất 1 đoạn ở 28% câu.
- Bị chặn trước khi tìm (pregate / hỏi lại): 1 câu.

## Dữ liệu cho cổng đủ bằng chứng

Một ngưỡng duy nhất trên điểm này tách câu trong và ngoài phạm vi tốt đến đâu (chưa có reranker).

| Điểm | TB trong phạm vi | TB ngoài phạm vi | AUC | Ngưỡng tốt nhất | Đúng ở ngưỡng đó |
|---|---|---|---|---|---|
| Cosine bge-m3 cao nhất | 0.691 | 0.523 | 0.98 | 0.591 | 98% |
| Điểm RRF cao nhất | 0.031 | 0.030 | 0.66 | 0.025 | 78% |

## Câu trong phạm vi mà kết hợp không đưa đoạn đúng vào top 5 (16)

- `IN-002` [so_lieu] Trong sốc sốt xuất huyết kéo dài ở trẻ em, thuốc vận mạch nên chọn đầu tiên và liều truyền theo cân nặng là bao nhiêu? → hạng 7
- `IN-011` [dinh_nghia] Trong sốc sốt xuất huyết Dengue, ba rối loạn chuyển hóa cần theo dõi gồm toan máu, calci máu và đường máu được viết tắt thế nào? → hạng 8
- `IN-016` [dinh_nghia] Khi có người gần gũi với ca bệnh pest, thường dự phòng bằng kháng sinh nào và uống trong bao nhiêu ngày? → hạng 9
- `IN-017` [so_lieu] Khi hồi sức sốc do sốt xuất huyết Dengue, lượng nước tiểu nên đạt khoảng bao nhiêu ml/kg mỗi giờ? → hạng 28
- `IN-029` [phan_biet] Trong điều trị sốt xuất huyết Dengue, khi nào có thể ngừng dịch cao phân tử và chuyển sang truyền dịch điện giải, cần dựa vào các tiêu chí nào? → hạng 13
- `IN-031` [dinh_nghia] Trong bệnh truyền nhiễm, HIV là viết tắt của cụm từ nào, nghĩa là gì? → hạng 10
- `IN-033` [quy_trinh] Ở trạm y tế xã, nếu chỉ dùng một loại thuốc hạ huyết áp và tăng dần đến liều cao nhất mà vẫn chưa đạt mục tiêu thì phải xử trí thế nào? → hạng 7
- `IN-034` [phan_biet] Viêm màng não tăng bạch cầu ái toan do ký sinh trùng thường biểu hiện bằng những triệu chứng nào? → hạng 9
- `IN-035` [ly_do] Khi chuyển viện bệnh nhân sốt xuất huyết Dengue, phiếu tóm tắt cần ghi lại những chỉ số mạch, huyết áp hay nhịp thở nào để theo dõi diễn biến? → hạng 14
- `IN-038` [quy_trinh] Những trường hợp sốt xuất huyết Dengue nặng nào thì cần hội chẩn hoặc chuyển lên bệnh viện tuyến trên? → hạng 11
- `IN-050` [dinh_nghia] Điều trị hen suyễn ở người lớn nhằm đạt những đích nào? → hạng 8
- `IN-054` [ly_do] Người suy giảm miễn dịch bị viêm màng não do vi khuẩn nên bắt đầu điều trị bằng phối hợp kháng sinh nào? → hạng 10
- `IN-070` [dinh_nghia] Những tình huống nào trong sốt xuất huyết Dengue cần được mời hội chẩn ở cấp khoa hoặc bệnh viện? → hạng 9
- `IN-075` [so_lieu] Theo tiêu chuẩn chăm sóc sốt xuất huyết Dengue ở trẻ em, bé gái 10 tuổi thường có cân nặng tham khảo khoảng bao nhiêu kg? → hạng 12
- `IN-078` [ly_do] Trong xuất huyết tiêu hóa trên do sốt xuất huyết Dengue, trường hợp nào thì cần tiếp tục truyền máu và kết hợp nội soi can thiệp? → hạng 11
- `IN-082` [phan_biet] Khi hỏi bệnh ở trạm y tế xã, những biểu hiện nào giúp nghi ngờ người bệnh có thể đang mắc tiểu đường? → hạng 7
