"""The spaced-review deck (adaptive practice, phase 1).

A card schedules a concept, not a question. A missed MCQ (or a lucky guess) adds a card for
the item's source chunk; when it comes due it is reviewed with a *different* item from that
chunk if one exists, otherwise as open recall (the vignette without options), because
re-showing the same 4 options mostly tests memory of the letter. Chat cards are front/back notes.

Schedule: 1, 3, 7, 21 days, then mastered. A miss resets to 1 day; a confident miss is
relearned after 10 minutes. Correct-but-unsure keeps the interval; only a sure correct advances.
"""

import json
import random
import re
import sqlite3
from datetime import UTC, datetime, timedelta

from yhdp.mcq.items import USABLE, full, public, source_refs, target_chunk

INTERVALS_DAYS = (1, 3, 7, 21)
RELEARN = timedelta(minutes=10)
MASTERED = len(INTERVALS_DAYS)
RATINGS = ("again", "hard", "good")
CITE = re.compile(r"\[S(\d+)\]")


def now_utc() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def stamp(dt: datetime) -> str:
    """The format of SQLite's datetime('now'), so stored times compare as strings."""
    return dt.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


def interval(step: int) -> timedelta:
    return RELEARN if step < 0 else timedelta(days=INTERVALS_DAYS[step])


def rating_for(correct: bool, confidence: str | None) -> str:
    if not correct:
        return "again"
    return "hard" if confidence in ("unsure", "guess") else "good"


def schedule(step: int, rating: str, relearn: bool, now: datetime) -> tuple[int, str | None]:
    """(new step, due) after a review."""
    if rating == "again":
        step = -1 if relearn else 0
    elif rating == "good":
        step += 1
    if step >= MASTERED:
        return MASTERED, None
    return step, stamp(now + interval(step))


def _when(step: int) -> str:
    return "10 phút" if step < 0 else f"{INTERVALS_DAYS[step]} ngày"


def _summary(card: sqlite3.Row, event: str) -> dict:
    step = card["step"]
    if step >= MASTERED:
        text = "Thẻ ôn tập: đã thuộc, ngừng nhắc lại."
    elif event == "added":
        text = f"Đã thêm vào bộ thẻ ôn tập, ôn lại sau {_when(step)}."
    elif event == "reset":
        text = f"Thẻ ôn tập của nội dung này được đặt lại, ôn lại sau {_when(step)}."
    else:
        text = f"Thẻ ôn tập: lần ôn tới sau {_when(step)}."
    return {"id": card["id"], "event": event, "step": step, "due": card["due"], "text": text}


def _card(con: sqlite3.Connection, card_id: int) -> sqlite3.Row:
    return con.execute("SELECT * FROM revision_cards WHERE id = ?", (card_id,)).fetchone()


def _review(con: sqlite3.Connection, card: sqlite3.Row, rating: str, relearn: bool,
            item_id: int | None, now: datetime) -> sqlite3.Row:
    step, due = schedule(card["step"], rating, relearn, now)
    con.execute("UPDATE revision_cards SET step = ?, due = ?, reviews = reviews + 1, "
                "lapses = lapses + ?, last_review = ? WHERE id = ?",
                (step, due, int(rating == "again"), stamp(now), card["id"]))
    con.execute("INSERT INTO card_reviews (card_id, rating, item_id, ts) VALUES (?, ?, ?, ?)",
                (card["id"], rating, item_id, stamp(now)))
    return _card(con, card["id"])


def on_attempt(con: sqlite3.Connection, username: str, item: sqlite3.Row, correct: bool,
               confidence: str | None, card_id: int | None = None,
               now: datetime | None = None) -> dict | None:
    """Update the deck after an MCQ answer; the caller commits. Returns what happened, for
    the learner, or None when the deck is unchanged."""
    now = now or now_utc()
    rating = rating_for(correct, confidence)
    relearn = not correct and confidence == "sure"
    ref = target_chunk(item)
    card = None
    if card_id is not None:
        card = con.execute("SELECT * FROM revision_cards WHERE id = ? AND username = ?",
                           (card_id, username)).fetchone()
    if card is None:
        card = con.execute("SELECT * FROM revision_cards WHERE username = ? AND origin = 'mcq' "
                           "AND chunk_id = ?", (username, ref["chunk_id"])).fetchone()
    if card is not None and card["step"] < MASTERED and (
            card_id == card["id"] or (card["due"] and card["due"] <= stamp(now))):
        return _summary(_review(con, card, rating, relearn, item["id"], now), "reviewed")
    if rating == "good" or (rating == "hard" and confidence != "guess"):
        return None  # a guess that happened to be right doesn't count as knowing it
    step, due = schedule(0, "again", relearn, now)
    if card is not None:
        con.execute("UPDATE revision_cards SET step = ?, due = ?, lapses = lapses + ?, "
                    "item_id = ? WHERE id = ?",
                    (step, due, int(rating == "again"), item["id"], card["id"]))
        return _summary(_card(con, card["id"]), "reset")
    cur = con.execute("INSERT INTO revision_cards (username, origin, chunk_id, item_id, sources, "
                      "step, due, created) VALUES (?, 'mcq', ?, ?, ?, ?, ?, ?)",
                      (username, ref["chunk_id"], item["id"], json.dumps([ref]), step, due,
                       stamp(now)))
    return _summary(_card(con, cur.lastrowid), "added")


def add_chat_card(con: sqlite3.Connection, username: str, front: str, back: str,
                  refs: list[dict], now: datetime | None = None) -> dict:
    """A note card from chat. `back` cites [S#] into `refs`; only the cited sources are kept
    and renumbered from 1."""
    cited = sorted({int(n) for n in CITE.findall(back) if 1 <= int(n) <= len(refs)})
    if not cited:
        raise ValueError("mặt sau của thẻ phải trích dẫn ít nhất một nguồn [S#]")
    renumber = {old: new for new, old in enumerate(cited, start=1)}
    back = CITE.sub(lambda m: f"[S{renumber[int(m[1])]}]" if int(m[1]) in renumber else "", back)
    now = now or now_utc()
    step, due = schedule(0, "again", False, now)
    with con:
        cur = con.execute("INSERT INTO revision_cards (username, origin, front, back, sources, "
                          "step, due, created) VALUES (?, 'chat', ?, ?, ?, ?, ?, ?)",
                          (username, front.strip(), back.strip(),
                           json.dumps([refs[n - 1] for n in cited]), step, due, stamp(now)))
    return {**_summary(_card(con, cur.lastrowid), "added"), "front": front.strip()}


def _title(con: sqlite3.Connection, card: sqlite3.Row) -> str:
    if card["origin"] == "chat":
        return card["front"]
    src = source_refs(con, json.loads(card["sources"]))
    return src[0]["citation"] if src else "(đoạn nguồn đã bị xóa)"


def due_count(con: sqlite3.Connection, username: str, now: datetime | None = None) -> int:
    return con.execute("SELECT count(*) FROM revision_cards WHERE username = ? AND due <= ?",
                       (username, stamp(now or now_utc()))).fetchone()[0]


def next_card(con: sqlite3.Connection, username: str, now: datetime | None = None,
              rnd: random.Random | None = None) -> dict | None:
    """The most urgent due card (relearning first), as an MCQ, open recall or flashcard."""
    now, rnd = now or now_utc(), rnd or random.Random()
    card = con.execute("SELECT * FROM revision_cards WHERE username = ? AND due <= ? "
                       "ORDER BY step >= 0, due LIMIT 1", (username, stamp(now))).fetchone()
    if card is None:
        return None
    view = {"id": card["id"], "origin": card["origin"], "step": card["step"],
            "lapses": card["lapses"], "reviews": card["reviews"], "title": _title(con, card)}
    out = {"card": view, "due": due_count(con, username, now)}
    if card["origin"] == "chat":
        return {**out, "mode": "flash", "front": card["front"], "back": card["back"],
                "sources": source_refs(con, json.loads(card["sources"]))}
    siblings = con.execute(
        "SELECT * FROM mcq_items WHERE status IN (?, ?) AND "
        "json_extract(sources, '$[0].chunk_id') = ?", (*USABLE, card["chunk_id"])).fetchall()
    last = {r["item_id"]: r["ts"] for r in con.execute(
        "SELECT item_id, max(ts) AS ts FROM mcq_attempts WHERE username = ? GROUP BY item_id",
        (username,))}
    if unseen := [s for s in siblings if s["id"] not in last]:
        return {**out, "mode": "mcq", "item": public(rnd.choice(unseen))}
    if siblings:
        row = min(siblings, key=lambda s: last[s["id"]])
        item = full(con, row)
        return {**out, "mode": "recall", "item_id": row["id"],
                "front": f"{row['stem']}\n\n**{row['lead_in']}**",
                "back": f"**Đáp án:** {item['options'][row['answer']]}\n\n"
                        f"{item['explanations'][row['answer']]['why']}",
                "sources": item["sources"]}
    src = source_refs(con, json.loads(card["sources"]))  # its items were all rejected
    return {**out, "mode": "flash", "front": f"Nhớ lại nội dung chính của: {view['title']}",
            "back": (src[0]["text"] + " [S1]") if src else "", "sources": src}


def review(con: sqlite3.Connection, username: str, card_id: int, rating: str,
           item_id: int | None = None, now: datetime | None = None) -> dict:
    """A self-rated flashcard or open-recall review."""
    if rating not in RATINGS:
        raise ValueError(f"unknown rating {rating!r}")
    card = con.execute("SELECT * FROM revision_cards WHERE id = ? AND username = ?",
                       (card_id, username)).fetchone()
    if card is None:
        raise KeyError(card_id)
    with con:
        card = _review(con, card, rating, False, item_id, now or now_utc())
    return _summary(card, "reviewed")


def list_cards(con: sqlite3.Connection, username: str, now: datetime | None = None) -> dict:
    now = now or now_utc()
    cards = [{"id": c["id"], "origin": c["origin"], "title": _title(con, c), "step": c["step"],
              "due": c["due"], "lapses": c["lapses"], "reviews": c["reviews"],
              "created": c["created"]}
             for c in con.execute("SELECT * FROM revision_cards WHERE username = ? "
                                  "ORDER BY due IS NULL, due", (username,))]
    return {"cards": cards, "due": due_count(con, username, now),
            "mastered": sum(c["step"] >= MASTERED for c in cards), "total": len(cards)}


def delete(con: sqlite3.Connection, username: str, card_id: int) -> None:
    with con:
        if con.execute("DELETE FROM revision_cards WHERE id = ? AND username = ?",
                       (card_id, username)).rowcount == 0:
            raise KeyError(card_id)
