"""Mine dictionary suggestions from parsed documents (P0 T13).

Results go to data/dictionary/suggestions.jsonl for reviewer approval and never straight
into terms.yaml:
- abbreviation lists ("DANH MỤC CHỮ VIẾT TẮT"): alternating ABBR / expansion lines;
- "term (ABBR)" in running text, where ABBR's letters are the initials of the last words
  ("bệnh phổi tắc nghẽn mạn tính (BPTNMT)") or of one word ("Hematocrit (Hct)");
- the LLM, for "(ABBR)" mentions the initials rule can't resolve ("Huyết áp trung bình (MAP)").
"""

import re
import unicodedata
from itertools import pairwise

from pydantic import BaseModel

from yhdp.dictionary import Dictionary, TermType, fold, is_abbreviation
from yhdp.ingest.model import ParsedDoc
from yhdp.llm import Ollama

ABBR_SECTION = re.compile(r"(?i)chữ viết tắt")
PAREN_ABBR = re.compile(r"\(([A-ZĐ][A-ZĐa-z0-9\-]{1,9})\)")
WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


class Suggestion(BaseModel):
    canonical: str
    alias: str
    method: str  # abbr_list | initials | llm
    sources: list[str]  # chunk-style refs "doc_id#anchor"
    context: str = ""
    known_as: str | None = None  # canonical the alias already has in terms.yaml, if any


def _initial(word: str) -> str:
    return fold(unicodedata.normalize("NFD", word)[0])  # "Đ" stays "đ"; "Ố" → "o"


def expansion_for(abbr: str, before: str) -> str | None:
    """The words before "(ABBR)" whose initials spell ABBR, or the single word containing it."""
    letters = [fold(c) for c in abbr if c.isalpha()]
    words = WORD.findall(before)
    n = len(letters)
    if n and len(words) >= n and [_initial(w) for w in words[-n:]] == letters:
        tail = words[-n:]
        start = before.rfind(tail[0], 0, len(before) - sum(len(w) for w in tail[1:]))
        return before[start:].strip(" ,;:-–")
    if words and fold(words[-1]).startswith(letters[0] if letters else "?") and \
            _is_subsequence(letters, fold(words[-1])):
        return words[-1]
    return None


def _is_subsequence(needle: list[str], hay: str) -> bool:
    it = iter(hay)
    return all(c in it for c in needle)


def mine_abbreviation_list(doc: ParsedDoc) -> list[Suggestion]:
    lines, anchor = [], None
    for b in doc.blocks:
        if b.kind != "heading" and b.loc.section_path and ABBR_SECTION.search(b.loc.section_path[-1]):
            lines += b.text.splitlines()
            anchor = b.loc.anchor
    out = []
    for abbr, expansion in pairwise(lines):
        if is_abbreviation(abbr) and not is_abbreviation(expansion):
            out.append(Suggestion(canonical=expansion, alias=abbr, method="abbr_list",
                                  sources=[f"{doc.doc_id}#{anchor}"]))
    return out


def mine_paren_abbreviations(doc: ParsedDoc) -> tuple[list[Suggestion], list[Suggestion]]:
    """(resolved by the initials rule, unresolved with canonical="" for the LLM)."""
    resolved, unresolved = [], []
    for b in doc.blocks:
        for m in PAREN_ABBR.finditer(b.text):
            before = b.text[max(0, m.start() - 120):m.start()].splitlines()[-1:] or [""]
            term = expansion_for(m.group(1), before[0].rstrip())
            s = Suggestion(canonical=term or "", alias=m.group(1), method="initials",
                           sources=[f"{doc.doc_id}#{b.loc.anchor}"],
                           context=b.text[max(0, m.start() - 100):m.end() + 20])
            if not term:
                unresolved.append(s)
            elif fold(term) != fold(m.group(1)):
                resolved.append(s)
    return resolved, unresolved


class _Expansion(BaseModel):
    canonical: str | None  # null when the context doesn't say
    type: TermType | None


def resolve_with_llm(unresolved: list[Suggestion], llm: Ollama) -> list[Suggestion]:
    out, seen = [], set()
    for s in unresolved:
        if s.alias in seen:
            continue
        seen.add(s.alias)
        reply = llm.chat([{"role": "user", "content":
                           f"Trong đoạn tài liệu y khoa sau, chữ viết tắt \"{s.alias}\" là viết tắt "
                           "của thuật ngữ nào? Trả về thuật ngữ đầy đủ đúng như cách tài liệu dùng "
                           "(tiếng Việt nếu tài liệu ghi tiếng Việt) và loại thuật ngữ. Nếu đoạn văn "
                           f"không cho biết, trả canonical = null.\n\nĐoạn văn: \"{s.context}\""}],
                         schema=_Expansion, temperature=0)
        if reply.canonical and fold(reply.canonical) != fold(s.alias):
            out.append(s.model_copy(update={"canonical": reply.canonical, "method": "llm"}))
    return out


def merge(suggestions: list[Suggestion], dictionary: Dictionary) -> list[Suggestion]:
    """One suggestion per (alias, canonical); drop pairs terms.yaml already has; flag aliases
    terms.yaml maps elsewhere (e.g. HI = Haemophilus influenzae vs HI = 'High' on a meter)."""
    merged: dict[tuple[str, str], Suggestion] = {}
    for s in suggestions:
        key = (s.alias, fold(s.canonical))
        if key in merged:
            merged[key].sources = sorted(set(merged[key].sources + s.sources))
            continue
        known = dictionary.normalize(s.alias)
        if known is not None and fold(known) == fold(s.canonical):
            continue
        if dictionary.normalize(s.canonical) is not None and known is None:
            known = dictionary.normalize(s.canonical)
        merged[key] = s.model_copy(update={"known_as": known})
    return sorted(merged.values(), key=lambda s: (s.alias.casefold(), s.canonical))
