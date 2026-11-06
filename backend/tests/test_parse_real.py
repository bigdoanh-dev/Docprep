"""Regression checks on the real sources (skipped when sources/ is absent)."""

import pytest

from yhdp.ingest.parse_docx import parse_docx
from yhdp.sources import load_sources


def _parse(doc_id, tmp_path):
    source = load_sources()[doc_id]
    try:
        path = source.resolve()
    except LookupError:
        pytest.skip(f"{doc_id} source not available")
    return parse_docx(path, source, tmp_path / "figures")


def _kinds(doc, kind):
    return [b for b in doc.blocks if b.kind == kind]


def test_qd2760(tmp_path):
    doc = _parse("qd2760", tmp_path)
    figures = _kinds(doc, "figure")
    assert len(figures) == 17
    assert all(f.loc.anchor.startswith("pl") for f in figures)
    assert len(_kinds(doc, "table")) == 27  # 30 in the file minus header, Nơi nhận, ban biên soạn

    anchors = {b.loc.anchor.split("/")[0] for b in doc.blocks}
    expected_pl = {f"pl{n}" for n in range(1, 27) if n != 16} | {"pl16.1", "pl16.2"}
    assert expected_pl <= anchors
    assert "root" not in anchors

    heads = {b.text: b.loc.section_path for b in _kinds(doc, "heading")}
    assert sum(1 for b in _kinds(doc, "heading") if b.text == "I. ĐẠI CƯƠNG") == 1  # TOC dropped
    assert heads["C.1. Điều trị sốt xuất huyết Dengue nặng trẻ em"] == [
        "IV. ĐIỀU TRỊ", "C. Điều trị sốt xuất huyết Dengue nặng",
        "C.1. Điều trị sốt xuất huyết Dengue nặng trẻ em"]
    assert not any("Ban hành kèm theo Quyết định số" in b.text for b in doc.blocks)
    assert not any("Nguyễn Văn Kính" in b.text for b in doc.blocks)  # editorial list dropped
    assert any("pl8" in b.refs for b in doc.blocks if b.kind != "figure")


def test_qd5904(tmp_path):
    doc = _parse("qd5904", tmp_path)
    assert len(_kinds(doc, "table")) == 28
    assert len(_kinds(doc, "formula")) == 1
    assert not any("@TrungHau" in b.text for b in doc.blocks)
    paths = {tuple(b.loc.section_path) for b in doc.blocks}
    assert ("Phần 1. Tăng huyết áp tại trạm y tế xã", "Bước 3. Chẩn đoán", "A. Phân độ THA") in paths
    assert ("Phần 2. Đái tháo đường tại trạm y tế xã",) in paths


def test_qd5642(tmp_path):
    doc = _parse("qd5642", tmp_path)
    diseases = [b.text for b in _kinds(doc, "heading") if len(b.loc.section_path) == 1
                and (b.text.startswith("BỆNH") or b.text == "NHIỄM KHUẨN HUYẾT")]
    assert len(diseases) == 14
    first = next(b for b in _kinds(doc, "heading") if b.text == "3.2. Cận lâm sàng")
    assert first.loc.section_path[0] == "BỆNH VIÊM NÃO DO VIRUS HERPES SIMPLEX"
    assert not any("Aksamit" in b.text for b in doc.blocks)  # references dropped
    assert not any(b.text.startswith("2, 3 (D1") for b in _kinds(doc, "heading"))
    flat = [b for b in doc.blocks if "table_flattened" in b.needs_review]
    assert len(flat) == 12
    assert any(b.text.startswith("Lứa tuổi") and b.loc.anchor.endswith("4/4.2") for b in flat)
