from yhdp.ingest.sections import Heading, SectionStack


def push_all(*texts: str) -> SectionStack:
    stack = SectionStack()
    for t in texts:
        stack.push(Heading.from_text(t))
    return stack


def tokens(stack: SectionStack) -> list[str]:
    return [h.text.split()[0] for h in stack.entries]


def test_numeric_nesting_and_siblings():
    s = push_all("I. ĐẠI CƯƠNG", "II. DIỄN BIẾN", "1. Giai đoạn sốt", "1.1. Lâm sàng",
                 "1.2. Cận lâm sàng", "2. Giai đoạn nguy hiểm", "2.1. Lâm sàng")
    assert tokens(s) == ["II.", "2.", "2.1."]


def test_roman_closes_everything():
    s = push_all("II. DIỄN BIẾN", "3. Giai đoạn hồi phục", "3.2. Cận lâm sàng", "III. CHẨN ĐOÁN")
    assert tokens(s) == ["III."]


def test_letter_chain_from_qd2760():
    s = push_all("IV. ĐIỀU TRỊ", "A. Điều trị SXHD", "1. Điều trị triệu chứng", "3. Theo dõi",
                 "B. Điều trị SXHD có dấu hiệu cảnh báo", "B1. Trẻ em", "B2. Người lớn")
    assert tokens(s) == ["IV.", "B.", "B2."]
    # C.1 has no "C." parent: it must not end up under B.
    s.push(Heading.from_text("C.1. Điều trị SXHD nặng trẻ em"))
    assert tokens(s) == ["IV.", "C.1."]
    s.push(Heading.from_text("C1.1. Điều trị sốc SXHD"))
    s.push(Heading.from_text("C.1.3. Điều trị xuất huyết nặng"))
    assert tokens(s) == ["IV.", "C.1.", "C.1.3."]
    s.push(Heading.from_text("C.2. Điều trị SXHD nặng người lớn"))
    s.push(Heading.from_text("C.2.5. Điều trị suy tạng nặng"))
    s.push(Heading.from_text("C.2.5.1. Tổn thương gan nặng"))
    assert tokens(s) == ["IV.", "C.2.", "C.2.5.", "C.2.5.1."]
    s.push(Heading.from_text("C.2.6. Điều trị SXHD ở PNCT"))
    s.push(Heading.from_text("1. Đặc điểm SXHD ở PNCT"))
    s.push(Heading.from_text("2. Điều trị SXHD ở PNCT"))
    assert tokens(s) == ["IV.", "C.2.", "C.2.6.", "2."]
    s.push(Heading.from_text("D. Các vấn đề khác"))
    assert tokens(s) == ["IV.", "D."]


def test_numeric_parent_must_match_prefix():
    # "1.6" after "2.2" (a numbering slip in the source) must not nest under "2."
    s = push_all("PHỤ LỤC 19", "2. Chế độ ăn", "2.2. Sốc SXHD", "1.6. Giai đoạn hồi phục")
    assert tokens(s) == ["PHỤ", "1.6."]


def test_appendix_resets_to_root_and_hosts_roman():
    s = push_all("IV. ĐIỀU TRỊ", "C.2. x", "PHỤ LỤC 23", "I. CHĂM SÓC KHÔNG SỐC", "1. Đại cương")
    assert tokens(s) == ["PHỤ", "I.", "1."]
    s.push(Heading.from_text("II. CHĂM SÓC SỐC"))
    assert tokens(s) == ["PHỤ", "II."]
    s.push(Heading.from_text("PHỤ LỤC 24"))
    assert tokens(s) == ["PHỤ"]


def test_style_headings():
    s = SectionStack()
    s.push(Heading(text="Phần 1. Tăng huyết áp", family="style", depth=2))
    s.push(Heading(text="Bước 1. Hỏi bệnh", family="style", depth=3))
    s.push(Heading(text="Bước 2. Khám", family="style", depth=3))
    assert [h.text for h in s.entries] == ["Phần 1. Tăng huyết áp", "Bước 2. Khám"]
    s.push(Heading(text="Phần 2. Đái tháo đường", family="style", depth=2))
    assert [h.text for h in s.entries] == ["Phần 2. Đái tháo đường"]


def test_transparent_part_resets_without_entering_path():
    s = push_all("PHỤ LỤC 3")
    s.push(Heading(text="HƯỚNG DẪN CHẨN ĐOÁN", family="part", depth=0), transparent=True)
    assert s.entries == []
