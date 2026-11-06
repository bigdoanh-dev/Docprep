"""Load chunks into SQLite (idempotent upsert) and embed the ones whose search text changed."""

import hashlib
import json
import sqlite3
from dataclasses import dataclass

import numpy as np

from yhdp.ingest.chunk import Chunk, embed_text
from yhdp.llm import Ollama
from yhdp.settings import settings
from yhdp.sources import Source


@dataclass
class LoadStats:
    added: int = 0
    changed: int = 0
    unchanged: int = 0
    removed: int = 0

    def __str__(self) -> str:
        return (f"{self.added} added, {self.changed} changed, {self.unchanged} unchanged, "
                f"{self.removed} removed")


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()


def load_doc(con: sqlite3.Connection, source: Source, chunks: list[Chunk]) -> LoadStats:
    stats = LoadStats()
    with con:
        con.execute(
            "INSERT INTO documents (doc_id, title, issuer, year, kind, citation) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (doc_id) DO UPDATE SET title = excluded.title, "
            "issuer = excluded.issuer, year = excluded.year, kind = excluded.kind, "
            "citation = excluded.citation",
            (source.doc_id, source.title, source.issuer, source.year, source.kind, source.citation))
        old = {r["chunk_id"]: (r["content_hash"], r["search_text"]) for r in con.execute(
            "SELECT chunk_id, content_hash, search_text FROM chunks WHERE doc_id = ?",
            (source.doc_id,))}
        gone = old.keys() - {c.chunk_id for c in chunks}
        con.executemany("DELETE FROM chunks WHERE chunk_id = ?", [(g,) for g in gone])
        con.executemany("DELETE FROM review_items WHERE kind = 'tag' AND ref = ? AND status = 'open'",
                        [(g,) for g in gone])
        stats.removed = len(gone)
        for seq, c in enumerate(chunks):
            search = embed_text(c, source)
            prev = old.get(c.chunk_id)
            if prev is None:
                stats.added += 1
            elif prev == (c.content_hash, search):
                stats.unchanged += 1
            else:
                stats.changed += 1
            extra = c.model_dump(include={"figure_path", "caption", "needs_review", "refs"})
            con.execute(
                "INSERT INTO chunks (chunk_id, doc_id, seq, content_hash, kind, text, search_text,"
                " loc, parent_anchor, tokens, extra) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (chunk_id) DO UPDATE SET seq = excluded.seq, content_hash = "
                "excluded.content_hash, kind = excluded.kind, text = excluded.text, search_text = "
                "excluded.search_text, loc = excluded.loc, parent_anchor = excluded.parent_anchor,"
                " tokens = excluded.tokens, extra = excluded.extra",
                (c.chunk_id, c.doc_id, seq, c.content_hash, c.kind, c.text, search,
                 c.loc.model_dump_json(), c.loc.anchor, c.tokens,
                 json.dumps(extra, ensure_ascii=False)))
        con.execute("DELETE FROM chunks_fts WHERE chunk_id IN "
                    "(SELECT chunk_id FROM chunks WHERE doc_id = ?)", (source.doc_id,))
        con.executemany("DELETE FROM chunks_fts WHERE chunk_id = ?", [(g,) for g in gone])
        con.execute("INSERT INTO chunks_fts (chunk_id, body) "
                    "SELECT chunk_id, search_text FROM chunks WHERE doc_id = ?", (source.doc_id,))
    return stats


def embed_missing(con: sqlite3.Connection, llm: Ollama, model: str | None = None) -> int:
    """Embed every chunk with no vector for `model`, or whose search text changed."""
    model = model or settings.embed_model
    rows = con.execute(
        "SELECT c.chunk_id, c.search_text, v.search_hash FROM chunks c "
        "LEFT JOIN chunk_vectors v ON v.chunk_id = c.chunk_id AND v.model = ? ORDER BY c.chunk_id",
        (model,)).fetchall()
    todo = [r for r in rows if r["search_hash"] != _sha1(r["search_text"])]
    if not todo:
        return 0
    vecs = llm.embed([r["search_text"] for r in todo], model=model)
    with con:
        con.executemany(
            "INSERT INTO chunk_vectors (chunk_id, model, search_hash, vec) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (chunk_id, model) DO UPDATE SET search_hash = excluded.search_hash, "
            "vec = excluded.vec",
            [(r["chunk_id"], model, _sha1(r["search_text"]), v.astype(np.float32).tobytes())
             for r, v in zip(todo, vecs, strict=True)])
    return len(todo)
