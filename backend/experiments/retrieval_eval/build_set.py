"""Builds a SILVER retrieval test set from the active corpus release, without human labels.

1. Sample passages evenly across documents and chapters.
2. For each, the model writes a question a preventive-medicine student would ask, answerable from that
   passage, in its own words (not copying the passage, so keyword search gets no free ride), plus a
   quote proving it is answerable.
3. Out-of-scope questions: the model writes questions in the same field that the release's chapters
   do not cover.
4. Pooling (as in TREC): the union of the hybrid top 30 and the keyword top 30 is shown to the model,
   which marks every passage that answers the question. Gold = those passages, so near-duplicates
   (the Dengue appendices for children and adults) count as correct too.
5. Filters: an in-scope question is kept only when its own source passage is marked as answering it;
   an out-of-scope question only when no candidate answers it even partly.

Labels are machine-made: this is a silver set, good for comparing retrieval versions, not a final
truth. Run inside the chat container (see README.md).
"""
import argparse
import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.chat.postcheck import _squash
from app.chat.retrieval import get_passages
from app.db import connect
from common import ask_json, gateway, hybrid, keyword, seeded, visible_passages

HERE = Path(__file__).resolve().parent
STYLES = {
    "dinh_nghia": "hỏi khái niệm hoặc định nghĩa",
    "so_lieu": "hỏi con số, ngưỡng, liều, thời gian hoặc tiêu chuẩn cụ thể",
    "quy_trinh": "hỏi các bước, cách xử trí hoặc cách theo dõi",
    "phan_biet": "hỏi dấu hiệu, tiêu chí phân biệt hoặc phân loại",
    "ly_do": "hỏi vì sao, khi nào hoặc trong trường hợp nào",
}
QUESTION_SYSTEM = """You write study questions for Vietnamese preventive-medicine students, to test a search engine.
Given one passage from a Vietnamese clinical guideline, write ONE question in Vietnamese that a student would type into a study chatbot, such that this passage answers it.

Rules
- The passage alone must answer it. Ask about something the passage actually states.
- Use the student's own words: do not copy distinctive phrases from the passage; paraphrase, and use everyday or alternative medical wording where natural. Name the disease or topic so the question makes sense on its own.
- Never ask about one specific patient (no "con tôi", "bệnh nhân này", no dose for a person). Ask in general.
- Never refer to "đoạn văn", "tài liệu", "bảng trên".
- Keep it to one sentence, under 30 words.
Output JSON only: {"question": "...", "answer_quote": "<words copied exactly from the passage that answer it>"}"""
OOS_SYSTEM = """You write test questions for a study chatbot for Vietnamese preventive-medicine students. The chatbot can only answer from the guideline chapters listed by the user.
Write questions in Vietnamese, in the same medical field, that these chapters do NOT answer. Mix two kinds:
- "gan": close to the listed topics but not covered by them (another disease of the same group, a drug or vaccine detail, an epidemiology method);
- "xa": other medical or public-health topics.
Never ask about one specific patient. One sentence each.
Output JSON only: {"questions": [{"question": "...", "kind": "gan" | "xa"}]}"""
JUDGE_SYSTEM = """You label search results for a Vietnamese medical study chatbot. Given a student's question and numbered passages, decide for each passage whether it answers the question.
- "answers": the passage states the answer, or the main part of it, so a tutor could answer from it alone.
- "partial": the passage states something directly useful for the answer, but not its main part.
Ignore passages that only mention the same disease or words. Judge only from the passages.
Output JSON only: {"answers": ["P3", ...], "partial": ["P7", ...]}"""


def sample(passages: list[dict], n: int, rng) -> list[dict]:
    """Round-robin over documents, then over each document's chapters, so no chapter dominates."""
    ok = [p for p in passages if len(p["text"]) >= 250]
    by_doc = defaultdict(lambda: defaultdict(list))
    for p in ok:
        by_doc[p["document"]][p["chapter"] or ""].append(p)
    queues = {}
    for doc, chapters in by_doc.items():
        order = list(chapters.values())
        for c in order:
            rng.shuffle(c)
        rng.shuffle(order)
        flat = []
        while any(order):
            for c in order:
                if c:
                    flat.append(c.pop())
        queues[doc] = flat
    picked, docs = [], list(queues)
    while len(picked) < n and any(queues.values()):
        for d in docs:
            if queues[d] and len(picked) < n:
                picked.append(queues[d].pop(0))
    return picked


def write_question(gw, p: dict, style: str) -> dict | None:
    user = (f"Kiểu câu hỏi: {STYLES[style]} (nếu đoạn không có nội dung kiểu này, chọn kiểu phù hợp nhất).\n\n"
            f"Vị trí: {p['document']} › {p['context'] or p['chapter'] or ''}\n\nĐoạn:\n{p['text']}")
    data = ask_json(gw, QUESTION_SYSTEM, user, "eval-question-v1")
    if not data or not isinstance(data.get("question"), str) or not isinstance(data.get("answer_quote"), str):
        return None
    if len(data["answer_quote"].split()) < 2 or _squash(data["answer_quote"]) not in _squash(p["text"]):
        return None                                   # the quote is not in the passage: not provably answerable
    return {"question": data["question"].strip(), "answer_quote": data["answer_quote"]}


def candidates(conn, gw, text: str, source: str | None = None, cap: int = 45) -> list:
    """The pool: hybrid top 30 and keyword top 30, interleaved and de-duplicated, capped; the source
    passage is always in it (shuffled in place, so its position tells the judge nothing)."""
    a, b = hybrid(conn, gw, text, 30), keyword(conn, text, 30, min_score=0.0)
    seen, out = set(), []
    for i in range(max(len(a), len(b))):
        for ranking in (a, b):
            if i < len(ranking) and ranking[i].id not in seen:
                seen.add(ranking[i].id); out.append(ranking[i])
    out = out[:cap]
    if source and source not in {p.id for p in out}:
        out = out[:cap - 1] + list(get_passages(conn, [source]).values())
    return out


def judge(gw, question: str, cands: list) -> dict | None:
    blocks = "\n\n".join(f"[P{i + 1}] ({c.document_title} › {c.chapter or ''} › {c.section or ''})\n{c.text[:1500]}"
                         for i, c in enumerate(cands))
    data = ask_json(gw, JUDGE_SYSTEM, f"Câu hỏi: {question}\n\n{blocks}", "eval-judge-v1")
    if not data:
        return None
    pick = lambda key: [cands[int(m) - 1].id for m in re.findall(r"P(\d+)", " ".join(map(str, data.get(key) or [])))
                        if 0 < int(m) <= len(cands)]
    return {"answers": list(dict.fromkeys(pick("answers"))), "partial": list(dict.fromkeys(pick("partial")))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-scope", type=int, default=90, help="passages to write questions from (some are filtered out)")
    ap.add_argument("--out-of-scope", type=int, default=30)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=str(HERE / "silver_set.jsonl"))
    args = ap.parse_args()
    rng, gw = seeded(), gateway()

    with connect() as conn:
        passages = visible_passages(conn)
        picked = sample(passages, args.in_scope, rng)
        chapters = sorted({f"{p['document']} › {p['chapter']}" for p in passages if p["chapter"]})
    print(f"{len(passages)} passages visible; {len(picked)} sampled; {len(chapters)} chapters")

    styles = list(STYLES)
    with ThreadPoolExecutor(args.workers) as pool:
        written = list(pool.map(lambda ip: write_question(gw, ip[1], styles[ip[0] % len(styles)]), enumerate(picked)))
    items = [{"type": "in_scope", "style": styles[i % len(styles)], "source": p["id"], "document": p["document"],
              "chapter": p["chapter"], **w} for i, (p, w) in enumerate(zip(picked, written)) if w]
    oos = ask_json(gw, OOS_SYSTEM, "Các chương có trong kho:\n" + "\n".join(chapters) +
                   f"\n\nViết {args.out_of_scope} câu hỏi.", "eval-oos-v1") or {}
    items += [{"type": "out_of_scope", "style": q.get("kind"), "question": q["question"].strip()}
              for q in oos.get("questions", []) if isinstance(q, dict) and isinstance(q.get("question"), str)]
    print(f"{sum(i['type'] == 'in_scope' for i in items)} in-scope written, {sum(i['type'] == 'out_of_scope' for i in items)} out-of-scope")

    with connect() as conn:                          # retrieval needs the database: one thread
        for it in items:
            it["_cands"] = candidates(conn, gw, it["question"], it.get("source"))
            rng.shuffle(it["_cands"])
    with ThreadPoolExecutor(args.workers) as pool:
        labels = list(pool.map(lambda it: judge(gw, it["question"], it["_cands"]), items))

    kept, dropped = [], defaultdict(int)
    for it, lab in zip(items, labels):
        pool_size = len(it.pop("_cands"))
        if lab is None:
            dropped["judge_failed"] += 1; continue
        if it["type"] == "in_scope" and it["source"] not in lab["answers"]:
            dropped["source_not_confirmed"] += 1; continue
        if it["type"] == "out_of_scope" and (lab["answers"] or lab["partial"]):
            dropped["oos_answered_by_corpus"] += 1; continue
        kept.append({**it, "gold": lab["answers"], "partial": lab["partial"], "pool": pool_size})
    for n, it in enumerate(kept, 1):
        it["id"] = f"{'IN' if it['type'] == 'in_scope' else 'OUT'}-{n:03d}"
    Path(args.out).write_text("\n".join(json.dumps(k, ensure_ascii=False) for k in kept) + "\n", encoding="utf-8")
    print(f"kept {len(kept)} ({sum(k['type'] == 'in_scope' for k in kept)} in, "
          f"{sum(k['type'] == 'out_of_scope' for k in kept)} out); dropped {dict(dropped)} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
