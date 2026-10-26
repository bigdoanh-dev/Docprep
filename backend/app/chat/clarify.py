"""Asking back before answering (handover/04, "Clarification"). Pure.

Experts flag a glossary term as ambiguous and give its senses a common `sense_group`. A question
that names the term, and none of its senses, is not answered: the learner is offered the senses,
each as the same question with the term replaced. No search and no model call are spent.
"""
import re
import unicodedata

from app.text import unaccent

MAX_OPTIONS = 4


def _pattern(phrase: str) -> re.Pattern:
    """The phrase as whole words, however it is spaced or hyphenated."""
    words = [re.escape(w) for w in re.findall(r"\w+", phrase.lower())]
    return re.compile(r"(?<!\w)" + r"[\s‐-―−\-]+".join(words) + r"(?!\w)")


def options(query: str, glossary: list[dict]) -> tuple[str, list[dict]] | None:
    """The ambiguous term the question names and 2–4 options `{term, label_vi, query}`, or None when
    there is nothing to ask: no flagged term in the question, one of its senses already named, or
    fewer than two senses to choose from. A question typed without diacritics is matched without them."""
    text = unicodedata.normalize("NFC", query)
    low = text.lower()
    plain = low == unaccent(low)

    def found(phrase: str) -> re.Match | None:
        return _pattern(unaccent(phrase) if plain else phrase).search(low)

    for entry in glossary:
        if not entry.get("ambiguous") or not entry.get("sense_group"):
            continue
        hit = next((m for m in (found(form) for form in [entry["term"], *entry["synonyms"]]) if m), None)
        if hit is None:
            continue
        senses = sorted((g for g in glossary if g.get("sense_group") == entry["sense_group"] and not g.get("ambiguous")),
                        key=lambda g: g["term"])
        if len(senses) < 2 or any(found(form) for g in senses for form in [g["term"], *g["synonyms"]]):
            continue
        capital = text[hit.start()].isupper()

        def asked(sense: str) -> str:
            return text[:hit.start()] + (sense[0].upper() + sense[1:] if capital else sense) + text[hit.end():]

        return entry["term"], [{"term": g["term"], "label_vi": g["term"][0].upper() + g["term"][1:], "query": asked(g["term"])}
                               for g in senses[:MAX_OPTIONS]]
    return None
