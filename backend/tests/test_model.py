import pytest

from yhdp.ingest.model import Block, Loc, ParsedDoc, ascii_slug, heading_token, make_anchor


@pytest.mark.parametrize("heading,token", [
    ("IV. ĐIỀU TRỊ", "IV"),
    ("II. DIỄN BIẾN LÂM SÀNG BỆNH SỐT XUẤT HUYẾT DENGUE", "II"),
    ("2. Giai đoạn nguy hiểm: thường vào ngày thứ 3 - 7", "2"),
    ("2.3 Trẻ em", "2.3"),
    ("3.1.2. Triệu chứng lâm sàng", "3.1.2"),
    ("C.1. Điều trị sốt xuất huyết Dengue nặng trẻ em", "C.1"),
    ("B1. Đối với người bệnh trẻ em", "B1"),
    ("PHỤ LỤC 8", "pl8"),
    ("Phụ lục 8: Sơ đồ truyền dịch trong sốc", "pl8"),
    ("Phụ lục 16.1: Sơ đồ truyền dịch ở người lớn", "pl16.1"),
    ("CHĂM SÓC SỐT XUẤT HUYẾT DENGUE KHÔNG SỐC Ở NGƯỜI LỚN", "cham-soc-sot-xuat-huyet-dengue"),
    ("Đường cong Kaplan-Meier", "duong-cong-kaplan-meier"),
])
def test_heading_token(heading, token):
    assert heading_token(heading) == token


def test_heading_token_does_not_treat_words_as_roman():
    # "VI rút" style words must not be read as a Roman numeral heading
    assert heading_token("Vi rút Dengue") == "vi-rut-dengue"


def test_ascii_slug_strips_vietnamese_marks():
    assert ascii_slug("Điều trị sốc") == "dieu-tri-soc"


def test_make_anchor_is_stable_and_joined():
    path = ["IV. ĐIỀU TRỊ", "2. Điều trị SXHD có dấu hiệu cảnh báo", "2.3 Trẻ em"]
    assert make_anchor(path) == "IV/2/2.3"
    assert make_anchor(path) == make_anchor(list(path))
    assert make_anchor([]) == "root"


def test_parsed_doc_round_trip(tmp_path):
    doc = ParsedDoc(doc_id="ngodoc", blocks=[
        Block(kind="para", text="Triệu chứng ngộ độc thường xuất hiện trong giờ đầu…",
              loc=Loc(section_path=["3.1. Chẩn đoán xác định"], anchor="3.1",
                      printed_pages=["54", "55"], image_indices=[61, 62])),
        Block(kind="table", text="| a | b |\n|---|---|\n| 1 | 2 |",
              loc=Loc(section_path=[], anchor="root"), needs_review=["table_rebuilt"]),
    ])
    path = tmp_path / "parsed.json"
    doc.save(path)
    assert ParsedDoc.load(path) == doc
