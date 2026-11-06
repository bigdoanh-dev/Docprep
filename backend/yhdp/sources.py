"""Source document registry (data/sources.yaml) and filename resolution."""

import unicodedata
from functools import cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from yhdp.settings import settings


def nfc_fold(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    file_match: str
    title: str
    issuer: str | None
    year: int | None
    kind: Literal["primary", "secondary", "textbook"]
    format: Literal["docx", "scan"]
    citation: Literal["section", "page"]
    van_de_prior: list[int] = []
    mien_prior: list[str] = []
    strip_patterns: list[str] = []
    needs_unwrap: bool = False
    flattened_tables: bool = False
    skip_sections: list[str] = []  # regexes on the top-level section title: cover pages, prefaces

    def resolve(self, sources_dir: Path | None = None) -> Path:
        """Return the single file in sources_dir whose name contains file_match."""
        sources_dir = sources_dir or settings.sources_dir
        needle = nfc_fold(self.file_match)
        hits = [p for p in sorted(sources_dir.glob("*.docx")) if needle in nfc_fold(p.name)]
        if len(hits) != 1:
            raise LookupError(f"{self.doc_id}: expected 1 file matching {self.file_match!r}, "
                              f"found {[p.name for p in hits]}")
        return hits[0]


@cache
def load_sources(path: Path | None = None) -> dict[str, Source]:
    path = path or settings.sources_path
    entries = yaml.safe_load(path.read_text(encoding="utf-8"))
    sources = [Source.model_validate(e) for e in entries]
    ids = [s.doc_id for s in sources]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate doc_id in {path}")
    return {s.doc_id: s for s in sources}
