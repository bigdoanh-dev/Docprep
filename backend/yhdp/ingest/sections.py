"""Section stack: turns a flat sequence of headings into section paths.

Guidelines mix numbering schemes (I. → A. → B1. → C.1. → 1. → 1.1.), so a heading's level
is not fixed by its pattern. A heading nests under the deepest open heading of the same
family whose number is its prefix; otherwise it replaces the first open heading of its
family (closing everything below); a new family nests under whatever is open.
"""

from dataclasses import dataclass, field

from yhdp.ingest.numbering import parse_numbering

ROOT_FAMILIES = {"pl", "part"}  # appendices and unnumbered top-level parts reset to root


@dataclass(frozen=True)
class Heading:
    text: str
    family: str  # pl | part | roman | letter | num | style | caps
    depth: int
    letter: str | None = None
    parts: tuple[int, ...] = ()

    @classmethod
    def from_text(cls, text: str) -> "Heading":
        n = parse_numbering(text)
        if n is None:
            raise ValueError(f"not a numbered heading: {text!r}")
        return cls(text=text, family=n.family, depth=n.depth, letter=n.letter, parts=n.parts)

    def is_parent_of(self, child: "Heading") -> bool:
        if self.family != child.family or self.depth >= child.depth:
            return False
        if self.family == "letter" and self.letter != child.letter:
            return False
        if self.family in ("letter", "num"):
            return child.parts[: len(self.parts)] == self.parts
        return self.family == "style"


@dataclass
class SectionStack:
    entries: list[Heading] = field(default_factory=list)

    def push(self, heading: Heading, transparent: bool = False) -> None:
        if heading.family in ROOT_FAMILIES:
            self.entries = []
        else:
            parent = next((i for i in range(len(self.entries) - 1, -1, -1)
                           if self.entries[i].is_parent_of(heading)), None)
            if parent is not None:
                self.entries = self.entries[: parent + 1]
            else:
                same = next((i for i, h in enumerate(self.entries)
                             if h.family == heading.family), None)
                if same is not None:
                    self.entries = self.entries[:same]
        if not transparent:
            self.entries.append(heading)

    def path(self) -> list[str]:
        return [h.text for h in self.entries]
