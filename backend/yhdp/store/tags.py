"""Reading and writing chunk tags. A human tag for the chunk's current content wins over the
auto tag; tags for an older content_hash are ignored."""

import json
import sqlite3


def effective_tags(con: sqlite3.Connection) -> dict[str, dict]:
    """chunk_id → {"doc_id", "kind", "record", "source"} for every chunk with a current tag."""
    out: dict[str, dict] = {}
    rows = con.execute(
        "SELECT c.chunk_id, c.doc_id, c.kind, t.tags, t.source FROM chunks c JOIN chunk_tags t "
        "ON t.chunk_id = c.chunk_id AND t.content_hash = c.content_hash "
        "ORDER BY c.doc_id, c.seq, t.source = 'human'")  # human last, so it overwrites auto
    for r in rows:
        out[r["chunk_id"]] = {"doc_id": r["doc_id"], "kind": r["kind"],
                              "record": json.loads(r["tags"]), "source": r["source"]}
    return out


def tag_pairs(con: sqlite3.Connection) -> list[tuple[str, dict, dict, str]]:
    """(chunk_id, auto record, human record, why it was reviewed) for chunks with both tags on
    the current content — the material for the tagging eval (T18)."""
    rows = con.execute(
        "SELECT c.chunk_id, a.tags AS auto, h.tags AS human, "
        "COALESCE(json_extract(r.payload, '$.reasons'), '[]') AS reasons "
        "FROM chunks c "
        "JOIN chunk_tags a ON a.chunk_id = c.chunk_id AND a.content_hash = c.content_hash "
        "AND a.source = 'auto' "
        "JOIN chunk_tags h ON h.chunk_id = c.chunk_id AND h.content_hash = c.content_hash "
        "AND h.source = 'human' "
        "LEFT JOIN review_items r ON r.kind = 'tag' AND r.ref = c.chunk_id "
        "ORDER BY c.doc_id, c.seq").fetchall()
    out = []
    for r in rows:
        reasons = json.loads(r["reasons"])
        why = "audit" if reasons == ["audit_sample"] else ("queued" if reasons else "unqueued")
        out.append((r["chunk_id"], json.loads(r["auto"]), json.loads(r["human"]), why))
    return out


def save_human_tag(con: sqlite3.Connection, chunk_id: str, content_hash: str, record: dict,
                   reviewer: str) -> None:
    record = {**record, "review_status": "human", "reviewer": reviewer}
    con.execute(
        "INSERT INTO chunk_tags (chunk_id, content_hash, tags, source, reviewer) "
        "VALUES (?, ?, ?, 'human', ?) ON CONFLICT (chunk_id, content_hash, source) DO UPDATE SET "
        "tags = excluded.tags, reviewer = excluded.reviewer, ts = datetime('now')",
        (chunk_id, content_hash, json.dumps(record, ensure_ascii=False), reviewer))
