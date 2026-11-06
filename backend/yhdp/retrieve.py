"""Hybrid retrieval: dense (bge-m3, numpy brute force) + BM25 (FTS5), fused with RRF.

A first cut of design §6: dictionary query expansion, but no reranker or graph expansion yet.
Questions that span many chapters ("lập bảng triệu chứng các bệnh") are answered from a fan-out:
the best chunks for one aspect in each chapter the question needs (`outline`, `fan_out`).
"""

import json
import re
import sqlite3
from dataclasses import dataclass, field

import numpy as np

from yhdp.dictionary import Dictionary, fold
from yhdp.ingest.model import Loc
from yhdp.llm import Ollama
from yhdp.settings import settings

RRF_K = 60
CANDIDATES = 30
FAN_OUT_SOURCES = 24  # the character budget usually binds first
FAN_OUT_PER_SECTION = 3
FAN_OUT_CHARS = 24_000  # about 9k tokens of sources: room for the prompt and a long table
WORD = re.compile(r"\w+", re.UNICODE)


@dataclass
class Hit:
    chunk_id: str
    doc_id: str
    kind: str
    text: str
    loc: Loc
    extra: dict
    score: float
    ranks: dict[str, int] = field(default_factory=dict)  # retriever → 1-based rank


def load_hits(con: sqlite3.Connection, chunk_ids: list[str]) -> list[Hit]:
    """Chunks as unscored hits, in the given order; unknown ids are skipped."""
    hits = []
    for cid in chunk_ids:
        r = con.execute("SELECT * FROM chunks WHERE chunk_id = ?", (cid,)).fetchone()
        if r is not None:
            hits.append(Hit(chunk_id=cid, doc_id=r["doc_id"], kind=r["kind"], text=r["text"],
                            loc=Loc.model_validate_json(r["loc"]), extra=json.loads(r["extra"]),
                            score=0.0))
    return hits


def rrf(rankings: dict[str, list[str]], k: int = RRF_K) -> list[tuple[str, float, dict[str, int]]]:
    """Reciprocal rank fusion of several ranked id lists, best first."""
    scores: dict[str, float] = {}
    ranks: dict[str, dict[str, int]] = {}
    for name, ids in rankings.items():
        for r, cid in enumerate(ids, start=1):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + r)
            ranks.setdefault(cid, {})[name] = r
    return [(cid, s, ranks[cid]) for cid, s in sorted(scores.items(), key=lambda x: -x[1])]


def fts_query(question: str, phrases: list[str] = ()) -> str:
    """OR of the question's words plus synonym phrases, each quoted so FTS5 syntax characters
    can't break it."""
    words = dict.fromkeys(w.lower() for w in WORD.findall(question) if len(w) > 1 or w.isdigit())
    terms = [f'"{w}"' for w in words]
    for p in phrases:
        if tokens := WORD.findall(p.lower()):
            terms.append('"' + " ".join(tokens) + '"')
    return " OR ".join(dict.fromkeys(terms))


def expansions(question: str, dictionary: Dictionary | None) -> list[str]:
    """Synonyms of the dictionary terms in the question that the question doesn't already use."""
    if dictionary is None:
        return []
    q = fold(question)
    return [f for t in dictionary.find(question) for f in t.forms() if fold(f) not in q]


class Retriever:
    def __init__(self, con: sqlite3.Connection, llm: Ollama, model: str | None = None,
                 dictionary: Dictionary | None = None):
        self.con, self.llm, self.dictionary = con, llm, dictionary
        self.model = model or settings.embed_model
        rows = con.execute("SELECT chunk_id, vec FROM chunk_vectors WHERE model = ? "
                           "ORDER BY chunk_id", (self.model,)).fetchall()
        if not rows:
            raise RuntimeError("no embeddings in the database; run `yhdp index` first")
        self.ids = [r["chunk_id"] for r in rows]
        self.matrix = np.stack([np.frombuffer(r["vec"], dtype=np.float32) for r in rows])

    def similarity(self, question: str) -> dict[str, float]:
        """Cosine similarity of every chunk to the question (with dictionary canonical terms
        appended, as for dense retrieval)."""
        canon = [t.canonical for t in self.dictionary.find(question)] if self.dictionary else []
        missing = [c for c in canon if fold(c) not in fold(question)]
        text = f"{question} ({'; '.join(missing)})" if missing else question
        q = self.llm.embed([text], model=self.model)[0]
        return dict(zip(self.ids, (self.matrix @ q).tolist(), strict=True))

    def dense(self, question: str, n: int = CANDIDATES) -> list[str]:
        sims = self.similarity(question)
        return sorted(sims, key=sims.get, reverse=True)[:n]

    def topic(self, topic: str, k: int = CANDIDATES) -> tuple[dict[str, float], set[str]]:
        """Chunks about a topic: (chunk_id → cosine similarity for the fused top-k plus every
        in-scope chunk, the in-scope ids). In scope = the document title or section path names
        a disease the topic mentions, so a broad topic ("sốt xuất huyết Dengue") covers its whole
        guideline, not just the chunks that happen to repeat the name."""
        sims = self.similarity(topic)
        fused = [cid for cid, _, _ in rrf({"dense": sorted(sims, key=sims.get, reverse=True)[:k],
                                           "bm25": self.bm25(topic, k)})[:k]]
        forms = [fold(f) for t in (self.dictionary.find(topic) if self.dictionary else [])
                 if t.type == "Bệnh" for f in t.forms()]
        scoped = set()
        if forms:  # whole words only: folded "tha" (THA) must not match "thay"
            name = re.compile(r"(?<!\w)(" + "|".join(map(re.escape, forms)) + r")(?!\w)")
            for r in self.con.execute("SELECT c.chunk_id, c.loc, d.title FROM chunks c "
                                      "JOIN documents d ON d.doc_id = c.doc_id"):
                where = fold(r["title"] + " " + " ".join(json.loads(r["loc"])["section_path"]))
                if name.search(where):
                    scoped.add(r["chunk_id"])
        return {c: sims[c] for c in [*fused, *scoped]}, scoped

    def bm25(self, question: str, n: int = CANDIDATES) -> list[str]:
        query = fts_query(question, expansions(question, self.dictionary))
        if not query:
            return []
        rows = self.con.execute("SELECT chunk_id FROM chunks_fts WHERE chunks_fts MATCH ? "
                                "ORDER BY bm25(chunks_fts) LIMIT ?", (query, n)).fetchall()
        return [r["chunk_id"] for r in rows]

    def outline(self) -> list[tuple[str, str, str]]:
        """Each document's top-level sections in reading order: (doc_id, title, heading)."""
        out: dict[tuple[str, str], str] = {}
        for r in self.con.execute("SELECT c.doc_id, d.title, c.loc FROM chunks c JOIN documents d "
                                  "ON d.doc_id = c.doc_id ORDER BY d.doc_id, c.seq"):
            path = json.loads(r["loc"])["section_path"]
            out.setdefault((r["doc_id"], path[0] if path else ""), r["title"])
        return [(doc, title, heading) for (doc, heading), title in out.items()]

    def fan_out(self, aspect: str, sections: list[tuple[str, str]],
                budget: int = FAN_OUT_SOURCES) -> list[Hit]:
        """The chunks of each (doc_id, heading) section most similar to `aspect`: the best of
        every section first, then second-best ones while the source budget and FAN_OUT_CHARS
        allow. A search over the whole corpus would return whichever chunks repeat the
        question's words (for "bệnh … triệu chứng", the list of abbreviations)."""
        sims = self.similarity(aspect)
        ranked: dict[tuple[str, str], list[sqlite3.Row]] = {s: [] for s in sections}
        for r in self.con.execute("SELECT chunk_id, doc_id, loc, length(text) AS n FROM chunks"):
            path = json.loads(r["loc"])["section_path"]
            key = (r["doc_id"], path[0] if path else "")
            if key in ranked:
                ranked[key].append(r)
        for rows in ranked.values():
            rows.sort(key=lambda r: sims.get(r["chunk_id"], 0.0), reverse=True)
        chosen, chars = [], 0
        for depth in range(FAN_OUT_PER_SECTION):
            for i, rows in enumerate(ranked.values()):
                if depth < len(rows) and len(chosen) < budget and (
                        depth == 0 or chars + rows[depth]["n"] <= FAN_OUT_CHARS):
                    chosen.append((i, depth, rows[depth]["chunk_id"]))
                    chars += rows[depth]["n"]
        hits = load_hits(self.con, [cid for *_, cid in sorted(chosen)])  # grouped by section
        for h in hits:
            h.score = sims.get(h.chunk_id, 0.0)
        return hits

    def search(self, question: str, k: int = 6) -> list[Hit]:
        fused = rrf({"dense": self.dense(question), "bm25": self.bm25(question)})[:k]
        hits = load_hits(self.con, [cid for cid, _, _ in fused])
        for h, (_, score, ranks) in zip(hits, fused, strict=True):
            h.score, h.ranks = score, ranks
        return hits
