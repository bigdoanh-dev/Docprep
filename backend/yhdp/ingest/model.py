"""Common document model: the contract between parsers (docx, OCR) and the chunker."""

import re
import unicodedata
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from yhdp.ingest.numbering import parse_numbering

BlockKind = Literal["para", "list", "table", "figure", "formula", "box", "heading"]


def ascii_slug(text: str, max_len: int = 30) -> str:
    text = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:max_len].rstrip("-")


def heading_token(heading: str) -> str:
    """'IV. ĐIỀU TRỊ' -> 'IV', 'C.1. …' -> 'C.1', 'Phụ lục 8: …' -> 'pl8', else a slug."""
    heading = unicodedata.normalize("NFC", heading.strip())
    numbering = parse_numbering(heading)
    return numbering.token if numbering else ascii_slug(heading)


def make_anchor(section_path: list[str]) -> str:
    return "/".join(heading_token(h) for h in section_path) or "root"


class Loc(BaseModel):
    section_path: list[str]
    anchor: str
    printed_pages: list[str] | None = None  # scans: ["54"] or ["54", "55"]; front matter "xii"
    image_indices: list[int] | None = None  # scans: 1-based page image index in the docx


class Block(BaseModel):
    kind: BlockKind
    text: str  # markdown; tables as GFM, formulas as LaTeX
    loc: Loc
    figure_path: str | None = None
    caption: str | None = None
    caption_desc: str | None = None  # LLM/VLM description of a figure or table (T11)
    needs_review: list[str] = []  # e.g. ["table_rebuilt", "ocr_disagreement"]
    refs: list[str] = []  # anchors this block cross-references, e.g. ["pl8"] for "xem Phụ lục 8"


class ParsedDoc(BaseModel):
    doc_id: str
    blocks: list[Block]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "ParsedDoc":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
