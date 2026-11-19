# Persona probe: tổng hợp

- **Trả lời**: số lần trả lời được / số lần chạy. Profile phải xấp xỉ C0, vì hồ sơ không được đổi quyết định đủ tài liệu.
- **Tầng B dùng**: số lần bản viết lại qua mọi kiểm tra / số lần trả lời. Các lần còn lại hiển thị tầng A; lý do ở cột cuối.
- **Câu A → B**: số câu trung vị của tầng A và của bản tầng B trong cùng lượt (chỉ tính lượt tầng B được dùng).
- **Bao phủ**: tỷ lệ ý chính của tầng A còn có trong bản tầng B, cùng lượt (LLM judge). Phải ≈ 100%.

## Q1

- P5_chua_du_du_lieu: _no policy: same turn as C0_

| Điều kiện | Mức | Trả lời | Tầng B dùng | Câu A → B | Ký tự/câu | Câu có số | Câu có lý do | Bao phủ | Bỏ ở post-check | Lý do quay về A |
|---|---|---|---|---|---|---|---|---|---|---|
| C0 | — | 3/3 | — | — | 107 | 22% | 23% | — | 3/14 | — |
| P1_nam1_mat_goc | co_ban | 3/3 | 3/3 | 3 → 4 | 105 | 53% | 36% | 100% | 1/10 | — |
| P2_kha_yeu_dengue | co_ban | 3/3 | 3/3 | 3 → 5 | 121 | 35% | 63% | 100% | 2/12 | — |
| P3_gioi_on_thi | nang_cao | 3/3 | 3/3 | 4 → 3 | 135 | 50% | 53% | 100% | 2/13 | — |
| P4_nho_tot_hieu_kem | trung_binh | 3/3 | 3/3 | 3 → 4 | 115 | 56% | 61% | 100% | 2/13 | — |

## Q2

- P5_chua_du_du_lieu: _no policy: same turn as C0_

| Điều kiện | Mức | Trả lời | Tầng B dùng | Câu A → B | Ký tự/câu | Câu có số | Câu có lý do | Bao phủ | Bỏ ở post-check | Lý do quay về A |
|---|---|---|---|---|---|---|---|---|---|---|
| C0 | — | 3/3 | — | — | 89 | 67% | 40% | — | 0/15 | — |
| P1_nam1_mat_goc | co_ban | 3/3 | 2/3 | 4 → 6 | 91 | 69% | 61% | 100% | 0/12 | not_entailed ×1 |
| P2_kha_yeu_dengue | nang_cao | 3/3 | 3/3 | 5 → 5 | 104 | 53% | 67% | 100% | 0/15 | — |
| P3_gioi_on_thi | nang_cao | 3/3 | 2/3 | 4.5 → 3.5 | 116 | 55% | 38% | 100% | 0/13 | not_entailed ×1 |
| P4_nho_tot_hieu_kem | trung_binh | 3/3 | 3/3 | 5 → 6 | 115 | 61% | 58% | 100% | 0/15 | — |

## Q3

- P5_chua_du_du_lieu: _no policy: same turn as C0_

| Điều kiện | Mức | Trả lời | Tầng B dùng | Câu A → B | Ký tự/câu | Câu có số | Câu có lý do | Bao phủ | Bỏ ở post-check | Lý do quay về A |
|---|---|---|---|---|---|---|---|---|---|---|
| C0 | — | 0/3 | — | — | — | — | — | — | 0/0 | — |
| P1_nam1_mat_goc | co_ban | 0/3 | — | — | — | — | — | — | 0/0 | — |
| P2_kha_yeu_dengue | trung_binh | 0/3 | — | — | — | — | — | — | 0/0 | — |
| P3_gioi_on_thi | nang_cao | 0/3 | — | — | — | — | — | — | 0/0 | — |
| P4_nho_tot_hieu_kem | trung_binh | 0/3 | — | — | — | — | — | — | 0/0 | — |

## Q4

- P5_chua_du_du_lieu: _no policy: same turn as C0_

| Điều kiện | Mức | Trả lời | Tầng B dùng | Câu A → B | Ký tự/câu | Câu có số | Câu có lý do | Bao phủ | Bỏ ở post-check | Lý do quay về A |
|---|---|---|---|---|---|---|---|---|---|---|
| C0 | — | 3/3 | — | — | 117 | 23% | 25% | — | 0/13 | — |
| P1_nam1_mat_goc | co_ban | 3/3 | 3/3 | 5 → 7 | 107 | 20% | 40% | 100% | 0/15 | — |
| P2_kha_yeu_dengue | trung_binh | 3/3 | 1/3 | 5 → 5 | 103 | 22% | 22% | 100% | 0/14 | not_entailed ×2 |
| P3_gioi_on_thi | nang_cao | 3/3 | 3/3 | 5 → 5 | 106 | 28% | 28% | 100% | 0/14 | — |
| P4_nho_tot_hieu_kem | trung_binh | 3/3 | 0/3 | — | 101 | 19% | 32% | — | 0/16 | not_entailed ×3 |

