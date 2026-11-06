import pytest

from yhdp.ingest.unwrap import should_join, starts_block, table_runs

# Lines copied from QĐ 5642 (PDF converted to docx, wrapped at ~85 chars).
WRAPPED = "Dexamethason 0,4 mg/kg/ngày, tiêm tĩnh mạch châm, dùng 4 ngày (cùng hoặc"


@pytest.mark.parametrize("prev,nxt", [
    (WRAPPED, "trước kháng sinh 15 phút)."),
    ("Phòng co giật bằng barbituric 5 - 20 mg/kg/ngày, uống. Cắt cơn giật bằng seduxen",
     "0,1 mg/kg (pha với 2 ml NaCl 0,9%) tiêm TM đến khi ngừng giật."),
    ("Liều kháng sinh khi chức năng gan, thận bình thường (liều thấp áp dụng ở trẻ dưới",
     "7 ngày tuổi)."),
    ("Cầu khuẩn Gram dương", "hoặc vi khuẩn chưa rõ"),  # short, but next starts lowercase
])
def test_joins_wrapped_lines(prev, nxt):
    assert should_join(prev, nxt)


@pytest.mark.parametrize("prev,nxt", [
    ("Hạ nhiệt: bằng paracetamon 15 mg/kg/lần, không quá 60 mg/kg/ngày.", WRAPPED),
    ("Khi có kết quả nhuộm Gram cần điều chỉnh ngay kháng sinh phù hợp:", "Cầu khuẩn Gram dương"),
    (WRAPPED, "− Vệ sinh cá nhân."),
    (WRAPPED, "b. Theo dõi điều trị"),
    (WRAPPED, "3.1. Lâm sàng"),
    (WRAPPED, "IV. ĐIỀU TRỊ"),
    ("Lâm sàng", "Sốt cao đột ngột"),  # short line, capitalised next: a paragraph break
    ("", WRAPPED),
])
def test_keeps_paragraph_breaks(prev, nxt):
    assert not should_join(prev, nxt)


@pytest.mark.parametrize("text,expected", [
    ("1. ĐẠI CƯƠNG", True), ("3.1. Lâm sàng", True), ("+ Sốt", True), ("a) Người lớn", True),
    ("7 ngày tuổi).", False), ("150.000 - 250.000 đv/kg", False), ("S. aureus kháng", False),
])
def test_starts_block(text, expected):
    assert starts_block(text) is expected


def test_table_runs_find_flattened_cells():
    cells = ["Kháng sinh", "Tổng liều/kg/ngày", "Amikacin (c)", "Gentamicin", "Ampicilin",
             "Cefotaxim", "Ceftazidim", "20 - 30 mg/kg", "5 mg/kg"]
    lines = [WRAPPED, "trước kháng sinh 15 phút).", *cells, WRAPPED]
    assert table_runs(lines) == [(2, 11)]


def test_table_runs_ignore_short_lists_and_breaks():
    bullets = [f"− Triệu chứng {i}" for i in range(10)]
    assert table_runs(bullets) == []
    cells = ["a1", "a2", "a3", "a4", None, "b1", "b2", "b3", "b4"]  # None: heading in between
    assert table_runs(cells) == []
