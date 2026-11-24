"""Source entries supplied by the YHDP registry, with explicit local file selection."""
import unicodedata
from typing import Literal

from pydantic import BaseModel


def nfc_fold(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()


class Source(BaseModel):
    doc_id: str
    title: str
    issuer: str | None = None
    year: int | None = None
    kind: Literal["primary", "secondary", "textbook"]
    format: Literal["docx", "scan"]
    citation: Literal["section", "page"]
    strip_patterns: list[str] = []
    needs_unwrap: bool = False
    skip_sections: list[str] = []
