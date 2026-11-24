"""Extract page images from scanned-book .docx files (one image per page)."""

import hashlib
import io
import json
from pathlib import Path

from docx import Document
from PIL import Image, ImageStat
from pydantic import BaseModel

R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
BLANK_STDDEV = 2.0  # grayscale std-dev below this means an empty page


class PageImage(BaseModel):
    index: int  # 1-based position in document order (= Loc.image_indices)
    file: str
    part: str  # media part in the docx, e.g. /word/media/image17.jpg
    width: int
    height: int
    sha1: str
    blank: bool


def _image_rids(doc) -> list[str]:
    rids = []
    for el in doc.element.body.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "blip":
            rids.append(el.get(f"{R}embed"))
        elif tag == "imagedata":
            rids.append(el.get(f"{R}id"))
    return [r for r in rids if r]


def is_blank(img: Image.Image) -> bool:
    return ImageStat.Stat(img.convert("L")).stddev[0] < BLANK_STDDEV


def extract_pages(docx_path: Path, out_dir: Path) -> list[PageImage]:
    """Write pages as NNNN.<ext> (original bytes) plus manifest.json; skips unchanged files."""
    doc = Document(str(docx_path))
    parts = doc.part.related_parts
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = []
    for i, rid in enumerate(_image_rids(doc), start=1):
        part = parts[rid]
        blob = part.blob
        sha1 = hashlib.sha1(blob).hexdigest()
        name = f"{i:04d}{Path(part.partname).suffix.lower()}"
        target = out_dir / name
        if not target.exists() or hashlib.sha1(target.read_bytes()).hexdigest() != sha1:
            target.write_bytes(blob)
        with Image.open(io.BytesIO(blob)) as img:
            pages.append(PageImage(index=i, file=name, part=str(part.partname), width=img.width,
                                   height=img.height, sha1=sha1, blank=is_blank(img)))
    manifest = json.dumps([p.model_dump() for p in pages], ensure_ascii=False, indent=1)
    (out_dir / "manifest.json").write_text(manifest, encoding="utf-8")
    return pages


def load_manifest(out_dir: Path) -> list[PageImage]:
    data = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    return [PageImage.model_validate(d) for d in data]


def upscale(path: Path, factor: int = 2) -> Image.Image:
    """In-memory LANCZOS upscale for OCR (scans are ~100 dpi)."""
    with Image.open(path) as img:
        return img.convert("RGB").resize((img.width * factor, img.height * factor),
                                         Image.Resampling.LANCZOS)
