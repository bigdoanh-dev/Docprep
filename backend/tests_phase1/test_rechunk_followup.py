from types import SimpleNamespace

import pytest

from app.content import service, tagger
from app.content_tools.chunk import chunk_doc
from app.content_tools.model import ParsedDoc
from app.content_tools.ocr_layout import Line, Word, format_scan
from app.content_tools.rechunk import approx_tokens
from app.content_tools.sources import Source
from experiments.retrieval_eval.chat_release_eval import compare, score_case
from experiments.tagger_eval.evaluate import kappa


def line(text, y, columns=None):
    return Line(("1", str(y)), tuple(
        Word(value, col, y, 50, 14) for col, value in (columns or [(100, text)])
    ))


def test_ocr_chapter_and_subsection_are_preserved_across_pages():
    pages = [
        ([line("Chương IV. Nội dung", 10), line("C. CHỦ ĐỀ CHÍNH", 30),
          line("C.2. Đại cương", 50), line("C.2.2. Định nghĩa", 70),
          line("Đây là đoạn văn mở đầu về nội dung đang được mô tả.", 95)],
         {"page": 11, "width": 900}),
        ([line("Đoạn này tiếp tục cùng nội dung từ ảnh trang trước.", 10),
          line("C.2.3. Phân loại", 30), line("Đoạn văn thuộc mục tiếp theo.", 70)],
         {"page": 12, "width": 900}),
    ]
    blocks = format_scan(pages)
    same = [b for b in blocks if b.kind == "para"][:2]
    assert len(same) == 2 and same[0].loc.anchor == same[1].loc.anchor
    assert same[1].loc.section_path == ["Chương IV. Nội dung", "C. CHỦ ĐỀ CHÍNH", "C.2. Đại cương", "C.2.2. Định nghĩa"]
    source = Source(doc_id="test", title="OCR", kind="textbook", format="scan", citation="page")
    chunks = chunk_doc(ParsedDoc(doc_id="test", blocks=blocks), source, approx_tokens)
    assert chunks[0].loc.image_indices == [11, 12]
    assert not chunks[0].loc.printed_pages
    assert chunks[0].loc.anchor != chunks[1].loc.anchor


def test_ocr_table_requires_caption_and_aligned_rows():
    pages = [([
        line("Chương 1. Giới thiệu", 10), line("Bảng 1. Số liệu", 30),
        line("", 50, [(100, "Nhóm"), (300, "Tổng")]),
        line("", 70, [(100, "A"), (300, "15")]),
        line("", 90, [(100, "B"), (300, "23")]),
        line("Bảng 2. Chưa rõ dạng cột", 110), line("Giữ nguyên đoạn nguồn khi không chắc chắn.", 130),
    ], {"page": 1, "width": 800})]
    blocks = format_scan(pages)
    table, = [b for b in blocks if b.kind == "table"]
    assert table.text.splitlines() == ["| Nhóm | Tổng |", "| --- | --- |", "| A | 15 |", "| B | 23 |"]
    assert "ocr_table_layout_requires_review" in table.needs_review
    assert any("ocr_table_unresolved" in b.needs_review for b in blocks)
    assert any(b.text == "Giữ nguyên đoạn nguồn khi không chắc chắn." for b in blocks)


def test_tagger_validates_codes_and_uses_text_behind_no_reviewer_labels():
    row = {"kind": "text", "text": "Đoạn học liệu", "location": {"section_path": ["Chương 1"]}}
    taxonomy = {"van_de": [{"id": 2, "name": "Vấn đề"}],
                "mien": [{"sub": [{"id": "1.1", "name": "Miền"}]}]}

    class Gateway:
        def complete(self, task, system, messages, version, **_):
            assert task == "content_tag" and "Đoạn học liệu" in messages[0]["content"]
            return SimpleNamespace(text='{"primary_issue":2,"secondary_issues":[],"domains":["1.1"],'
                                        '"bloom":"Hiểu","content_type":"khác","population":[],"rationale":"Đề xuất"}',
                                   model="fixture")

    labels, provenance = tagger.predict(Gateway(), row, taxonomy)
    assert labels["van_de"] == [{"id": 2, "primary": True}]
    assert provenance["strategy"] == "model"
    with pytest.raises(ValueError, match="outside taxonomy"):
        tagger.predict(Gateway(), row, {**taxonomy, "van_de": []})
    index = {tagger._match_key("doc", "text", row["text"], row["location"]): [(labels, provenance)]}
    assert tagger.reuse(index, {**row, "external_doc_id": "doc"})
    assert tagger.reuse(index, {**row, "external_doc_id": "doc", "text": "Nội dung khác"}) is None


def test_cohens_kappa_nominal_and_ordinal():
    assert kappa([(1, 1), (2, 2)]) == 1
    assert kappa([(1, 2), (2, 1)]) == -1
    assert kappa([(1, 1)] * 3) is None
    pairs = [("Nhớ", "Hiểu"), ("Sáng tạo", "Sáng tạo")]
    assert 1 > kappa(pairs, service.BLOOM) > kappa(pairs)


def test_chat_comparison_scores_paired_hybrid_and_candidate_only():
    trace = {"before_rerank": ["x"] * 6 + ["hit"], "after_rerank": ["hit"],
             "provider": "fixture", "embedding_model": "embed", "embedding_revision": "r1",
             "rerank": {"enabled": True}, "rerank_model": "fixture"}
    expected = {"passages": ["hit"], "states": ["answered"]}
    metrics = score_case(trace, [{"passage_id": "hit"}], "answered", expected)
    assert not metrics["before_hit_at_5"] and metrics["after_hit_at_5"]
    row = {"id": "1", "status": "complete", "trace": trace, "metrics": metrics, "model": "same", "prompt": "same"}
    result = compare({"case_sha256": "s", "variant": "baseline", "release": "old", "rows": [row]},
                     {"case_sha256": "s", "variant": "candidate", "release": "new", "rows": [row, {**row, "id": "2"}]})
    assert result["paired_with_compatible_hybrid"] == 1 and result["candidate_only"]["cases"] == 1


def big(text, y):
    """A large, indented all-caps line: the layout the heuristic treats as a chapter-level title."""
    return Line(("t", str(y)), tuple(Word(w, 300 + 60 * i, y, 50, 30) for i, w in enumerate(text.split())))


TOC = [
    {"chapter": "Chương 2. Ngộ độc", "group": "Phần 2.1. Thuốc", "title": "NGỘ ĐỘC PARACETAMOL",
     "match": "NGỘ ĐỘC PARACETAMOL", "cont": None},
    {"chapter": "Chương 2. Ngộ độc", "group": "Phần 2.1. Thuốc", "title": "NGỘ ĐỘC CẤP HÓA CHẤT DIỆT CHUỘT LOẠI NATRI",
     "match": "NGỘ ĐỘC CẤP HÓA CHẤT DIỆT CHUỘT", "cont": "LOẠI NATRI"},
    {"chapter": "Chương 2. Ngộ độc", "group": "Phần 2.2. Tự nhiên", "title": "RẮN HỔ MANG CẮN",
     "match": "RẮN HỔ MANG CẮN", "cont": None},
]


def test_ocr_topics_follow_table_of_contents_not_garbled_caps():
    body = [line("Đoạn nội dung mô tả chi tiết của mục này.", 200 + 20 * i) for i in range(6)]
    pages = [
        ([line("NGO DOC PARACETAMOL", 10), line("1. DAI CUONG", 30), *body[:2],
          big("HAN RAN CAP NIA CAN", 150)], {"page": 16, "width": 900}),
        # Running header repeating the open topic must not reopen or skip it.
        ([line("NGỘ ĐỘC PARACETAMOL", 5), *body[2:3], line("NGỘ ĐỘC CẤP HÓA CHẤT DIỆT CHUỘT", 40),
          line("LOẠI NATRI", 60), line("1. ĐẠI CƯƠNG", 80), *body[3:4]], {"page": 17, "width": 900}),
        ([line("RAN HO MANG CAN", 10), *body[4:]], {"page": 18, "width": 900}),
    ]
    blocks = format_scan(pages, outline={16: "Chương 2. Ngộ độc"}, topics=TOC)
    paths = [b.loc.section_path for b in blocks if b.kind == "para"]
    assert paths[0] == ["Chương 2. Ngộ độc", "Phần 2.1. Thuốc", "NGỘ ĐỘC PARACETAMOL", "1. ĐẠI CƯƠNG"]
    assert all("HAN RAN" not in " ".join(p) for p in paths)
    assert any(b.text == "HAN RAN CAP NIA CAN" for b in blocks if b.kind == "para")
    rodent = [p for p in paths if "NGỘ ĐỘC CẤP HÓA CHẤT DIỆT CHUỘT LOẠI NATRI" in p]
    assert rodent and rodent[0][-1] == "1. ĐẠI CƯƠNG"
    assert not any(b.text == "LOẠI NATRI" for b in blocks)
    assert paths[-1] == ["Chương 2. Ngộ độc", "Phần 2.2. Tự nhiên", "RẮN HỔ MANG CẮN"]


def test_caps_numbered_heading_inside_ocr_paragraph_opens_section():
    # Tesseract put the heading line into the same paragraph as the text around it.
    para = [Line(("p", "1"), tuple(Word(w, 100 + 60 * i, y, 50, 14) for i, w in enumerate(t.split())))
            for t, y in (("Nội dung phần chẩn đoán phân biệt.", 10), ("4. DIEU TRI", 30), ("Truyền dịch sớm.", 50))]
    blocks = format_scan([([line("Chương 1. Bệnh", 1), line("3. CHẨN ĐOÁN", 2), *para], {"page": 1, "width": 900})])
    last = [b for b in blocks if b.kind == "para"][-1]
    assert last.text == "Truyền dịch sớm." and last.loc.section_path[-1] == "4. ĐIỀU TRỊ"
    heading, = [b for b in blocks if b.kind == "heading" and b.text == "4. ĐIỀU TRỊ"]
    assert "ocr_heading_normalized" in heading.needs_review


def test_restore_heading_only_known_multi_syllable_terms():
    from app.content_tools.ocr_layout import restore_heading
    assert restore_heading("5. TIEN TRIEN VA BIEN CHUNG") == "5. TIẾN TRIỂN VA BIẾN CHỨNG"
    assert restore_heading("2. Chan doan phân biệt:") == "2. Chẩn đoán phân biệt:"
    assert restore_heading("RAN CAP NIA CAN") == "RAN CAP NIA CAN"


def test_ocr_topic_out_of_toc_order_is_still_opened_once():
    toc = [{**TOC[2], "title": t, "match": t} for t in ("RẮN HỔ MANG CẮN", "RẮN CẠP NIA CẮN", "RẮN HỔ MÈO CẮN")]
    pages = [([line("RAN HO MANG CAN", 10), line("Nội dung một.", 20), line("RAN HO MÈO CAN", 30),
               line("Nội dung hai.", 40), line("RAN CAP NIA CAN", 50), line("Nội dung ba.", 60),
               line("RẮN HỔ MÈO CẮN", 70), line("Vẫn thuộc rắn cạp nia.", 80)], {"page": 16, "width": 900})]
    blocks = format_scan(pages, outline={16: "Chương 2. Ngộ độc"}, topics=toc)
    topic = {b.text: b.loc.section_path[2] for b in blocks if b.kind == "para"}
    assert topic["Nội dung hai."] == "RẮN HỔ MÈO CẮN" and topic["Nội dung ba."] == "RẮN CẠP NIA CẮN"
    assert topic["Vẫn thuộc rắn cạp nia."] == "RẮN CẠP NIA CẮN"


def test_ocr_setup_rejects_missing_language_model(monkeypatch, tmp_path):
    from app.content_tools import rechunk
    (tmp_path / "eng.traineddata").write_bytes(b"eng")
    listing = f'List of available languages in "{tmp_path}/" (1):\neng\n'
    monkeypatch.setattr(rechunk.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=0, stdout=listing, stderr=""))
    with pytest.raises(ValueError, match="missing: vie"):
        rechunk.ocr_setup("tesseract", "vie+eng")
    (tmp_path / "vie.traineddata").write_bytes(b"vie")
    monkeypatch.setattr(rechunk.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=0, stdout=listing.replace("(1):\neng", "(2):\neng\nvie"), stderr=""))
    command, fingerprint = rechunk.ocr_setup("tesseract", "vie+eng", tmp_path)
    assert command == ["tesseract", "--tessdata-dir", str(tmp_path)] and len(fingerprint) == 64
