"""Post-check tier 1 (code, every answer): a claim is shown only if its citation holds up.

A claim survives when every passage it cites was retrieved, each of those passages has a quote
(an excerpt of at least three words) that really appears in it, and every number in the claim
appears in a cited passage. Anything else is dropped; the pipeline turns "nothing left" into
insufficient_evidence.

This is a lexical check: it cannot tell whether the quoted words actually support the claim.
That judgement is tier 2 (a model call, off by default).
"""
import re
import unicodedata
from dataclasses import dataclass

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_THOUSANDS = re.compile(r"^\d{1,3}(?:\.\d{3})+$")


@dataclass(frozen=True)
class Claim:
    text: str
    passage_ids: list[str]


@dataclass(frozen=True)
class Evidence:
    passage_id: str
    quote: str


def resolve_ids(claims: list[Claim], evidence: list[Evidence], sent: list[str]) -> tuple[list[Claim], list[Evidence]]:
    """Map an id the model shortened back to the passage it names. Corpus ids are long
    ("yhdp:<doc hash>:<passage hash>") and a model sometimes copies only the part after the last ':'.
    An id is rewritten only when that tail names exactly one passage that was sent; anything else is
    left as written, so the check below still drops it."""
    known = set(sent)
    tails: dict[str, list[str]] = {}
    for pid in sent:
        tails.setdefault(pid.rsplit(":", 1)[-1], []).append(pid)

    def fix(pid: str) -> str:
        if pid in known:
            return pid
        match = tails.get(pid.rsplit(":", 1)[-1], [])
        return match[0] if len(match) == 1 else pid

    return ([Claim(c.text, [fix(p) for p in c.passage_ids]) for c in claims],
            [Evidence(fix(e.passage_id), e.quote) for e in evidence])


def _canonical(number: str) -> str:
    """Vietnamese formats: '.' groups thousands (2.000), ',' is the decimal mark (2,5)."""
    if _THOUSANDS.match(number):
        return number.replace(".", "")
    number = number.replace(",", ".")
    if "." in number:
        number = number.rstrip("0").rstrip(".")
    return number


def numbers_in(text: str) -> set[str]:
    return {_canonical(m) for m in _NUMBER.findall(text)}


MIN_QUOTE_WORDS = 3  # a quote has to be an excerpt; a stray word would "support" anything
_TYPOGRAPHY = {ord(c): "-" for c in "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"}
_TYPOGRAPHY.update({ord(c): '"' for c in "\u201c\u201d"})
_TYPOGRAPHY.update({ord(c): chr(39) for c in "\u2018\u2019"})


# Chunked tables keep line breaks inside a cell as <br>; a model copying the cell writes a newline.
_LINE_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)


def _squash(s: str) -> str:
    """Whitespace (including a table cell's <br>), case, and dash/quote typography do not matter
    when matching a quote. The words themselves must still match exactly."""
    s = _LINE_BREAK.sub(" ", unicodedata.normalize("NFC", s))
    return " ".join(s.translate(_TYPOGRAPHY).split()).casefold()


def check_tier1(claims: list[Claim], evidence: list[Evidence], passages: dict[str, str]) -> list[Claim]:
    supported_ids = {e.passage_id for e in evidence
                     if e.passage_id in passages and len(e.quote.split()) >= MIN_QUOTE_WORDS
                     and _squash(e.quote) in _squash(passages[e.passage_id])}
    kept = []
    for claim in claims:
        if not claim.passage_ids or any(pid not in passages for pid in claim.passage_ids):
            continue
        if not set(claim.passage_ids) <= supported_ids:  # every citation shown needs its own quote
            continue
        cited_text = " ".join(passages[pid] for pid in claim.passage_ids)
        if not numbers_in(claim.text) <= numbers_in(cited_text):
            continue
        kept.append(claim)
    return kept
