import pytest
from docx_builder import DocBuilder

from yhdp.ingest.parse_docx import parse_docx
from yhdp.sources import Source

SRC = Source(doc_id="t", file_match="t", title="Hướng dẫn chẩn đoán, điều trị sốt xuất huyết Dengue",
             issuer="QĐ 2760/QĐ-BYT", year=2023, kind="primary", format="docx", citation="section")


@pytest.fixture
def parse(tmp_path):
    def _parse(builder: DocBuilder, source: Source = SRC):
        path = builder.save(tmp_path / "in.docx")
        return parse_docx(path, source, tmp_path / "figures")
    return _parse


def headings(doc):
    return [(b.text, b.loc.section_path) for b in doc.blocks if b.kind == "heading"]


def test_front_matter_title_toc_and_boilerplate(parse):
    doc = parse(DocBuilder()
                .caps("QUYẾT ĐỊNH")
                .p(" Ban hành kèm theo Quyết định này", bold_prefix="Điều 1.")
                .caps("HƯỚNG DẪN CHẨN ĐOÁN, ĐIỀU TRỊ").caps("SỐT XUẤT HUYẾT DENGUE")
                .p("(Ban hành kèm theo Quyết định số 2760/QĐ-BYT)", center=True)
                .caps("DANH SÁCH BAN BIÊN SOẠN")
                .caps("“HƯỚNG DẪN CHẨN ĐOÁN, ĐIỀU TRỊ SỐT XUẤT HUYẾT DENGUE”")  # contains the title
                .table([["Chủ biên", "GS. A"]])
                .caps("MỤC LỤC").p("I. ĐẠI CƯƠNG").p("PHỤ LỤC 1: CÁC GIAI ĐOẠN")
                .caps("HƯỚNG DẪN CHẨN ĐOÁN, ĐIỀU TRỊ SỐT XUẤT HUYẾT DENGUE")
                .h("I. ĐẠI CƯƠNG").p("Sốt xuất huyết Dengue là bệnh truyền nhiễm."))
    front = [b for b in doc.blocks if b.loc.section_path == ["Quyết định ban hành"]]
    assert [b.text for b in front] == ["**QUYẾT ĐỊNH**", "Điều 1. Ban hành kèm theo Quyết định này"]
    assert headings(doc) == [("I. ĐẠI CƯƠNG", ["I. ĐẠI CƯƠNG"])]
    body = [b.text for b in doc.blocks]
    assert not any("Ban hành kèm theo Quyết định số" in t or "GS. A" in t or "CÁC GIAI ĐOẠN" in t
                   for t in body)
    assert doc.blocks[-1].loc.anchor == "I"


def test_bold_prefix_heading_splits_off_body_text(parse):
    doc = parse(DocBuilder().h("1. Chẩn đoán căn nguyên")
                .p(" lấy máu trong giai đoạn sốt.", bold_prefix="1.2. Xét nghiệm PCR:"))
    assert headings(doc)[-1] == ("1.2. Xét nghiệm PCR",
                                 ["1. Chẩn đoán căn nguyên", "1.2. Xét nghiệm PCR"])
    assert doc.blocks[-1].kind == "para"
    assert doc.blocks[-1].text == "lấy máu trong giai đoạn sốt."
    assert doc.blocks[-1].loc.anchor == "1/1.2"


def test_non_bold_numbered_lines_and_bold_labels_are_not_headings(parse):
    doc = parse(DocBuilder().h("I. ĐẠI CƯƠNG:").p("1. Uống nhiều nước.")
                .h("* Những lưu ý khi truyền dịch").h("Lưu ý:"))
    assert headings(doc) == [("I. ĐẠI CƯƠNG", ["I. ĐẠI CƯƠNG"])]
    assert [b.text for b in doc.blocks[1:]] == [
        "- 1. Uống nhiều nước.", "**\\* Những lưu ý khi truyền dịch**", "**Lưu ý:**"]


def test_lists_are_grouped_with_nesting(parse):
    doc = parse(DocBuilder().h("I. ĐẠI CƯƠNG").p("- Xuất huyết.").p("+ Dưới da.")
                .p("a) Niêm mạc.").p("Đoạn văn thường."))
    assert [b.kind for b in doc.blocks] == ["heading", "list", "para"]
    assert doc.blocks[1].text == "- Xuất huyết.\n  - Dưới da.\n- a) Niêm mạc."


def test_appendix_title_merge_figure_caption_refs_and_tiny_images(parse, tmp_path):
    doc = parse(DocBuilder().h("IV. ĐIỀU TRỊ")
                .p(" Sơ đồ truyền dịch trong sốc.", bold_prefix="Phụ lục 8:")
                .caps("PHỤ LỤC 8").caps("SƠ ĐỒ TRUYỀN DỊCH TRONG SỐC")
                .p("(Ban hành kèm theo Quyết định số 2760/QĐ-BYT)", center=True)
                .image(64).image(1))
    ref = doc.blocks[1]
    assert ref.kind == "para" and ref.refs == ["pl8"]
    assert headings(doc)[-1] == ("Phụ lục 8: SƠ ĐỒ TRUYỀN DỊCH TRONG SỐC",
                                 ["Phụ lục 8: SƠ ĐỒ TRUYỀN DỊCH TRONG SỐC"])
    figs = [b for b in doc.blocks if b.kind == "figure"]
    assert len(figs) == 1
    assert figs[0].caption == "Phụ lục 8: SƠ ĐỒ TRUYỀN DỊCH TRONG SỐC"
    assert figs[0].loc.anchor == "pl8"
    assert (tmp_path / figs[0].figure_path).exists()


def test_appendix_hosts_roman_and_caps_subtitles(parse):
    doc = parse(DocBuilder().caps("PHỤ LỤC 14").caps("MẪU GIẤY TÓM TẮT")
                .p("Kèm theo giấy chuyển tuyến", center=True)
                .caps("GIẤY TÓM TẮT ĐIỀU TRỊ").p("Họ tên bệnh nhân: ……")
                .caps("PHỤ LỤC 23").caps("HƯỚNG DẪN CHĂM SÓC").h("I. CHĂM SÓC KHÔNG SỐC"))
    assert headings(doc) == [
        ("Phụ lục 14: MẪU GIẤY TÓM TẮT", ["Phụ lục 14: MẪU GIẤY TÓM TẮT"]),
        ("GIẤY TÓM TẮT ĐIỀU TRỊ", ["Phụ lục 14: MẪU GIẤY TÓM TẮT", "GIẤY TÓM TẮT ĐIỀU TRỊ"]),
        ("Phụ lục 23: HƯỚNG DẪN CHĂM SÓC", ["Phụ lục 23: HƯỚNG DẪN CHĂM SÓC"]),
        ("I. CHĂM SÓC KHÔNG SỐC", ["Phụ lục 23: HƯỚNG DẪN CHĂM SÓC", "I. CHĂM SÓC KHÔNG SỐC"]),
    ]
    assert doc.blocks[-1].loc.anchor == "pl23/I"


def test_table_to_gfm_with_merged_cells(parse):
    doc = parse(DocBuilder().h("I. PHÂN ĐỘ")
                .table([["Phân độ", "Lâm sàng", ""],
                        ["Nặng", "Sốc", "M = 0"],
                        ["", "Xuất huyết | nặng", "Hct giảm"]],
                       hmerge=(0, 1, 2), vmerge=(0, 1, 2)))
    table = doc.blocks[-1]
    assert table.kind == "table" and table.caption == "I. PHÂN ĐỘ"
    assert table.text == ("| Phân độ | Lâm sàng | Lâm sàng |\n"
                          "| --- | --- | --- |\n"
                          "| Nặng | Sốc | M = 0 |\n"
                          "| Nặng | Xuất huyết \\| nặng | Hct giảm |")


def test_single_cell_table_becomes_box(parse):
    doc = parse(DocBuilder().h("I. X").table([["Hộp 4.10. Kiểm duyệt"]]))
    assert doc.blocks[-1].kind == "box"
    assert doc.blocks[-1].text == "Hộp 4.10. Kiểm duyệt"


def test_style_headings_transparent_title_byline_and_formula(parse):
    src = SRC.model_copy(update={"title": "Hướng dẫn chẩn đoán, điều trị và quản lý một số bệnh không lây nhiễm"})
    doc = parse(DocBuilder().add_style("Code")
                .p("QĐ 5904/QĐ-BYT – Hướng dẫn chẩn đoán, điều trị và quản lý một số bệnh không lây nhiễm",
                   style="Heading 1")
                .p("Nov 3, 2026 · @TrungHau")
                .p("Phần 1. Tăng huyết áp", style="Heading 2")
                .p("Bước 1. Hỏi bệnh", style="Heading 3")
                .p(r"\text{CNLT} = (\text{Chiều cao} - 100) \times 0{,}9", style="Code"), src)
    assert headings(doc) == [("Phần 1. Tăng huyết áp", ["Phần 1. Tăng huyết áp"]),
                             ("Bước 1. Hỏi bệnh", ["Phần 1. Tăng huyết áp", "Bước 1. Hỏi bệnh"])]
    assert not any("@TrungHau" in b.text for b in doc.blocks)
    assert doc.blocks[-1].kind == "formula"
    assert doc.blocks[-1].text.startswith("$$") and doc.blocks[-1].text.endswith("$$")


def test_unwrap_joins_lines_and_collects_flattened_tables(parse):
    # QĐ 5642 shapes: disease title and "1." share a style, wrapped tails, cells one per line
    wrapped = "Dexamethason 0,4 mg/kg/ngày, tiêm tĩnh mạch châm, dùng 4 ngày (cùng hoặc"
    b = (DocBuilder().p("BỆNH UỐN VÁN", style="Heading 2").p("1. ĐẠI CƯƠNG", style="Heading 2")
         .p(wrapped).p("trước kháng sinh 15 phút).")
         .p("Phát triển các dấu hiệu nguy hiểm vào các ngày điều trị thứ 1,")
         .p("2, 3 (D1, D2, D3).", style="Heading 2"))
    for cell in ["Kháng sinh", "Tổng liều", "Amikacin", "Gentamicin", "20 mg/kg", "5 mg/kg",
                 "150 mg/kg", "100 mg/kg"]:
        b.p(cell)
    b.p("TÀI LIỆU THAM KHẢO", style="Heading 2").p("1. Aksamit A.J. Herpes", style="Heading 3")
    b.p("treatment options in neurology (2005).")
    b.p("BỆNH DỊCH HẠCH", style="Heading 2").p("Nội dung.")
    doc = parse(b, SRC.model_copy(update={"needs_unwrap": True}))
    by_kind = [(blk.kind, blk.loc.anchor, blk.text) for blk in doc.blocks]
    assert ("heading", "benh-uon-van/1", "1. ĐẠI CƯƠNG") in by_kind
    texts = [blk.text for blk in doc.blocks if blk.kind == "para"]
    assert wrapped + " trước kháng sinh 15 phút)." in texts
    assert any(t.endswith("thứ 1, 2, 3 (D1, D2, D3).") for t in texts)
    flat = [blk for blk in doc.blocks if blk.needs_review == ["table_flattened"]]
    assert len(flat) == 1 and flat[0].text.splitlines()[0] == "Kháng sinh"
    assert not any("Aksamit" in blk.text or "neurology" in blk.text for blk in doc.blocks)
    assert doc.blocks[-1].loc.anchor == "benh-dich-hach"


def test_unwrap_heading_absorbs_lowercase_tail(parse):
    b = (DocBuilder().p("BỆNH SỐT RÉT", style="Heading 2")
         .p("5.3. Triển khai các biện pháp dự phòng sự lan truyền sốt rét từ vùng này sang vùng",
            style="Heading 3")
         .p("khác, đặc biệt từ vùng đã xác định có kháng thuốc.")
         .p("5.4. Giám sát", style="Heading 3").p("Theo dõi hằng tháng."))
    doc = parse(b, SRC.model_copy(update={"needs_unwrap": True}))
    heads = [blk.text for blk in doc.blocks if blk.kind == "heading"]
    assert heads[1].endswith("sang vùng khác, đặc biệt từ vùng đã xác định có kháng thuốc.")
    assert heads[2] == "5.4. Giám sát"
    assert [blk.text for blk in doc.blocks if blk.kind == "para"] == ["Theo dõi hằng tháng."]
