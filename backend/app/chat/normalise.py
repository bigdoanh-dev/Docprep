"""Query normalisation (FR-LRN-01): case, diacritics, glossary synonyms and abbreviations."""
import re
import unicodedata
from dataclasses import dataclass

from app.text import unaccent

_STOPWORDS_VI = ("là của và có không gì nào khi bao nhiêu được cho các những một trong thì với ở này đó ra sao thế "
                 "theo về như hay hoặc")
STOPWORDS = set(_STOPWORDS_VI.split()) | {unaccent(w) for w in _STOPWORDS_VI.split()}
# Phrases that frame a question but carry no subject matter; they must not count as content
# a passage has to cover.
_FRAMES_VI = ["phân biệt", "so sánh", "giải thích", "trình bày", "định nghĩa", "khác nhau", "như thế nào",
              "thế nào", "ra sao", "nghĩa là", "cho biết", "chi tiết hơn", "hãy nêu", "là gì"]
FRAMES = _FRAMES_VI + [unaccent(f) for f in _FRAMES_VI]
_TOKEN = re.compile(r"\w+")


_DASHES = re.compile("[\u2010-\u2015\u2212\\-]+")


def tokens(s: str) -> list[str]:
    return _TOKEN.findall(s.lower())


def fold_dashes(s: str) -> str:
    """Hyphen and dash variants become spaces, so a phrase matches however it is punctuated."""
    return " ".join(_DASHES.sub(" ", s).split())


@dataclass(frozen=True)
class Normalised:
    text: str
    unaccented: str
    terms: list[str]            # every token to search for: both forms, plus glossary expansions
    plain: bool                 # True when the learner typed no diacritics at all
    concepts: list[list[str]]   # matched glossary entries; each is its interchangeable forms
    loose: list[str]            # content tokens of the query outside any matched glossary form
    matched: tuple[str, ...] = ()   # the glossary terms found in the query, as the glossary writes them


def _word_pattern(needle: str) -> re.Pattern:
    return re.compile(rf"(?<!\w){re.escape(needle)}(?!\w)")


def normalise(query: str, glossary: list[dict]) -> Normalised:
    text = unicodedata.normalize("NFC", query).strip().lower()
    unaccented = unaccent(text)
    plain = text == unaccented
    # Accent-sensitive matching, so "sẽ" never triggers the abbreviation "Se"; a query typed
    # entirely without diacritics is matched accent-free instead.
    scoring_text = fold_dashes(unaccented if plain else text)
    fold = (lambda s: fold_dashes(unaccent(s))) if plain else fold_dashes

    concepts: list[list[str]] = []
    matched: list[str] = []
    residual = scoring_text
    for entry in glossary:
        forms = [fold(f.lower()) for f in [entry["term"], *entry["synonyms"]]]
        hits = [f for f in forms if _word_pattern(f).search(scoring_text)]
        if hits:
            concepts.append(forms)
            matched.append(entry["term"])
            for f in hits:
                residual = _word_pattern(f).sub(" ", residual)

    for frame in FRAMES:
        residual = _word_pattern(frame).sub(" ", residual)

    loose: list[str] = []
    for tok in tokens(residual):
        if tok not in STOPWORDS and tok not in loose:
            loose.append(tok)

    expansions = [f for forms in concepts for f in forms]
    terms: list[str] = []
    for source in [text, unaccented, *expansions, *(unaccent(e) for e in expansions)]:
        for tok in tokens(source):
            if tok not in STOPWORDS and tok not in terms:
                terms.append(tok)
    return Normalised(text=text, unaccented=unaccented, terms=terms, plain=plain, concepts=concepts, loose=loose,
                      matched=tuple(matched))
