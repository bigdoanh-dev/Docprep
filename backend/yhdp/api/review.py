"""Review queue logic behind the reviewer screens: fetch the next item, apply a decision."""

import json
import sqlite3

from pydantic import BaseModel, Field

from yhdp.dictionary import Term, TermType, add_alias, add_term, fold, load_dictionary
from yhdp.ingest.model import Loc
from yhdp.ingest.tag import BLOOM, CONTENT_TYPES, POPULATIONS, to_record
from yhdp.store.tags import save_human_tag


def cite(doc: sqlite3.Row, loc: Loc) -> str:
    head = f"{doc['issuer']} ({doc['year']})" if doc["issuer"] else doc["title"]
    if doc["citation"] == "page" and loc.printed_pages:
        return f"{head}, tr. {'–'.join(dict.fromkeys([loc.printed_pages[0], loc.printed_pages[-1]]))}"
    return f"{head} › " + " › ".join(loc.section_path)


def stats(con: sqlite3.Connection) -> dict:
    counts = {f"{r['kind']}:{r['status']}": r["n"] for r in con.execute(
        "SELECT kind, status, count(*) AS n FROM review_items GROUP BY kind, status")}
    by_reviewer = {r["reviewer"]: r["n"] for r in con.execute(
        "SELECT reviewer, count(*) AS n FROM review_items WHERE status = 'done' "
        "AND reviewer IS NOT NULL GROUP BY reviewer")}
    counts["mcq:open"] = con.execute("SELECT count(*) FROM mcq_items WHERE status IN "
                                     "('flagged', 'validated')").fetchone()[0]
    return {"counts": counts, "by_reviewer": by_reviewer,
            "human_tags": con.execute("SELECT count(*) FROM chunk_tags WHERE source = 'human'")
            .fetchone()[0]}


# --- tags ---------------------------------------------------------------------------------

def next_tag_item(con: sqlite3.Connection, doc_id: str | None = None) -> dict | None:
    """Oldest open tag item in reading order whose chunk still has the content it was tagged on."""
    rows = con.execute(
        "SELECT r.id, r.payload, c.*, t.tags FROM review_items r "
        "JOIN chunks c ON c.chunk_id = r.ref "
        "JOIN chunk_tags t ON t.chunk_id = c.chunk_id AND t.content_hash = c.content_hash "
        "AND t.source = 'auto' "
        "WHERE r.kind = 'tag' AND r.status = 'open' AND (? IS NULL OR c.doc_id = ?) "
        "ORDER BY c.doc_id, c.seq LIMIT 1", (doc_id, doc_id)).fetchone()
    if rows is None:
        return None
    doc = con.execute("SELECT * FROM documents WHERE doc_id = ?", (rows["doc_id"],)).fetchone()
    loc = Loc.model_validate_json(rows["loc"])
    payload = json.loads(rows["payload"])
    extra = json.loads(rows["extra"])
    remaining = con.execute(
        "SELECT count(*) FROM review_items r JOIN chunks c ON c.chunk_id = r.ref "
        "WHERE r.kind = 'tag' AND r.status = 'open' AND (? IS NULL OR c.doc_id = ?)",
        (doc_id, doc_id)).fetchone()[0]
    return {
        "id": rows["id"], "kind": "tag", "remaining": remaining,
        "chunk": {"chunk_id": rows["chunk_id"], "doc_id": rows["doc_id"], "kind": rows["kind"],
                  "text": rows["text"], "section_path": loc.section_path,
                  "citation": cite(doc, loc), "figure_path": extra.get("figure_path"),
                  "needs_review": extra.get("needs_review", [])},
        "auto": json.loads(rows["tags"]),
        "runs": payload.get("runs"), "reasons": payload.get("reasons", []),
        "old_human": payload.get("old_human"),
    }


class TagEdit(BaseModel):
    van_de_chinh: int
    van_de_phu: list[int] = Field(default_factory=list, max_length=2)
    mien: list[str] = Field(min_length=1, max_length=2)
    bloom: str
    content_type: str
    population: list[str] = Field(default_factory=list)
    note: str = ""


def _output_from_edit(edit: TagEdit, ly_do: str) -> dict:
    if edit.bloom not in BLOOM or edit.content_type not in CONTENT_TYPES or \
            not set(edit.population) <= set(POPULATIONS):
        raise ValueError("unknown Bloom level, content type or population")
    secondary = [v for v in dict.fromkeys(edit.van_de_phu) if v != edit.van_de_chinh]
    return {"ly_do": ly_do,
            "van_de": [{"id": edit.van_de_chinh, "primary": True, "conf": 1.0},
                       *({"id": v, "primary": False, "conf": 1.0} for v in secondary)],
            "mien": [{"id": m, "conf": 1.0} for m in dict.fromkeys(edit.mien)],
            "bloom_ceiling": {"level": edit.bloom, "conf": 1.0},
            "content_type": edit.content_type, "population": edit.population}


def decide_tag(con: sqlite3.Connection, item_id: int, action: str, reviewer: str,
               edit: TagEdit | None = None) -> None:
    item = con.execute("SELECT * FROM review_items WHERE id = ? AND kind = 'tag'",
                       (item_id,)).fetchone()
    if item is None:
        raise KeyError(item_id)
    chunk = con.execute("SELECT * FROM chunks WHERE chunk_id = ?", (item["ref"],)).fetchone()
    with con:
        if action in ("accept", "save"):
            auto = con.execute("SELECT tags FROM chunk_tags WHERE chunk_id = ? AND content_hash = ? "
                               "AND source = 'auto'", (chunk["chunk_id"], chunk["content_hash"])
                               ).fetchone()
            record = json.loads(auto["tags"])
            if action == "save":
                if edit is None:
                    raise ValueError("save needs the edited tags")
                doc = con.execute("SELECT * FROM documents WHERE doc_id = ?",
                                  (chunk["doc_id"],)).fetchone()
                record = to_record(dict(chunk), doc, _output_from_edit(edit, record.get("ly_do", "")),
                                   "human")
                record["note"] = edit.note
            save_human_tag(con, chunk["chunk_id"], chunk["content_hash"], record, reviewer)
            status = "done"
        elif action == "skip":
            status = "skipped"
        else:
            raise ValueError(f"unknown action {action!r}")
        con.execute("UPDATE review_items SET status = ?, reviewer = ?, ts = datetime('now') "
                    "WHERE id = ?", (status, reviewer, item_id))


# --- dictionary ---------------------------------------------------------------------------

def next_dictionary_item(con: sqlite3.Connection) -> dict | None:
    row = con.execute("SELECT * FROM review_items WHERE kind = 'dictionary' AND status = 'open' "
                      "ORDER BY ref LIMIT 1").fetchone()
    if row is None:
        return None
    s = json.loads(row["payload"])
    dic = load_dictionary()
    known = dic.by_key.get(fold(s["alias"])) or dic.by_key.get(fold(s["canonical"]))
    remaining = con.execute("SELECT count(*) FROM review_items WHERE kind = 'dictionary' "
                            "AND status = 'open'").fetchone()[0]
    return {"id": row["id"], "kind": "dictionary", "remaining": remaining, "suggestion": s,
            "existing": known.model_dump() if known else None}


class DictionaryDecision(BaseModel):
    action: str  # new_term | add_alias | reject | skip
    canonical: str | None = None
    aliases: list[str] = Field(default_factory=list)
    type: TermType | None = None
    en: str | None = None


def decide_dictionary(con: sqlite3.Connection, item_id: int, d: DictionaryDecision,
                      reviewer: str) -> None:
    if con.execute("SELECT 1 FROM review_items WHERE id = ? AND kind = 'dictionary'",
                   (item_id,)).fetchone() is None:
        raise KeyError(item_id)
    if d.action == "new_term":
        if not d.canonical or d.type is None:
            raise ValueError("a new term needs a canonical form and a type")
        add_term(Term(canonical=d.canonical, aliases=d.aliases, type=d.type, en=d.en))
    elif d.action == "add_alias":
        if not d.canonical or len(d.aliases) != 1:
            raise ValueError("add_alias needs the existing canonical and exactly one alias")
        add_alias(d.canonical, d.aliases[0])
    elif d.action not in ("reject", "skip"):
        raise ValueError(f"unknown action {d.action!r}")
    status = "skipped" if d.action == "skip" else "done"
    with con:
        con.execute("UPDATE review_items SET status = ?, reviewer = ?, ts = datetime('now'), "
                    "payload = json_set(payload, '$.decision', json(?)) WHERE id = ?",
                    (status, reviewer, d.model_dump_json(), item_id))
