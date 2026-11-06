"""The MCQ bank in use: adaptive practice, mock-exam and topic sets, scoring, flags and reviewer
decisions."""

import json
import random
import sqlite3
from datetime import timedelta

from yhdp.blueprint import Blueprint, load_blueprint
from yhdp.ingest.tag import BLOOM
from yhdp.mcq import deck
from yhdp.mcq.allocate import allocate, pick_items
from yhdp.mcq.items import USABLE, full, public, target_chunk
from yhdp.mcq.mastery import mastery, need

MINUTES_PER_QUESTION = 1  # QĐ 51: 140 questions in 140 minutes per session
TOPIC_SET_MAX = 30
TOPIC_MARGIN = 0.08   # cosine; see create_topic_set
RESEEN_DAYS = 7      # practice doesn't repeat an item within a week; the deck handles misses
STRENGTH_FLOOR = 0.2  # strong vấn đề still come up, just less often


def _seen(con: sqlite3.Connection, username: str) -> dict[int, int]:
    return {r["item_id"]: r["n"] for r in con.execute(
        "SELECT item_id, count(*) AS n FROM mcq_attempts WHERE username = ? GROUP BY item_id",
        (username,))}


# --- practice -----------------------------------------------------------------------------

def next_practice(con: sqlite3.Connection, username: str, de_muc: int | None = None,
                  van_de: int | None = None, bp: Blueprint | None = None,
                  rnd: random.Random | None = None) -> dict | None:
    """A practice item weighted toward weak vấn đề and heavy đề mục: blueprint weight ×
    (floor + need), unseen items first, nothing repeated within a week, consecutive questions
    from different vấn đề when possible. Items whose concept is in the deck are kept back for
    its review."""
    bp, rnd = bp or load_blueprint(), rnd or random.Random()
    rows = con.execute(
        "SELECT * FROM mcq_items WHERE status IN (?, ?) AND (? IS NULL OR de_muc = ?) "
        "AND (? IS NULL OR van_de = ?)", (*USABLE, de_muc, de_muc, van_de, van_de)).fetchall()
    if not rows:
        return None
    last = {r["item_id"]: r["ts"] for r in con.execute(
        "SELECT item_id, max(ts) AS ts FROM mcq_attempts WHERE username = ? GROUP BY item_id",
        (username,))}
    prev = con.execute("SELECT i.van_de FROM mcq_attempts a JOIN mcq_items i ON i.id = a.item_id "
                       "WHERE a.username = ? ORDER BY a.id DESC LIMIT 1", (username,)).fetchone()
    in_deck = {r["chunk_id"] for r in con.execute(
        "SELECT chunk_id FROM revision_cards WHERE username = ? AND origin = 'mcq' AND step < ?",
        (username, deck.MASTERED))}
    weight = {d.id: sum(d.weight) / 2 for d in bp.de_muc}
    m = mastery(con, username)
    cutoff = deck.stamp(deck.now_utc() - timedelta(days=RESEEN_DAYS))
    pool, weights = [], []
    for r in rows:
        seen = last.get(r["id"])
        if seen and seen > cutoff:
            continue
        w = weight.get(r["de_muc"], 1) * (STRENGTH_FLOOR + need(m, r["van_de"]))
        w *= 0.3 if seen else 1.0
        w *= 0.3 if target_chunk(r)["chunk_id"] in in_deck else 1.0
        w *= 0.3 if prev and r["van_de"] == prev["van_de"] else 1.0
        pool.append(r)
        weights.append(w)
    row = rnd.choices(pool, weights)[0] if pool else min(rows, key=lambda r: last[r["id"]])
    vd = m.get(row["van_de"])
    focus = ("new" if vd is None else "weak" if vd["p"] < 0.6 else "keep")
    return {**public(row), "focus": {"kind": focus, "p": vd["p"] if vd else None,
                                     "n": vd["n"] if vd else 0}}


def answer(con: sqlite3.Connection, username: str, item_id: int, chosen: str | None,
           seconds: float | None = None, mode: str = "practice", set_id: int | None = None,
           confidence: str | None = None, card_id: int | None = None) -> dict:
    if confidence not in (None, "sure", "unsure", "guess"):
        raise ValueError(f"unknown confidence {confidence!r}")
    row = con.execute("SELECT * FROM mcq_items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        raise KeyError(item_id)
    correct = chosen == row["answer"]
    with con:
        con.execute("INSERT INTO mcq_attempts (username, item_id, set_id, chosen, correct, seconds, "
                    "mode, confidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (username, item_id, set_id, chosen, int(correct), seconds, mode, confidence))
        card = deck.on_attempt(con, username, row, correct, confidence, card_id)
    return {"correct": correct, "chosen": chosen, "confidence": confidence, "card": card,
            **full(con, row)}


def mastery_report(con: sqlite3.Connection, username: str, bp: Blueprint | None = None) -> dict:
    """Per-vấn đề mastery for the vấn đề the bank covers, weakest first, plus đề mục totals."""
    bp = bp or load_blueprint()
    m = mastery(con, username)
    names = {v.id: v for v in bp.van_de}
    bank_n = {r["van_de"]: r["n"] for r in con.execute(
        "SELECT van_de, count(*) AS n FROM mcq_items WHERE status IN (?, ?) GROUP BY van_de",
        USABLE)}
    van_de = sorted(({"id": v, "name": names[v].name, "de_muc": names[v].de_muc,
                      "items": n, "p": m[v]["p"] if v in m else None,
                      "answered": m[v]["n"] if v in m else 0,
                      "correct": m[v]["correct"] if v in m else 0}
                     for v, n in bank_n.items() if v in names),
                    key=lambda x: (x["p"] is None, x["p"] if x["p"] is not None else 0))
    de_muc = []
    for d in bp.de_muc:
        rows = [v for v in van_de if v["de_muc"] == d.id]
        de_muc.append({"id": d.id, "name": d.name, "items": sum(v["items"] for v in rows),
                       "answered": sum(v["answered"] for v in rows),
                       "correct": sum(v["correct"] for v in rows)})
    return {"van_de": van_de, "de_muc": de_muc, "due": deck.due_count(con, username)}


# --- mock exams ---------------------------------------------------------------------------

def create_set(con: sqlite3.Connection, username: str, size: int, timed: bool = True,
               bp: Blueprint | None = None, seed: int | None = None) -> dict:
    bp = bp or load_blueprint()
    rows = con.execute("SELECT * FROM mcq_items WHERE status IN (?, ?)", USABLE).fetchall()
    by_dm: dict[int, list[dict]] = {}
    seen = _seen(con, username)
    for r in rows:
        by_dm.setdefault(r["de_muc"], []).append({"id": r["id"], "mien": r["mien"],
                                                  "seen": seen.get(r["id"], 0)})
    previous = con.execute("SELECT count(*) FROM mcq_sets WHERE username = ?",
                           (username,)).fetchone()[0]
    quota, notes = allocate(size, {d.id: tuple(d.weight) for d in bp.de_muc},
                            {d: len(v) for d, v in by_dm.items()}, rotation=previous)
    rnd = random.Random(seed)
    mien_weights = {str(m.id): sum(m.weight) / 2 for m in bp.mien}
    counts: dict[str, int] = {}
    chosen = []
    for dm, k in sorted(quota.items(), key=lambda x: -x[1]):
        chosen += [c["id"] for c in pick_items(by_dm.get(dm, []), k, mien_weights, counts, rnd)]
    rnd.shuffle(chosen)
    if len(chosen) < size:
        notes.insert(0, f"Ngân hàng hiện chỉ đủ {len(chosen)}/{size} câu cho đề này.")
    minutes = len(chosen) * MINUTES_PER_QUESTION if timed else None
    with con:
        cur = con.execute("INSERT INTO mcq_sets (username, size, minutes, items, allocation, notes) "
                          "VALUES (?, ?, ?, ?, ?, ?)",
                          (username, size, minutes, json.dumps(chosen), json.dumps(quota),
                           json.dumps(notes, ensure_ascii=False)))
    return get_set(con, cur.lastrowid, username)


def create_topic_set(con: sqlite3.Connection, username: str, title: str,
                     chunks: dict[str, float], scoped: set[str] = frozenset(), size: int = 10,
                     rnd: random.Random | None = None) -> dict:
    """An untimed set on a topic. `chunks` maps candidate chunk ids to their similarity to the
    topic (Retriever.topic); items written from an in-scope chunk qualify, and other items only
    within a margin of the best one, since shared boilerplate ("tại trạm y tế xã") makes
    unrelated chunks look similar. Unseen items first, then in-scope, then most similar.
    LookupError when nothing matches."""
    size = max(1, min(size, TOPIC_SET_MAX))
    rnd = rnd or random.Random()
    seen = _seen(con, username)
    cand = [(chunks[cid], cid in scoped, r["id"])
            for r in con.execute("SELECT * FROM mcq_items WHERE status IN (?, ?)", USABLE)
            if (cid := target_chunk(r)["chunk_id"]) in chunks]
    if not cand:
        raise LookupError(title)
    best = max(sim for sim, _, _ in cand)
    # with a named disease in scope, outside items must be near-identical in similarity
    margin = TOPIC_MARGIN / 3 if any(inscope for _, inscope, _ in cand) else TOPIC_MARGIN
    keep = [(seen.get(i, 0), not inscope, -sim, i) for sim, inscope, i in cand
            if inscope or sim >= best - margin]
    chosen = [i for *_, i in sorted(keep)][:size]
    notes = []
    if len(chosen) < size:
        notes.append(f"Ngân hàng hiện chỉ có {len(chosen)}/{size} câu về chủ đề này.")
    rnd.shuffle(chosen)
    with con:
        cur = con.execute("INSERT INTO mcq_sets (username, size, minutes, items, allocation, notes, "
                          "title) VALUES (?, ?, NULL, ?, '{}', ?, ?)",
                          (username, size, json.dumps(chosen), json.dumps(notes, ensure_ascii=False),
                           title))
    return get_set(con, cur.lastrowid, username)


def get_set(con: sqlite3.Connection, set_id: int, username: str) -> dict:
    s = con.execute("SELECT * FROM mcq_sets WHERE id = ? AND username = ?",
                    (set_id, username)).fetchone()
    if s is None:
        raise KeyError(set_id)
    ids = json.loads(s["items"])
    rows = {r["id"]: r for r in con.execute(
        f"SELECT * FROM mcq_items WHERE id IN ({','.join('?' * len(ids))})", ids)} if ids else {}
    return {"id": s["id"], "title": s["title"], "size": s["size"], "minutes": s["minutes"],
            "started": s["started"], "submitted": s["submitted"], "notes": json.loads(s["notes"]),
            "allocation": json.loads(s["allocation"]),
            "items": [public(rows[i]) for i in ids if i in rows],
            "report": json.loads(s["report"]) if s["report"] else None}


def submit_set(con: sqlite3.Connection, set_id: int, username: str, answers: dict[str, str | None],
               seconds: float | None = None, bp: Blueprint | None = None) -> dict:
    bp = bp or load_blueprint()
    s = con.execute("SELECT * FROM mcq_sets WHERE id = ? AND username = ?",
                    (set_id, username)).fetchone()
    if s is None:
        raise KeyError(set_id)
    if s["submitted"]:
        return get_set(con, set_id, username)
    ids = json.loads(s["items"])
    results = []
    for i in ids:
        r = answer(con, username, i, answers.get(str(i)), None, "exam", set_id)
        results.append(r)
    report = score_report(results, seconds, bp)
    report["cards_added"] = len({r["card"]["id"] for r in results  # distinct concepts
                                 if r["card"] and r["card"]["event"] != "reviewed"})
    with con:
        con.execute("UPDATE mcq_sets SET submitted = datetime('now'), report = ? WHERE id = ?",
                    (json.dumps(report, ensure_ascii=False), set_id))
    return get_set(con, set_id, username)


def score_report(results: list[dict], seconds: float | None, bp: Blueprint) -> dict:
    def tally(key) -> list[dict]:
        groups: dict = {}
        for r in results:
            g = groups.setdefault(key(r), [0, 0])
            g[0] += r["correct"]
            g[1] += 1
        return [{"key": k, "correct": c, "total": t} for k, (c, t) in groups.items()]

    de_muc = {d.id: d.name for d in bp.de_muc}
    mien = {str(m.id): m.name for m in bp.mien}
    by_de_muc = sorted(tally(lambda r: r["de_muc"]), key=lambda g: g["key"])
    by_mien = sorted(tally(lambda r: r["mien"].split(".")[0]), key=lambda g: g["key"])
    by_bloom = sorted(tally(lambda r: r["bloom"]), key=lambda g: BLOOM.index(g["key"]))
    for g in by_de_muc:
        g["label"] = f"Đề mục {g['key']}: {de_muc[g['key']]}"
    for g in by_mien:
        g["label"] = f"Miền {g['key']}: {mien[g['key']]}"
    for g in by_bloom:
        g["label"] = g["key"]
    return {"correct": sum(r["correct"] for r in results), "total": len(results),
            "blank": sum(r["chosen"] is None for r in results), "seconds": seconds,
            "by_de_muc": by_de_muc, "by_mien": by_mien, "by_bloom": by_bloom,
            "items": results}


def list_sets(con: sqlite3.Connection, username: str) -> list[dict]:
    out = []
    for s in con.execute("SELECT * FROM mcq_sets WHERE username = ? ORDER BY id DESC LIMIT 30",
                         (username,)):
        rep = json.loads(s["report"]) if s["report"] else None
        out.append({"id": s["id"], "title": s["title"], "size": len(json.loads(s["items"])),
                    "started": s["started"],
                    "submitted": s["submitted"],
                    "score": f"{rep['correct']}/{rep['total']}" if rep else None})
    return out


# --- flags, review, stats -----------------------------------------------------------------

def flag(con: sqlite3.Connection, item_id: int, username: str, reason: str) -> None:
    with con:
        if con.execute("UPDATE mcq_items SET status = 'flagged', updated = datetime('now') "
                       "WHERE id = ? AND status != 'discarded'", (item_id,)).rowcount == 0:
            raise KeyError(item_id)
        con.execute("INSERT INTO mcq_flags (item_id, username, reason) VALUES (?, ?, ?)",
                    (item_id, username, reason))


def next_review(con: sqlite3.Connection) -> dict | None:
    """Flagged items first, then unreviewed ones."""
    row = con.execute("SELECT * FROM mcq_items WHERE status IN ('flagged', 'validated') "
                      "ORDER BY status = 'flagged' DESC, id LIMIT 1").fetchone()
    if row is None:
        return None
    flags = [dict(r) for r in con.execute(
        "SELECT username, reason, ts FROM mcq_flags WHERE item_id = ? ORDER BY ts", (row["id"],))]
    remaining = con.execute("SELECT count(*) FROM mcq_items WHERE status IN ('flagged', "
                            "'validated')").fetchone()[0]
    return {**full(con, row), "validation": json.loads(row["validation"]), "flags": flags,
            "remaining": remaining}


def review(con: sqlite3.Connection, item_id: int, action: str, reviewer: str, note: str = "") -> None:
    status = {"approve": "approved", "reject": "rejected"}.get(action)
    if status is None:
        raise ValueError(f"unknown action {action!r}")
    with con:
        if con.execute("UPDATE mcq_items SET status = ?, reviewer = ?, review_note = ?, "
                       "updated = datetime('now') WHERE id = ? AND status != 'discarded'",
                       (status, reviewer, note, item_id)).rowcount == 0:
            raise KeyError(item_id)


def stats(con: sqlite3.Connection) -> dict:
    by_status = {r["status"]: r["n"] for r in con.execute(
        "SELECT status, count(*) AS n FROM mcq_items GROUP BY status")}
    by_de_muc = {r["de_muc"]: r["n"] for r in con.execute(
        "SELECT de_muc, count(*) AS n FROM mcq_items WHERE status IN (?, ?) GROUP BY de_muc", USABLE)}
    by_van_de = {r["van_de"]: r["n"] for r in con.execute(
        "SELECT van_de, count(*) AS n FROM mcq_items WHERE status IN (?, ?) GROUP BY van_de", USABLE)}
    problems: dict[str, int] = {}
    for (v,) in con.execute("SELECT validation FROM mcq_items WHERE status = 'discarded'"):
        for p in json.loads(v).get("problems", []):
            key = p.split(":")[0]
            problems[key] = problems.get(key, 0) + 1
    return {"by_status": by_status, "by_de_muc": by_de_muc, "by_van_de": by_van_de,
            "discard_reasons": problems}
