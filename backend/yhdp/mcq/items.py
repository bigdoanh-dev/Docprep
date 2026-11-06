"""How MCQ items and their sources are shown: before answering (no key) and after."""

import json
import sqlite3

from yhdp.ingest.model import Loc

USABLE = ("validated", "approved")  # validated = passed automatic checks, not yet reviewed


def public(row: sqlite3.Row) -> dict:
    """An item as shown before answering: no key, no explanations."""
    return {"id": row["id"], "stem": row["stem"], "lead_in": row["lead_in"],
            "options": json.loads(row["options"]), "van_de": row["van_de"],
            "de_muc": row["de_muc"], "mien": row["mien"], "bloom": row["bloom"],
            "status": row["status"]}


def source_refs(con: sqlite3.Connection, refs: list[dict]) -> list[dict]:
    """[{chunk_id, content_hash}] → numbered sources with citation and text; `stale` when the
    chunk changed after the item or card was written."""
    docs = {r["doc_id"]: r for r in con.execute("SELECT * FROM documents")}
    out = []
    for i, s in enumerate(refs, start=1):
        c = con.execute("SELECT * FROM chunks WHERE chunk_id = ?", (s["chunk_id"],)).fetchone()
        if c is None:
            out.append({"n": i, "citation": "(đoạn nguồn đã bị xóa)", "text": "", "stale": True})
            continue
        d, loc = docs[c["doc_id"]], Loc.model_validate_json(c["loc"])
        head = f"{d['issuer']} ({d['year']})" if d["issuer"] else d["title"]
        out.append({"n": i, "chunk_id": c["chunk_id"], "doc_id": c["doc_id"], "kind": c["kind"],
                    "citation": f"{head} › " + " › ".join(loc.section_path), "text": c["text"],
                    "stale": c["content_hash"] != s["content_hash"]})
    return out


def sources(con: sqlite3.Connection, row: sqlite3.Row) -> list[dict]:
    return source_refs(con, json.loads(row["sources"]))


def full(con: sqlite3.Connection, row: sqlite3.Row) -> dict:
    return {**public(row), "answer": row["answer"],
            "explanations": json.loads(row["explanations"]), "sources": sources(con, row)}


def target_chunk(row: sqlite3.Row) -> dict:
    """The chunk the item was written from (sources[0]); the rest are context."""
    return json.loads(row["sources"])[0]
