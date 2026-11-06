"""Versioned parser-to-chunker contract; source YHDP c661586. No content approval implied."""
from pathlib import Path
from typing import Literal
from pydantic import BaseModel
BlockKind = Literal["para", "list", "table", "figure", "formula", "box", "heading"]

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
    schema_version: Literal["yhdp.parsed.v1"] = "yhdp.parsed.v1"
    doc_id: str
    blocks: list[Block]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "ParsedDoc":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
