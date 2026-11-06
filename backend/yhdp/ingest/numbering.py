"""Heading numbering schemes used in Vietnamese MOH guidelines.

Families: `pl` (PHỤ LỤC N), `roman` (I., IV.), `letter` (A., B1., C.1., C.2.5.1.),
`num` (1., 2.3, 3.1.2.). Depth is the nesting level within a family.
"""

import re
from dataclasses import dataclass

_PL = re.compile(r"^(?:PHỤ LỤC|Phụ lục)\s+(\d+(?:\.\d+)*)(?=[\s:.]|$)")
_ROMAN = re.compile(r"^([IVX]+)\.?(?=\s|$)")
_VALID_ROMAN = re.compile(r"^(X{0,3})(IX|IV|V?I{0,3})$")
# Letter + digits ("B1", "C.1", "C1.1", "C.2.4"), or a bare letter that must end in a dot ("A.").
_LETTER = re.compile(r"^(?:([A-Z])\.?(\d+(?:\.\d+)*)\.?|([A-Z])\.)(?=\s|$)")
_NUM = re.compile(r"^(\d+(?:\.\d+)*)\.?(?=\s|$)")


@dataclass(frozen=True)
class Numbering:
    family: str  # pl | roman | letter | num
    token: str  # anchor token, e.g. "IV", "C.1", "2.3", "pl8"
    depth: int
    letter: str | None = None
    parts: tuple[int, ...] = ()


def parse_numbering(text: str) -> Numbering | None:
    text = text.strip()
    if m := _PL.match(text):
        return Numbering("pl", f"pl{m.group(1)}", 0)
    if (m := _ROMAN.match(text)) and _VALID_ROMAN.match(m.group(1)):
        return Numbering("roman", m.group(1), 1)
    if m := _LETTER.match(text):
        if m.group(3):
            return Numbering("letter", m.group(3), 1, letter=m.group(3))
        parts = tuple(int(x) for x in m.group(2).split("."))
        token = text[: m.end()].rstrip(".")
        return Numbering("letter", token, 1 + len(parts), letter=m.group(1), parts=parts)
    if m := _NUM.match(text):
        parts = tuple(int(x) for x in m.group(1).split("."))
        return Numbering("num", m.group(1), len(parts), parts=parts)
    return None
