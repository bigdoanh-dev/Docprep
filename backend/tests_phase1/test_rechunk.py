import json

from docx import Document

from app.content_tools.augment import role_of
from app.content_tools.rechunk import build
from app.content_tools.sources import Source


def test_original_word_build_preserves_table_and_metadata(tmp_path):
    doc = Document()
    doc.add_heading("Chuyên đề kiểm tra", level=1)
    doc.add_heading("Ví dụ minh họa", level=2)
    doc.add_paragraph("Đoạn minh họa giữ lại nguyên câu và có đủ nội dung để đối chiếu.")
    table = doc.add_table(rows=2, cols=2)
    for cell, label in zip((c for row in table.rows for c in row.cells), ["Tên", "Giá trị", "Mục A", "1"]):
        cell.text = label
    path = tmp_path / "sample.docx"
    doc.save(path)
    source = Source(doc_id="sample", title="Tài liệu thử", kind="primary", format="docx", citation="section")
    report, records = build(source, path, tmp_path / "first")
    assert report["state"] == "review_required"
    text, table = records
    assert text["kind"] == "text" and table["kind"] == "table"
    assert "| Tên | Giá trị |\n| --- | --- |\n| Mục A | 1 |" == table["text"]
    table_meta = table["location"]["augmentation"]
    text_meta = text["location"]["augmentation"]
    assert table_meta["parent_id"] == text_meta["parent_id"]
    assert table_meta["context_child_id"] == text["chunk_id"]
    assert table_meta["pedagogical_role"] == "example"
    assert "Ví dụ minh họa" in table_meta["contextual_header"]
    assert not table["location"]["printed_pages"]
    for row in records:
        for question in row["location"]["augmentation"]["questions"]:
            assert question["evidence"] in row["text"]
    parents = json.loads((tmp_path / "first" / "parents.json").read_text(encoding="utf-8"))
    assert parents[table_meta["parent_id"]]["child_ids"] == [text["chunk_id"], table["chunk_id"]]
    assert (report, records) == build(source, path, tmp_path / "again")


def test_roles_use_explicit_heading_labels():
    assert role_of(["Phụ lục", "2. Bài tập"]) == "exercise"
    assert role_of(["I. ĐẠI CƯƠNG"]) == "theory"
    assert role_of(["3. Hướng dẫn"]) == "unknown"
