"""Undo PDF-to-docx damage (QĐ 5642): hard-wrapped lines and tables flattened to one cell per line.

Both rules work on plain line texts so they can be tested without a .docx.
"""

import re

TERMINAL = ".:;!?"
WRAP_MIN_CHARS = 60  # the source wraps at ~85 chars; a shorter line usually ends its paragraph
RUN_MAX_CHARS = 30  # flattened table cells are short …
RUN_MIN_LINES = 8  # … and come in long runs
MARKER = re.compile(r"^(?:[-•–−*+]\s|[a-zđ][.)]\s|\d+\)\s)")
# "1. ", "3.1. ", "IV. " — but not "7 ngày tuổi" or "150.000 đv/kg", which do wrap onto a new line
NUMBERED = re.compile(r"^(?:\d+(?:\.\d+)*|[IVX]+)\.\s")


def starts_block(text: str) -> bool:
    """A bullet, a label like 'a.' / '1)', or a numbered heading never continues a line."""
    return bool(MARKER.match(text) or NUMBERED.match(text))


def should_join(prev: str, nxt: str) -> bool:
    if not prev or not nxt or prev[-1] in TERMINAL or starts_block(nxt):
        return False
    return len(prev) >= WRAP_MIN_CHARS or nxt[0].islower()


def table_runs(lines: list[str | None]) -> list[tuple[int, int]]:
    """[start, end) index ranges of ≥ RUN_MIN_LINES consecutive short, non-list lines.

    None marks an element that can't be part of a run (a heading, a real table, an image).
    """
    runs, start = [], None
    for i, line in enumerate([*lines, None]):
        short = line is not None and 0 < len(line) < RUN_MAX_CHARS and not MARKER.match(line)
        prev = lines[i - 1] if i else None
        if short and start is None and prev and len(prev) >= WRAP_MIN_CHARS \
                and should_join(prev, line):
            short = False  # the tail of a wrapped sentence, not a cell
        if short and start is None:
            start = i
        elif not short and start is not None:
            if i - start >= RUN_MIN_LINES:
                runs.append((start, i))
            start = None
    return runs
