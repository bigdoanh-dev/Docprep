import pytest

from yhdp.ingest.numbering import parse_numbering


@pytest.mark.parametrize("text,family,token,depth", [
    ("I. ĐẠI CƯƠNG", "roman", "I", 1),
    ("IV. ĐIỀU TRỊ", "roman", "IV", 1),
    ("A. Điều trị sốt xuất huyết Dengue", "letter", "A", 1),
    ("D. Các vấn đề khác", "letter", "D", 1),
    ("B1. Đối với người bệnh trẻ em (< 16 tuổi)", "letter", "B1", 2),
    ("C.1. Điều trị sốt xuất huyết Dengue nặng trẻ em", "letter", "C.1", 2),
    ("C1.1. Điều trị sốc sốt xuất huyết Dengue", "letter", "C1.1", 3),
    ("C.1.3. Điều trị xuất huyết nặng", "letter", "C.1.3", 3),
    ("C.2.4 Điều trị xuất huyết nặng", "letter", "C.2.4", 3),
    ("C.2.5.1. Tổn thương gan nặng, suy gan cấp", "letter", "C.2.5.1", 4),
    ("1. Giai đoạn sốt", "num", "1", 1),
    ("2.3 Trẻ em", "num", "2.3", 2),
    ("3.1.2. Triệu chứng lâm sàng", "num", "3.1.2", 3),
    ("PHỤ LỤC 8", "pl", "pl8", 0),
    ("Phụ lục 16.1: Sơ đồ truyền dịch", "pl", "pl16.1", 0),
])
def test_parse_numbering(text, family, token, depth):
    n = parse_numbering(text)
    assert (n.family, n.token, n.depth) == (family, token, depth)


@pytest.mark.parametrize("text", [
    "Vi rút Dengue",          # 'V' followed by a letter is a word, not a numeral
    "CHĂM SÓC NGƯỜI BỆNH",    # starts with 'C' but no numbering
    "Bước 1. Hỏi bệnh",
    "A Dengue case",          # single letter without a dot is not numbering
    "Lưu ý:",
    "* Những lưu ý khi truyền dịch",
    "- Sốt cao đột ngột",
])
def test_not_numbering(text):
    assert parse_numbering(text) is None


def test_letter_parts():
    n = parse_numbering("C1.1. Điều trị sốc")
    assert n.letter == "C" and n.parts == (1, 1)
    assert parse_numbering("C.2.5.1. x").parts == (2, 5, 1)
    assert parse_numbering("3.1.2. x").parts == (3, 1, 2)
