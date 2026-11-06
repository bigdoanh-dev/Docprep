"""Medical synonym lite-dictionary (design §5): data/dictionary/terms.yaml.

Keys compare after NFC + casefold, except all-caps abbreviations, which match case-sensitively
in running text so "HA" (huyết áp) doesn't fire on an ordinary word.
"""

import json
import re
import unicodedata
from functools import cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from yhdp.settings import settings

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


def _scalar(text: str) -> str:
    """A YAML flow scalar: bare when safe, else a JSON (= YAML double-quoted) string."""
    if re.search(r"[:,\[\]{}#&*!|>'\"%@`]", text) or text != text.strip() or not text:
        return json.dumps(text, ensure_ascii=False)
    return text


def term_line(term: Term) -> str:
    aliases = ", ".join(_scalar(a) for a in term.aliases)
    en = f", en: {_scalar(term.en)}" if term.en else ""
    return f"- {{canonical: {_scalar(term.canonical)}, aliases: [{aliases}], type: {term.type}{en}}}"


def _write_validated(path: Path, text: str) -> None:
    entries = yaml.safe_load(text) or []
    Dictionary([Term.model_validate(e) for e in entries])  # raises ValueError on conflicts
    path.write_text(text, encoding="utf-8")
    load_dictionary.cache_clear()


def add_term(term: Term, path: Path | None = None) -> None:
    """Append a reviewer-approved term to terms.yaml, keeping the file's comments and layout."""
    path = path or settings.data_dir / "dictionary" / "terms.yaml"
    text = path.read_text(encoding="utf-8").rstrip("\n") + "\n"
    if APPROVED_HEADER not in text:
        text += f"\n{APPROVED_HEADER}\n"
    _write_validated(path, text + term_line(term) + "\n")


def add_alias(canonical: str, alias: str, path: Path | None = None) -> None:
    """Add an alias to an existing term's line in terms.yaml."""
    path = path or settings.data_dir / "dictionary" / "terms.yaml"
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("- {"):
            continue
        entry = yaml.safe_load(line)[0]
        if fold(entry["canonical"]) == fold(canonical):
            term = Term.model_validate(entry)
            lines[i] = term_line(term.model_copy(update={"aliases": [*term.aliases, alias]}))
            _write_validated(path, "\n".join(lines) + "\n")
            return
    raise KeyError(f"no term {canonical!r} in {path}")


APPROVED_HEADER = "# --- Reviewer-approved (added from the review UI) " + "-" * 40


@cache
def load_dictionary(path: Path | None = None) -> Dictionary:
    path = path or settings.data_dir / "dictionary" / "terms.yaml"
    entries = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return Dictionary([Term.model_validate(e) for e in entries])
