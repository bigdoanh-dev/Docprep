import io
import json

import pytest
from docx_builder import DocBuilder, png_bytes
from PIL import Image

from yhdp.ingest.scans import extract_pages, upscale
from yhdp.sources import load_sources


def white_png(w=40, h=60) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, format="PNG")
    return buf.getvalue()


def test_pages_follow_document_order_not_media_names(tmp_path):
    # python-docx names media image1..image11; name order would put image10 before image2.
    builder = DocBuilder()
    for size in range(20, 31):
        builder.image(size)
    path = builder.save(tmp_path / "scan.docx")
    pages = extract_pages(path, tmp_path / "out")
    assert [p.index for p in pages] == list(range(1, 12))
    assert [p.width for p in pages] == list(range(20, 31))
    assert (tmp_path / "out" / "0011.png").exists()


def test_blank_pages_kept_in_sequence_and_flagged(tmp_path):
    blank = white_png()
    path = (DocBuilder().image(30).picture(blank).image(31).picture(blank)
            .save(tmp_path / "scan.docx"))
    pages = extract_pages(path, tmp_path / "out")
    assert [p.blank for p in pages] == [False, True, False, True]
    manifest = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert [m["index"] for m in manifest] == [1, 2, 3, 4]


def test_extract_is_idempotent(tmp_path):
    path = DocBuilder().image(30).save(tmp_path / "scan.docx")
    extract_pages(path, tmp_path / "out")
    mtime = (tmp_path / "out" / "0001.png").stat().st_mtime_ns
    extract_pages(path, tmp_path / "out")
    assert (tmp_path / "out" / "0001.png").stat().st_mtime_ns == mtime


def test_upscale(tmp_path):
    p = tmp_path / "x.png"
    p.write_bytes(png_bytes(20))
    assert upscale(p, 2).size == (40, 40)


# dtch: image17 (white) is reused 7 times, plus a separate white image15.
@pytest.mark.parametrize("doc_id,count,blanks", [("ngodoc", 228, 0), ("dtch", 234, 8)])
def test_real_scans(tmp_path, doc_id, count, blanks):
    try:
        path = load_sources()[doc_id].resolve()
    except LookupError:
        pytest.skip(f"{doc_id} source not available")
    pages = extract_pages(path, tmp_path / doc_id)
    assert len(pages) == count
    assert sum(p.blank for p in pages) == blanks
