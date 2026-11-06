"""Parse native .docx guidelines (QĐ 2760, QĐ 5904, QĐ 5642) into the common document model.

Handles: heading styles or bold numbered headings (any mix of I./A./B1./C.1./1./1.1.),
centred all-caps parts and PHỤ LỤC appendices, front matter, tables of contents and
editorial lists and reference lists (dropped), bold-prefix headings, grouped lists, GFM tables with merged
cells, single-cell boxes, formulas, cross-references to appendices, and figures
(both DrawingML and legacy VML images). Sources converted from PDF (needs_unwrap) first get
their hard-wrapped lines joined and their flattened tables collected (see unwrap.py).
"""

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.table import Table
from docx.text.paragraph import Paragraph

from yhdp.ingest.model import Block, Loc, ParsedDoc, make_anchor
from yhdp.ingest.numbering import parse_numbering
from yhdp.ingest.sections import Heading, SectionStack
from yhdp.ingest.unwrap import should_join, table_runs
from yhdp.sources import Source, nfc_fold

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
BLIP = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
VML_IMAGE = "{urn:schemas-microsoft-com:vml}imagedata"

FRONT_MATTER = "Quyết định ban hành"
MIN_FIGURE_BYTES = 2048  # smaller images are bullet glyphs / arrows
MAX_HEADING_CHARS = 200

DROP_SECTIONS = re.compile(
    r"^(MỤC LỤC|DANH SÁCH BAN BIÊN SOẠN|BAN BIÊN SOẠN|THAM GIA BIÊN SOẠN|TÀI LIỆU THAM KHẢO)")
BOILERPLATE = [
    re.compile(r"^\(Ban hành kèm theo Quyết định"),
    re.compile(r"^[A-Z][a-z]{2} \d{1,2}, \d{4} · @\S+$"),  # docs export byline
]
LIST_ITEM = re.compile(r"^(?:(?P<bullet>[-•–−*])|(?P<sub>\+)|(?P<label>[a-zđ]\)|\d+\)|\d+\.))\s+(?P<rest>.+)$")
APPENDIX_REF = re.compile(r"(?i)phụ lục\s+(\d+(?:\.\d+)*)")


def clean(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\xa0", " ").replace("\t", " ")
    text = text.replace("\uf0b7", "•")  # Symbol-font bullet
    return re.sub(r"\s+", " ", text).strip()


def is_caps(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return len(letters) >= 3 and sum(c.isupper() for c in letters) / len(letters) >= 0.9


@dataclass
class Para:
    text: str
    style: str
    all_bold: bool
    bold_prefix: str  # leading bold text (raw, unnormalised)
    raw: str  # concatenated run text, aligned with bold_prefix
    centered: bool
    image_rids: list[str]

    @classmethod
    def read(cls, p: Paragraph) -> "Para":
        style_bold = bool(p.style is not None and p.style.font.bold)
        runs = list(p.runs)
        bold = [r.bold if r.bold is not None else style_bold for r in runs]
        texty = [b for r, b in zip(runs, bold) if r.text.strip()]
        prefix = []
        for r, b in zip(runs, bold):
            if not b and r.text.strip():
                break
            prefix.append(r.text)
        rids = [el.get(f"{R}embed") for el in p._p.iter(BLIP)]
        rids += [el.get(f"{R}id") for el in p._p.iter(VML_IMAGE)]
        align = p.alignment if p.alignment is not None else p.paragraph_format.alignment
        return cls(text=clean(p.text), style=p.style.name if p.style is not None else "",
                   all_bold=bool(texty) and all(texty), bold_prefix="".join(prefix),
                   raw="".join(r.text for r in runs), centered=align == WD_ALIGN_PARAGRAPH.CENTER,
                   image_rids=[r for r in rids if r])

    @property
    def is_caps_title(self) -> bool:
        return self.centered and self.all_bold and is_caps(self.text)

    @property
    def is_plain_line(self) -> bool:
        """A body line that may be hard-wrapped or a flattened table cell."""
        if self.image_rids or not self.text:
            return False
        if self.style.startswith("Heading"):  # PDF conversion styled a wrapped tail "2, 3 (D1)."
            head = self.text[0]
            return (head.islower() or head.isdigit()) and parse_numbering(self.text) is None
        return self.style == "Normal" and not self.all_bold

    def joined(self, other: "Para") -> "Para":
        return Para(text=f"{self.text} {other.text}", style=self.style, all_bold=False,
                    bold_prefix=self.bold_prefix, raw=f"{self.raw} {other.raw}",
                    centered=self.centered, image_rids=[])


@dataclass
class FlatRun:
    """Consecutive one-cell-per-line paragraphs of a table flattened by PDF conversion."""
    lines: list[str]


def unwrap(items: list) -> list:
    """Join hard-wrapped Paras and collect flattened-table runs into FlatRuns. A styled heading
    also absorbs its wrapped tail ("5.3. … sang vùng" + "khác, đặc biệt …"), but only a tail
    starting lowercase, since body text after a heading starts with a capital."""
    items = [it for it in items if not (isinstance(it, Para) and not it.text and not it.image_rids)]
    plain = [it.text if isinstance(it, Para) and it.is_plain_line else None for it in items]
    runs = dict(table_runs(plain))
    out: list = []
    tail = None  # last physical line of out[-1] while it is a joinable Para
    tail_is_heading = False
    i = 0
    while i < len(items):
        if i in runs:
            out.append(FlatRun(lines=plain[i:runs[i]]))
            tail, i = None, runs[i]
            continue
        line = plain[i]
        if line is not None and tail is not None and should_join(tail, line) \
                and (not tail_is_heading or line[0].islower()):
            out[-1] = out[-1].joined(items[i])
            tail = line
        else:
            out.append(items[i])
            tail_is_heading = (line is None and isinstance(items[i], Para)
                               and items[i].style.startswith("Heading"))
            tail = items[i].text if tail_is_heading else line
        i += 1
    return out


@dataclass
class _Builder:
    source: Source
    figures_dir: Path
    blocks: list[Block] = field(default_factory=list)
    stack: SectionStack = field(default_factory=SectionStack)
    mode: str = "front"  # front | body | drop
    drop_level: int | None = None  # heading-style level of a dropped section; deeper ones stay dropped
    caps_buf: list[str] = field(default_factory=list)
    pending_pl: str | None = None  # "8" while collecting a PHỤ LỤC title
    list_buf: list[str] = field(default_factory=list)
    anchor: str = make_anchor([FRONT_MATTER])
    used_anchors: set[str] = field(default_factory=set)
    figure_count: dict[str, int] = field(default_factory=dict)

    # --- section handling -------------------------------------------------------------
    def path(self) -> list[str]:
        return [FRONT_MATTER] if self.mode == "front" else self.stack.path()

    def loc(self) -> Loc:
        return Loc(section_path=self.path(), anchor=self.anchor)

    def is_title(self, text: str) -> bool:
        t, h = nfc_fold(self.source.title), nfc_fold(text)
        return t in h or (h in t and len(h) >= 0.6 * len(t))

    def open_heading(self, heading: Heading, transparent: bool = False) -> None:
        self.flush_list()
        self.mode, self.drop_level = "body", None
        self.stack.push(heading, transparent=transparent)
        anchor = make_anchor(self.stack.path())
        if not transparent:
            base, n = anchor, 2
            while anchor in self.used_anchors:
                anchor, n = f"{base}~{n}", n + 1
            self.used_anchors.add(anchor)
        self.anchor = anchor
        if not transparent:
            self.blocks.append(Block(kind="heading", text=heading.text, loc=self.loc()))

    def flush_caps(self) -> None:
        if self.pending_pl is None and not self.caps_buf:
            return
        title = " ".join(self.caps_buf)
        pl, self.pending_pl, self.caps_buf = self.pending_pl, None, []
        if pl is not None:
            text = f"Phụ lục {pl}: {title}" if title else f"Phụ lục {pl}"
            self.open_heading(Heading(text=text, family="pl", depth=0))
        elif DROP_SECTIONS.match(title.upper()):  # before is_title: "BAN BIÊN SOẠN “<title>”"
            self.flush_list()
            self.mode, self.drop_level = "drop", None
        elif self.is_title(title):
            self.open_heading(Heading(text=title, family="part", depth=0), transparent=True)
        elif self.mode == "front":
            self.emit_text(f"**{title}**")
        elif self.stack.entries and self.stack.entries[0].family == "pl":
            self.open_heading(Heading(text=title, family="caps", depth=1))
        else:
            self.open_heading(Heading(text=title, family="part", depth=0))

    # --- content ----------------------------------------------------------------------
    def emit(self, block: Block) -> None:
        if self.mode != "drop":
            self.blocks.append(block)

    def emit_text(self, text: str) -> None:
        self.flush_list()
        refs = sorted({f"pl{n}" for n in APPENDIX_REF.findall(text)})
        self.emit(Block(kind="para", text=text, loc=self.loc(), refs=refs))

    def flush_list(self) -> None:
        if self.list_buf:
            text = "\n".join(self.list_buf)
            refs = sorted({f"pl{n}" for n in APPENDIX_REF.findall(text)})
            self.list_buf = []
            self.emit(Block(kind="list", text=text, loc=self.loc(), refs=refs))

    def add_list_item(self, line: str) -> None:
        if self.mode != "drop":
            self.list_buf.append(line)

    # --- element handlers -------------------------------------------------------------
    def paragraph(self, para: Para, related_parts) -> None:
        text = para.text
        if para.is_caps_title and (n := parse_numbering(text)) and n.family == "pl":
            self.flush_caps()
            self.pending_pl = n.token.removeprefix("pl")
            return
        if para.is_caps_title and parse_numbering(text) is None and len(self.caps_buf) < 3:
            self.caps_buf.append(text)
            return
        self.flush_caps()

        if text and any(p.match(text) for p in BOILERPLATE):
            return
        if text and self.heading(para):
            pass
        elif text:
            self.body_text(para)
        for rid in para.image_rids:
            self.figure(related_parts[rid])

    def heading(self, para: Para) -> bool:
        """Open a section if the paragraph is a heading; return True if it was consumed."""
        text = para.text
        if para.style.startswith("Heading"):
            level = int(re.sub(r"\D", "", para.style) or 1)
            if self.mode == "drop" and self.drop_level is not None and level > self.drop_level:
                return True  # e.g. each reference under TÀI LIỆU THAM KHẢO
            if DROP_SECTIONS.match(text.upper()):
                self.flush_list()
                self.mode, self.drop_level = "drop", level
            elif level == 1 and self.is_title(text):
                self.open_heading(Heading(text=text, family="part", depth=0), transparent=True)
            elif (n := parse_numbering(text)) and n.family != "pl":
                # PDF conversions style "BỆNH …" and its "1. ĐẠI CƯƠNG" alike; numbering decides.
                # Styled "Phụ lục" keeps its style level so the next "Phần" doesn't nest under it.
                self.open_heading(Heading(text=text, family=n.family, depth=n.depth,
                                          letter=n.letter, parts=n.parts))
            else:
                self.open_heading(Heading(text=text, family="style", depth=level))
            return True
        if self.mode == "drop" and self.drop_level is not None:
            return False
        if para.all_bold and len(text) <= MAX_HEADING_CHARS:
            candidate = text.rstrip(":").strip()
        elif para.bold_prefix.strip() and not para.all_bold:
            candidate = clean(para.bold_prefix).rstrip(":").strip()
        else:
            return False
        n = parse_numbering(candidate)
        if n is None or n.family == "pl":
            return False
        self.open_heading(Heading(text=candidate, family=n.family, depth=n.depth,
                                  letter=n.letter, parts=n.parts))
        if not para.all_bold:
            rest = clean(para.raw[len(para.bold_prefix):]).lstrip(":").strip()
            if rest:
                self.emit_text(rest)
        return True

    def body_text(self, para: Para) -> None:
        text = para.text
        if para.style == "Code" and "\\" in text:
            self.flush_list()
            self.emit(Block(kind="formula", text=f"$${text}$$", loc=self.loc()))
            return
        if para.all_bold:  # bold labels ("* Những lưu ý…", "Lưu ý:") stay as bold paragraphs
            self.emit_text("**" + text.replace("*", "\\*") + "**")
            return
        if m := LIST_ITEM.match(text):
            rest = m.group("rest")
            if m.group("sub"):
                self.add_list_item(f"  - {rest}")
            elif m.group("label"):
                self.add_list_item(f"- {m.group('label')} {rest}")
            else:
                self.add_list_item(f"- {rest}")
            return
        if para.style.startswith("List"):
            self.add_list_item(f"- {text}")
            return
        self.emit_text(text)

    def flat_run(self, run: FlatRun) -> None:
        self.flush_caps()
        self.flush_list()
        self.emit(Block(kind="para", text="\n".join(run.lines), loc=self.loc(),
                        needs_review=["table_flattened"]))

    def figure(self, part) -> None:
        blob = part.blob
        if len(blob) < MIN_FIGURE_BYTES or self.mode != "body":
            return
        self.flush_list()
        n = self.figure_count[self.anchor] = self.figure_count.get(self.anchor, 0) + 1
        ext = Path(part.partname).suffix or ".png"
        name = f"{self.anchor.replace('/', '_')}-{n}{ext}"
        self.figures_dir.mkdir(parents=True, exist_ok=True)
        (self.figures_dir / name).write_bytes(blob)
        caption = self.path()[-1] if self.path() else self.source.title
        self.emit(Block(kind="figure", text=f"[Hình: {caption}]", loc=self.loc(),
                        figure_path=f"{self.figures_dir.name}/{name}", caption=caption))

    def table(self, table: Table) -> None:
        self.flush_caps()
        self.flush_list()
        if self.mode != "body":
            return
        rows = [[cell_text(c) for c in row.cells] for row in table.rows]
        rows = [r for r in rows if any(r)]
        if not rows:
            return
        caption = self.path()[-1] if self.path() else None
        if len(rows) == 1 and len(rows[0]) == 1 or all(len(set(r)) == 1 for r in rows):
            text = "\n\n".join(r[0] for r in rows).replace("<br>", "\n")
            self.emit(Block(kind="box", text=text.replace("\\|", "|"), loc=self.loc(), caption=caption))
            return
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        lines = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
        lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        self.emit(Block(kind="table", text="\n".join(lines), loc=self.loc(), caption=caption))


def cell_text(cell) -> str:
    paras = [clean(p.text) for p in cell.paragraphs]
    return "<br>".join(p for p in paras if p).replace("|", "\\|")


def parse_docx(path: Path, source: Source, figures_dir: Path) -> ParsedDoc:
    doc = Document(str(path))
    related = doc.part.related_parts
    items = [Para.read(Paragraph(el, doc)) if el.tag == f"{W}p" else Table(el, doc)
             for el in doc.element.body.iterchildren() if el.tag in (f"{W}p", f"{W}tbl")]
    if source.needs_unwrap:
        items = unwrap(items)
    b = _Builder(source=source, figures_dir=figures_dir)
    for item in items:
        if isinstance(item, Para):
            b.paragraph(item, related)
        elif isinstance(item, FlatRun):
            b.flat_run(item)
        else:
            b.table(item)
    b.flush_caps()
    b.flush_list()
    return ParsedDoc(doc_id=source.doc_id, blocks=b.blocks)


def outline(doc: ParsedDoc) -> str:
    """Heading tree with per-section block counts, for eyeballing a parse."""
    lines = [f"# Outline: {doc.doc_id}", ""]
    counts: dict[str, dict[str, int]] = {}
    order: list[tuple[str, list[str]]] = []
    for blk in doc.blocks:
        a = blk.loc.anchor
        if a not in counts:
            counts[a] = {}
            order.append((a, blk.loc.section_path))
        if blk.kind != "heading":
            counts[a][blk.kind] = counts[a].get(blk.kind, 0) + 1
    for anchor, path in order:
        title = path[-1] if path else "(root)"
        stats = ", ".join(f"{k} {v}" for k, v in sorted(counts[anchor].items()))
        lines.append(f"{'  ' * (len(path) - 1)}- {title}  `{anchor}`" + (f"  ({stats})" if stats else ""))
    totals: dict[str, int] = {}
    for blk in doc.blocks:
        totals[blk.kind] = totals.get(blk.kind, 0) + 1
    lines += ["", "Totals: " + ", ".join(f"{k} {v}" for k, v in sorted(totals.items()))]
    return "\n".join(lines) + "\n"
