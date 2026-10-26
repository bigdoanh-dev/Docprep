"""The tutor's "Gợi ý", checked in code before the learner sees it. Pure.

A hint may point at what to look at; it may not give the answer. A model can be asked not to, but
only code can be relied on, so a hint that could give the answer away is thrown away and the learner
gets a pointer to the source instead. The check errs on the side of throwing away: a good hint lost
costs a weaker hint, a leaked answer is recorded as knowledge the learner does not have.
"""
import re
import unicodedata
from decimal import Decimal, InvalidOperation

MAX_LENGTH = 400

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_THOUSANDS = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?")
# Words that introduce an option: "đáp án A", "chọn C", "loại trừ B", "không phải B", "ý A", "the answer is A".
_LEAD = r"(?:dap an|phuong an|lua chon|chon|cau tra loi|tra loi|loai tru|loai bo|loai|bo|khong phai|y|cau|option|answer)"
_FILLER = r"(?: (?:dung nhat|dung|chinh xac|se|la|is))*"
_NAMES_AN_OPTION = r"(?:^| )" + _LEAD + _FILLER + r" (?:{keys})(?: |$)"
# "A là đúng", "B, C, D đều sai": a key, or a list of keys, judged right or wrong.
_JUDGES_AN_OPTION = r"(?:^| )(?:{keys})(?: (?:va |hoac )?(?:{keys}))*(?: (?:la|deu|se|moi))* (?:dung|sai|hop ly|chinh xac)(?: |$)"
# "(A)", "[A]", '"A"', "**A**", "A)": a key set off by punctuation.
_KEY_SET_OFF = r"[(\[\"'*]\s*(?:{keys})\s*[)\]\"'*]|(?:^|\s)(?:{keys})\)"
_BY_POSITION = re.compile(r"(?:^| )(?:phuong an|dap an|lua chon|y|cau) (?:dau tien|thu nhat|thu hai|thu ba|thu tu|thu nam|cuoi cung|cuoi)(?: |$)")


def _plain(text: str) -> str:
    """Lower case, no accents, single spaces: so that wording, not typography, is compared."""
    text = text.replace("đ", "d").replace("Đ", "D")
    text = "".join(ch for ch in unicodedata.normalize("NFD", text) if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().lower()


def _number(match: re.Match) -> str:
    """One way of writing a number: "2.000" is two thousand, "2,5", "2.5" and "2,50" are the same."""
    token = match.group()
    token = token.replace(".", "").replace(",", ".") if _THOUSANDS.fullmatch(token) else token.replace(",", ".")
    try:
        value = Decimal(token)
    except InvalidOperation:
        return token
    return format(value.normalize(), "f")


def _words(text: str) -> str:
    """`_plain`, with numbers written one way, "phần trăm" as "%", and no other punctuation."""
    text = _NUMBER.sub(_number, _plain(text)).replace("phan tram", "%")
    text = re.sub(r"[^a-z0-9.%]+|\.(?!\d)", " ", text)
    return re.sub(r"\s+", " ", re.sub(r"\s+%", "%", text)).strip()


def _numbers(words: str) -> set[str]:
    return set(re.findall(r"\d+(?:\.\d+)?", words))


def _holds(words: str, phrase: str) -> bool:
    return bool(phrase) and f" {phrase} " in f" {words} "


def _parts(option_text: str) -> list[str]:
    """The option's text and each piece of it outside and inside brackets: "Tỷ suất chênh (OR)" is
    given away by "tỷ suất chênh" and by "OR" alike."""
    pieces = [option_text, *re.split(r"[()\[\]]", option_text)]
    return [w for w in dict.fromkeys(_words(piece) for piece in pieces) if w]


def reveals_answer(hint: str, options: list[dict], stem: str = "") -> bool:
    """Whether the hint could give the answer away. It does when it:
    - gives a number the question itself does not give (a result, or a figure from elsewhere);
    - contains the correct option's text, or the text of every other option;
    - points at an option, by its key or its position, to choose it or to rule it out."""
    plain, words = _plain(hint), _words(hint)
    if _numbers(words) - _numbers(_words(stem)):
        return True
    correct = [o for o in options if o.get("is_correct")]
    wrong = [o for o in options if not o.get("is_correct")]
    if any(_holds(words, part) for o in correct for part in _parts(o["text"])):
        return True
    if wrong and all(_holds(words, _words(o["text"])) for o in wrong):
        return True
    if _BY_POSITION.search(words):
        return True
    keys = "|".join(re.escape(_plain(o["key"])) for o in options)
    if not keys:
        return False
    return bool(re.search(_NAMES_AN_OPTION.format(keys=keys), words) or re.search(_JUDGES_AN_OPTION.format(keys=keys), words)
                or re.search(_KEY_SET_OFF.format(keys=keys), plain))


def usable(hint: object, options: list[dict], stem: str = "") -> bool:
    """A hint worth showing: a short text that does not give the answer away."""
    return isinstance(hint, str) and 0 < len(hint.strip()) <= MAX_LENGTH and not reveals_answer(hint, options, stem)


def pointer(source: dict) -> str:
    """The fallback, written by code: where in the source to look. `source` has document, chapter,
    section, page and article, as a citation does."""
    where = source.get("section") or source.get("chapter")
    place = f"trang {source['page']}" if source.get("page") else source.get("article")
    if not where:
        return f"Hãy xem lại {source['document']}."
    return f"Hãy xem lại {where} trong {source['document']}, {place}." if place else f"Hãy xem lại {where} trong {source['document']}."
