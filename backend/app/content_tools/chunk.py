"""Pure chunking port from YHDP c661586. Token counter must be supplied by the caller.
No tokenizer downloads, model calls, SQL or automatic content publication.

Rules: never cross a section; pack para/list blocks greedily up to TARGET_MAX tokens and fold
a short tail into the chunk before it; tables, figures, boxes, formulas and flattened tables
stand alone; oversized tables are split by row groups with the header repeated. Cover pages,
front matter and a source's skip_sections are left out.
"""

import hashlib
import re
import unicodedata
from collections.abc import Callable
from itertools import groupby, pairwise
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from .model import Block, Loc, ParsedDoc
from dataclasses import dataclass

FRONT_MATTER = "Quyết định ban hành"

@dataclass(frozen=True)
class Source:
    title: str
    skip_sections: tuple[str, ...] = ()

TARGET_MAX = 700
TAIL_MIN = 120
TABLE_MAX = 1500
STANDALONE = {"table", "figure", "box", "formula"}
XREF_ONLY = re.compile(r"^\(?\s*[Xx]em\b[^\n]{0,200}\)?\.?$")  # "(Xem kế hoạch chăm sóc …)": no content

ChunkKind = Literal["text", "table", "figure", "box", "formula"]


class Chunk(BaseModel):
    schema_version: Literal["yhdp.chunk.v1"] = "yhdp.chunk.v1"
    chunk_id: str  # f"{doc_id}#{anchor}#c{n:02d}"
    doc_id: str
    kind: ChunkKind
    text: str  # markdown, without the section heading
    loc: Loc  # loc.anchor is the parent section, for P1 parent expansion
    tokens: int
    content_hash: str
    figure_path: str | None = None
    caption: str | None = None
    needs_review: list[str] = []
    refs: list[str] = []



def content_hash(text: str) -> str:
    norm = re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()
    return hashlib.sha1(norm.encode()).hexdigest()


def embed_text(chunk: Chunk, source: Source) -> str:
    """What gets embedded and indexed: document title and section path give a short chunk
    ("Lâm sàng: sốt cao …") the context it lacks on its own."""
    return f"{source.title}\n{' › '.join(chunk.loc.section_path)}\n\n{chunk.text}"


def split_table(text: str, count: Callable[[str], int], max_tokens: int = TABLE_MAX) -> list[str]:
    lines = text.splitlines()
    header, rows = lines[:2], lines[2:]
    budget = max_tokens - count("\n".join(header))
    groups: list[list[str]] = []
    used = 0
    for row in rows:
        t = count(row)
        if groups and used + t <= budget:
            groups[-1].append(row)
            used += t
        else:
            groups.append([row])
            used = t
    return ["\n".join(header + g) for g in groups] or [text]


def _merge_locs(blocks: list[Block]) -> Loc:
    pages = list(dict.fromkeys(p for b in blocks for p in b.loc.printed_pages or []))
    images = list(dict.fromkeys(i for b in blocks for i in b.loc.image_indices or []))
    first = blocks[0].loc
    return Loc(section_path=first.section_path, anchor=first.anchor,
               printed_pages=pages or None, image_indices=images or None)


def _section_pieces(blocks: list[Block], count) -> list[tuple[ChunkKind, str, list[Block]]]:
    pieces: list[tuple[ChunkKind, str, list[Block]]] = []
    buf: list[Block] = []
    used = 0

    def flush():
        nonlocal buf, used
        if buf:
            pieces.append(("text", "\n\n".join(b.text for b in buf), buf))
        buf, used = [], 0

    for blk in blocks:
        if blk.kind == "heading":
            continue
        if blk.kind in STANDALONE or "table_flattened" in blk.needs_review:
            flush()
            kind: ChunkKind = "table" if blk.kind == "para" else blk.kind
            text = blk.text + (f"\n\n{blk.caption_desc}" if blk.caption_desc else "")
            parts = split_table(blk.text, count) if blk.kind == "table" else [text]
            pieces += [(kind, p, [blk]) for p in parts]
            continue
        t = count(blk.text)
        if buf and used + t > TARGET_MAX:
            flush()
        buf.append(blk)
        used += t
    flush()

    merged: list[tuple[ChunkKind, str, list[Block]]] = []
    for kind, text, blks in pieces:
        if kind == "text" and merged and merged[-1][0] == "text" and count(text) < TAIL_MIN:
            _, prev_text, prev_blks = merged[-1]
            merged[-1] = ("text", f"{prev_text}\n\n{text}", prev_blks + blks)
        else:
            merged.append((kind, text, blks))
    return merged


def chunk_doc(doc: ParsedDoc, source: Source,
              count: Callable[[str], int]) -> list[Chunk]:
    skip = [re.compile(p) for p in source.skip_sections]
    chunks: list[Chunk] = []
    for anchor, group in groupby(doc.blocks, key=lambda b: b.loc.anchor):
        blocks = list(group)
        path = blocks[0].loc.section_path
        if not path or path[0] == FRONT_MATTER or any(r.search(path[0]) for r in skip):
            continue
        n = sum(1 for c in chunks if c.loc.anchor == anchor)
        for kind, text, blks in _section_pieces(blocks, count):
            if kind == "text" and XREF_ONLY.match(text.strip()):
                continue
            n += 1
            first = blks[0]
            chunks.append(Chunk(
                chunk_id=f"{doc.doc_id}#{anchor}#c{n:02d}", doc_id=doc.doc_id, kind=kind,
                text=text, loc=_merge_locs(blks), tokens=count(text),
                content_hash=content_hash(text),
                figure_path=first.figure_path if kind == "figure" else None,
                caption=first.caption if kind in STANDALONE else None,
                needs_review=sorted({r for b in blks for r in b.needs_review}),
                refs=sorted({r for b in blks for r in b.refs})))
    return chunks


def save_chunks(chunks: list[Chunk], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(c.model_dump_json() + "\n" for c in chunks), encoding="utf-8")


def load_chunks(path: Path) -> list[Chunk]:
    return [Chunk.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines() if line]


def stats(chunks: list[Chunk]) -> str:
    kinds: dict[str, int] = {}
    for c in chunks:
        kinds[c.kind] = kinds.get(c.kind, 0) + 1
    bins = [0, 50, 120, 300, 700, 1600, 10**9]
    hist = [sum(lo <= c.tokens < hi for c in chunks) for lo, hi in pairwise(bins)]
    labels = ["<50", "50–119", "120–299", "300–699", "700–1599", "≥1600"]
    return (f"{len(chunks)} chunks; " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items()))
            + "\n  tokens: " + ", ".join(f"{lab} {h}" for lab, h in zip(labels, hist))
            + f"; max {max((c.tokens for c in chunks), default=0)}")
