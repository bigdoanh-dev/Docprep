"""Pure medical dictionary adapted from YHDP c661586 (no file writes/settings).

Keys compare after NFC + casefold, except all-caps abbreviations, which match case-sensitively
in running text so "HA" (huyết áp) doesn't fire on an ordinary word.
"""

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict


TermType = Literal["Bệnh", "TriệuChứng", "XétNghiệm", "Thuốc", "ThủThuật", "TácNhân", "ĐộcChất",
                   "KháiNiệmDịchTễ", "ĐốiTượng", "Khác"]


def fold(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold().strip()


def is_abbreviation(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters) and len(text) <= 8


class Term(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical: str
    aliases: list[str] = []
    type: TermType
    en: str | None = None

    def forms(self) -> list[str]:
        return [self.canonical, *self.aliases]


class Dictionary:
    def __init__(self, terms: list[Term]):
        self.terms = terms
        self.by_key: dict[str, Term] = {}
        errors = []
        for t in terms:
            for form in t.forms():
                key = fold(form)
                other = self.by_key.get(key)
                if other is not None and other is not t:
                    errors.append(f"{form!r} is used by both {other.canonical!r} and {t.canonical!r}")
                self.by_key[key] = t
        if errors:
            raise ValueError("dictionary conflicts:\n  " + "\n  ".join(errors))
        exact = sorted({f for t in terms for f in t.forms() if is_abbreviation(f)}, key=len, reverse=True)
        folded = sorted({fold(f) for t in terms for f in t.forms() if not is_abbreviation(f)},
                        key=len, reverse=True)
        self._exact = _alternation(exact)
        self._folded = _alternation(folded)

    def normalize(self, form: str) -> str | None:
        """Canonical form of a known term ("sxhd" → "sốt xuất huyết Dengue"), else None."""
        term = self.by_key.get(fold(form))
        return term.canonical if term else None

    def expand(self, form: str) -> list[str]:
        term = self.by_key.get(fold(form))
        return term.forms() if term else [form]

    def find(self, text: str) -> list[Term]:
        """Terms mentioned in text, in order of first mention."""
        found: dict[str, Term] = {}
        hits = []
        if self._exact:
            hits += [(m.start(), m.group()) for m in self._exact.finditer(unicodedata.normalize("NFC", text))]
        if self._folded:
            hits += [(m.start(), m.group()) for m in self._folded.finditer(fold(text))]
        for _, form in sorted(hits):
            term = self.by_key[fold(form)]
            found.setdefault(term.canonical, term)
        return list(found.values())


def _alternation(forms: list[str]) -> re.Pattern | None:
    if not forms:
        return None
    return re.compile(r"(?<!\w)(?:" + "|".join(re.escape(f) for f in forms) + r")(?!\w)")
