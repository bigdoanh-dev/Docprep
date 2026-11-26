"""Reconstruct a reviewable outline from word positions in Tesseract TSV."""
import re
from collections import defaultdict
from dataclasses import dataclass, replace
from difflib import SequenceMatcher
from itertools import groupby
from statistics import median

from app.text import unaccent

from .model import Block, Loc, make_anchor
from .sections import Heading, SectionStack


@dataclass(frozen=True)
class Word:
    text: str
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class Line:
    paragraph: tuple[str, str]
    words: tuple[Word, ...]

    @property
    def text(self):
        return " ".join(w.text for w in self.words)

    @property
    def height(self):
        return median(w.height for w in self.words)


CHAPTER = re.compile(r"^(?:chuong|phan|phu luc)\s+(?:\d+|[ivxlcdm]+)(?:[.:]?\s|[.:]?$)", re.I)
TABLE_CAPTION = re.compile(r"^bang\s+\d+(?:\.\d+)*\s*[:.\s]", re.I)
HEAD_WORDS = re.compile(r"\b(dai cuong|dinh nghia|phan loai|chan doan|dieu tri|lam sang|"
                        r"nguyen nhan|dich te hoc|du phong|phong benh|co che|tai lieu tham khao|"
                        r"bien chung|trieu chung|yeu to nguy co|chan doan phan biet)\b")


# Standard section names of clinical guidelines. OCR often drops their diacritics ("CHAN DOAN").
# Only multi-syllable terms: a single unaccented syllable ("CAP") is ambiguous in Vietnamese.
HEADING_TERMS = (
    "TÀI LIỆU THAM KHẢO", "CẬN LÂM SÀNG", "LÂM SÀNG", "CHẨN ĐOÁN", "XÁC ĐỊNH", "PHÂN BIỆT", "ĐIỀU TRỊ",
    "ĐẠI CƯƠNG", "ĐỊNH NGHĨA", "NGUYÊN NHÂN", "TIÊN LƯỢNG", "TIẾN TRIỂN", "BIẾN CHỨNG", "TRIỆU CHỨNG",
    "PHÒNG BỆNH", "PHÒNG TRÁNH", "PHÒNG NGỪA", "DỰ PHÒNG", "XỬ TRÍ", "CỤ THỂ", "CƠ CHẾ", "PHÂN LOẠI",
    "MỨC ĐỘ", "NGỘ ĐỘC", "HÓA CHẤT", "DIỆT CHUỘT", "CÂU HỎI", "NGUYÊN TẮC", "THEO DÕI",
)
_TERMS = sorted(((unaccent(t).split(), t.split()) for t in HEADING_TERMS), key=lambda term: -len(term[0]))
_EDGE = re.compile(r"^\W+|\W+$")


def restore_heading(text):
    """Restore diacritics of known section terms; other words are left as OCR read them."""
    tokens = text.split(" ")
    out, i = list(tokens), 0
    while i < len(tokens):
        for key, phrase in _TERMS:
            seg = tokens[i:i + len(key)]
            if len(seg) == len(key) and all(_EDGE.sub("", unaccent(t)) == k for t, k in zip(seg, key)):
                for j, (token, word) in enumerate(zip(seg, phrase)):
                    core = _EDGE.sub("", token)
                    if core:
                        rep = word if core.isupper() else (word.lower().capitalize() if core[0].isupper()
                                                           else word.lower())
                        out[i + j] = token.replace(core, rep, 1)
                i += len(key)
                break
        else:
            i += 1
    return " ".join(out)


def _norm(text):
    return " ".join(re.sub(r"[^a-z0-9()]+", " ", unaccent(text)).split())


def strong_numbered(line):
    """An all-caps numbered section name ("4. DIEU TRI") is a heading even when OCR glued it to a paragraph."""
    text = line.text.strip()
    letters = [c for c in text if c.isalpha()]
    if not 4 <= len(letters) <= 65 or text.endswith((",", ";", "(")) or re.search(r"\.{3,}|…", text):
        return None
    if sum(c.isupper() for c in letters) / len(letters) < 0.92 or not HEAD_WORDS.search(unaccent(text)):
        return None
    try:
        return Heading.from_text(text)
    except ValueError:
        return None


def heading(line, body_height, standalone, margin, *, page_width):
    text = line.text.strip()
    plain = unaccent(text).lower()
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 4 or len(text) > 145 or re.search(r"\.{3,}|…|https?\s*:", text, re.I):
        return None
    if CHAPTER.match(plain) and standalone and not re.search(r"\s\d+$", plain[CHAPTER.match(plain).end():]):
        return Heading(text=text, family="part", depth=0)
    if TABLE_CAPTION.match(plain) or text.endswith((".", "?", ";", ",", "(")):
        return None
    caps = sum(c.isupper() for c in letters) / len(letters) >= 0.92
    if not standalone:
        return strong_numbered(line)
    try:
        numbered = Heading.from_text(text)
    except ValueError:
        numbered = None
    enlarged = line.height > body_height * 1.28
    if numbered and (caps or enlarged or (len(letters) <= 65 and HEAD_WORDS.search(plain))):
        return numbered
    # A large, visibly centered all-caps title is a new chapter/topic, not a list item.
    if not numbered and caps and enlarged and line.words[0].x >= margin + page_width * 0.06:
        return Heading(text=text, family="part", depth=0)
    if not numbered and enlarged and len(letters) <= 65 and 2 <= len(plain.split()) <= 9 and plain[0].isalpha():
        return Heading(text=text, family="style", depth=2)
    return None


def _cells(line, gap):
    groups = []
    for word in sorted(line.words, key=lambda w: w.x):
        if not groups or word.x - (groups[-1][-1].x + groups[-1][-1].width) >= gap:
            groups.append([])
        groups[-1].append(word)
    return [(g[0].x, " ".join(w.text for w in g)) for g in groups]


def _table_after(lines, start, height, width):
    """Require a caption and at least three aligned rows with a textual header."""
    gap = max(height * 2.5, width * 0.026)
    rows = []
    for line in lines[start:start + 45]:
        cells = _cells(line, gap)
        if not 2 <= len(cells) <= 8:
            break
        if rows and (len(cells) != len(rows[0]) or
                     any(abs(x - y) > width * 0.065 for (x, _), (y, _) in zip(cells, rows[0]))):
            break
        rows.append(cells)
    if len(rows) < 3 or not all(any(c.isalpha() for c in text) for _, text in rows[0]):
        return None
    values = [[text.replace("|", "\\|") for _, text in row] for row in rows]
    values.insert(1, ["---"] * len(values[0]))
    return "\n".join("| " + " | ".join(row) + " |" for row in values), len(rows)


def _geometry_rows(lines, height):
    """Collect cells on one baseline. OCR sometimes emits each table column in its own block."""
    words = sorted((word for line in lines for word in line.words), key=lambda w: (w.y + w.height / 2, w.x))
    rows = []
    for w in words:
        cy = w.y + w.height / 2
        if not rows or abs(cy - rows[-1][0]) > height * 0.55:
            rows.append((cy, []))
        rows[-1][1].append(w)
    return [Line(("table", str(i)), tuple(sorted(ws, key=lambda w: w.x))) for i, (_, ws) in enumerate(rows)]


def format_scan(pages, strip_patterns=(), outline=None, topics=None):
    """Use a single heading stack across pages; flag OCR text and unverified structures.

    `topics` lists the table-of-contents entries (chapter → optional group → topic). When a chapter has
    such entries, only lines matching the next expected entry open a topic; other large all-caps lines
    stay body text, so an OCR-garbled line cannot become a topic and a missed title cannot merge two topics.
    """
    stack = SectionStack()
    anchor = None
    seen = defaultdict(int)
    output = []
    outline = outline or {}
    topics = topics or []
    pointer = 0  # first topic not opened yet, in table-of-contents order
    current = None
    opened = set()
    front = False

    def chapter():
        return stack.entries[0].text if stack.entries else None

    def match_topic(text):
        """Index of a not-yet-opened topic near the expected position whose title this line is.

        Body order can differ slightly from the printed table of contents, so a small window around the
        expected entry is searched. A line matching the open topic best is a running header and is ignored.
        """
        u = _norm(text)
        best = None
        for k in range(max(0, pointer - 3), min(len(topics), pointer + 3)):
            if k in opened and k != current:
                continue
            key = _norm(topics[k]["match"])
            if topics[k]["chapter"] != chapter() or not u or len(u) > len(key) + 12:
                continue
            ratio = SequenceMatcher(None, key, u).ratio()
            if ratio >= 0.88 and (best is None or ratio > best[0]):
                best = (ratio, k)
        return best[1] if best and best[1] != current else None
    for lines, report in pages:
        if not lines:
            continue
        page = report["page"]
        width = report["width"]
        body_height = median(w.height for line in lines for w in line.words)
        margin = min(line.words[0].x for line in lines)
        standalone = {key for key, entries in groupby(lines, key=lambda ln: ln.paragraph) if len(list(entries)) == 1}
        flags = ["ocr_requires_review", "printed_page_unverified", "scan_layout_unverified"]
        if report.get("confidence", 100) < 70:
            flags.append("ocr_low_confidence")

        def location():
            return Loc(section_path=stack.path() or ["Đề mục chưa xác minh"],
                       anchor=anchor or f"unresolved-{page:04d}", image_indices=[page])

        def add(kind, text, extra=(), caption=None):
            text = re.sub(r"https?\s*:\s*//\s*(?:www\.)?trungtamthuoc\.com/?", "", text, flags=re.I)
            for pattern in strip_patterns:
                text = re.sub(pattern, "", text)
            if text.strip():
                output.append(Block(kind=kind, text=text, loc=location(), caption=caption,
                                    needs_review=flags + list(extra) + (["ocr_front_matter"] if front else [])
                                    + ([] if anchor else ["heading_unresolved"])))

        def push(title, flags):
            nonlocal anchor
            if "ocr_heading_requires_review" in flags and (fixed := restore_heading(title.text)) != title.text:
                title, flags = replace(title, text=fixed), (*flags, "ocr_heading_normalized")
            stack.push(title)
            base = make_anchor(stack.path())
            seen[base] += 1
            anchor = base if seen[base] == 1 else f"{base}~{seen[base]}"
            add("heading", title.text, flags)

        if page in outline:
            title = outline[page]
            front = not CHAPTER.match(unaccent(title).lower()) and not title.startswith("Phụ lục")
            push(Heading(text=title, family="part", depth=0), ("source_outline_requires_review",))

        # Tesseract order is retained for prose. Only captioned local table runs use coordinate order.
        i = 0
        while i < len(lines):
            line = lines[i]
            if not front and TABLE_CAPTION.match(unaccent(line.text).lower()):
                end = i + 1
                while end < len(lines) and end - i <= 60:
                    nxt = lines[end]
                    if TABLE_CAPTION.match(unaccent(nxt.text).lower()) or heading(
                        nxt, body_height, nxt.paragraph in standalone, margin, page_width=width
                    ):
                        break
                    end += 1
                candidate = lines[i + 1:end]
                table = _table_after(candidate, 0, body_height, width)
                if table:
                    text, count = table
                    add("table", text, ("ocr_table_layout_requires_review",), line.text)
                    i += count + 1
                    continue
                # Replace whole runs only when the geometry accounts for every source line.
                # Keep the original prose intact if a caption, wrapped cell or extra line makes it ambiguous.
                rows = _geometry_rows(candidate, body_height)
                if rows and (table := _table_after(rows, 0, body_height, width)) and table[1] == len(rows):
                    add("table", table[0], ("ocr_table_layout_requires_review",), line.text)
                    i = end
                    continue
                add("para", line.text, ("ocr_table_unresolved",))
                i += 1
                continue
            if not front and (k := match_topic(line.text)) is not None:
                entry, current = topics[k], k
                opened.add(k)
                while pointer in opened:
                    pointer += 1
                if entry["group"] and len(stack.entries) > 1 and stack.entries[1].text == entry["group"]:
                    stack.entries = stack.entries[:2]
                else:
                    stack.entries = stack.entries[:1]
                    if entry["group"]:
                        push(Heading(text=entry["group"], family="group", depth=1), ("source_outline_requires_review",))
                push(Heading(text=entry["title"], family="topic", depth=2), ("source_outline_requires_review",))
                i += 1
                # A long title can wrap onto the next line; consume it so it is not left as body text.
                if entry["cont"] and i < len(lines) and SequenceMatcher(
                    None, _norm(entry["cont"]), _norm(lines[i].text)
                ).ratio() >= 0.8:
                    i += 1
                continue
            title = None if front else heading(line, body_height, line.paragraph in standalone, margin, page_width=width)
            if title and outline and title.family == "part":
                if CHAPTER.match(unaccent(title.text).lower()):
                    # The numbered chapter is already supplied by the source outline (or repeats in a running header).
                    title = None
                elif any(t["chapter"] == chapter() for t in topics):
                    # Topics of this chapter come from the table of contents only.
                    title = None
                else:
                    stack.entries = stack.entries[:1]
                    title = Heading(text=title.text, family="topic", depth=1)
            if title:
                push(title, ("ocr_heading_requires_review",))
                i += 1
                continue
            j = i + 1
            while j < len(lines) and lines[j].paragraph == line.paragraph and not TABLE_CAPTION.match(
                unaccent(lines[j].text).lower()
            ) and (front or (not strong_numbered(lines[j]) and match_topic(lines[j].text) is None)):
                j += 1
            add("para", "\n".join(ln.text for ln in lines[i:j]))
            i = j
    return output


def formatted_markdown(blocks):
    parts = []
    for block in blocks:
        pages = ", ".join(map(str, block.loc.image_indices or []))
        label = f"Ảnh trang {pages} · {block.loc.anchor}"
        if block.kind == "heading":
            parts.append(f"{'#' * min(6, len(block.loc.section_path))} {block.text}\n\n*Nguồn: {label}*")
        elif block.kind == "table":
            parts.append(f"**{block.caption}**\n\n{block.text}\n\n*Nguồn: {label}*")
        else:
            parts.append(f"{block.text}\n\n*Nguồn: {label}*")
    return "\n\n".join(parts) + "\n"
