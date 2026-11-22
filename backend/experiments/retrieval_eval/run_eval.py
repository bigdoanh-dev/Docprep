"""Scores today's retrieval on the silver set (silver_set.jsonl, from build_set.py). No model calls
except the bge-m3 query embedding.

For in-scope questions: Hit@1/5/30 and MRR@10 of the gold passages, for
  hybrid    the chat worker's path for a real provider (bge-m3 + full text, RRF); the chat sends the top 5
  keyword   the path without a model (full text + coverage threshold min_score), as the chat sends it
For out-of-scope questions: how often something is still sent to the model.
For the future gate: the best cosine similarity and the top RRF score of every question, and how well a
single threshold on each separates in-scope from out-of-scope (AUC, best accuracy).
"""
import argparse
import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from app.chat import clarify
from app.chat.pregate import PREGATE_PATH, is_patient_specific, load_patterns
from app.db import connect
from app.repo import content
from common import active_version, gateway, hybrid, keyword

HERE = Path(__file__).resolve().parent


def cosines(conn, vector, ids: list[str], version: str) -> dict[str, float]:
    rows = conn.execute("""select passage_id, 1 - (embedding <=> %s::vector) as cos from passage_embedding
                           where passage_id = any(%s) and corpus_version = %s""",
                        (json.dumps(vector.vectors[0]), ids, version)).fetchall()
    return {r["passage_id"]: float(r["cos"]) for r in rows}


def rank_of(ids: list[str], gold: set[str]) -> int | None:
    return next((i + 1 for i, pid in enumerate(ids) if pid in gold), None)


def auc(pos: list[float], neg: list[float]) -> float | None:
    """P(score of an in-scope question > score of an out-of-scope one); ties count half."""
    if not pos or not neg:
        return None
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def best_threshold(pos: list[float], neg: list[float]) -> tuple[float, float] | None:
    if not pos or not neg:
        return None
    cuts = sorted(set(pos + neg))
    scored = [(sum(p >= t for p in pos) + sum(n < t for n in neg), t) for t in cuts]
    right, t = max(scored)
    return t, right / (len(pos) + len(neg))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default=str(HERE / "silver_set.jsonl"))
    ap.add_argument("--out", default=str(HERE / "out"))
    args = ap.parse_args()
    items = [json.loads(l) for l in open(args.set, encoding="utf-8") if l.strip()]
    gw, rules = gateway(), load_patterns(PREGATE_PATH)
    out = Path(args.out) / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True)

    rows = []
    with connect() as conn:
        version, glossary = active_version(conn), content.glossary(conn)
        for it in items:
            q, gold = it["question"], set(it.get("gold") or [])
            blocked = ("pregate" if is_patient_specific(q, rules) else
                       "clarify" if clarify.options(q, glossary) else None)
            h = hybrid(conn, gw, q, 30)
            kw_rank = keyword(conn, q, 30, min_score=0.0)
            kw_sent = keyword(conn, q, 5)                    # what the keyword path really sends
            vector = gw.embed([q])
            cos = cosines(conn, vector, [p.id for p in h], version)
            h_ids = [p.id for p in h]
            rows.append({
                "id": it["id"], "type": it["type"], "style": it.get("style"), "document": it.get("document"),
                "question": q, "blocked": blocked, "gold": sorted(gold),
                "hybrid_rank": rank_of(h_ids, gold), "keyword_rank": rank_of([p.id for p in kw_rank], gold),
                "keyword_sent": len(kw_sent), "keyword_sent_hit": bool(gold & {p.id for p in kw_sent}),
                "top_cos": max(cos.values()) if cos else None, "top5_cos": [round(cos.get(i, 0), 4) for i in h_ids[:5]],
                "top_rrf": h[0].score if h else None, "hybrid_top5": h_ids[:5],
            })
    (out / "results.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    (out / "summary.md").write_text(summary(rows), encoding="utf-8")
    print(out)
    print(summary(rows))
    return 0


def metrics(rs: list[dict], key: str) -> dict:
    ranks = [r[key] for r in rs]
    hit = lambda k: sum(1 for x in ranks if x is not None and x <= k) / len(ranks)
    return {"n": len(rs), "hit1": hit(1), "hit5": hit(5), "hit30": hit(30),
            "mrr10": statistics.mean((1 / x) if x is not None and x <= 10 else 0 for x in ranks)}


def pct(x):
    return "—" if x is None else f"{x:.0%}"


def summary(rows: list[dict]) -> str:
    ins = [r for r in rows if r["type"] == "in_scope"]
    oos = [r for r in rows if r["type"] == "out_of_scope"]
    L = ["# Retrieval trên bộ silver", "",
         f"{len(ins)} câu trong phạm vi, {len(oos)} câu ngoài phạm vi. Nhãn do model gắn (pooling), chưa có người duyệt.", "",
         "## Câu trong phạm vi", "",
         "| Cách tìm | Hit@1 | Hit@5 (chat gửi 5) | Hit@30 (trần cho reranker) | MRR@10 |", "|---|---|---|---|---|"]
    for name, key in (("Kết hợp (bge-m3 + full text, RRF)", "hybrid_rank"), ("Chỉ từ khoá (xếp hạng, không ngưỡng)", "keyword_rank")):
        m = metrics(ins, key)
        L.append(f"| {name} | {pct(m['hit1'])} | {pct(m['hit5'])} | {pct(m['hit30'])} | {m['mrr10']:.2f} |")
    kw_sent = sum(r["keyword_sent_hit"] for r in ins) / len(ins) if ins else None
    L += ["", f"Đường chỉ từ khoá với ngưỡng min_score (khi không có model): gửi đúng đoạn ở {pct(kw_sent)} câu; "
          f"không gửi gì ở {pct(sum(r['keyword_sent'] == 0 for r in ins) / len(ins) if ins else None)} câu.", ""]
    for label, field in (("kiểu câu hỏi", "style"), ("tài liệu", "document")):
        groups = defaultdict(list)
        for r in ins:
            groups[r[field]].append(r)
        L += [f"### Theo {label} (kết hợp)", "", "| Nhóm | Số câu | Hit@5 | Hit@30 |", "|---|---|---|---|"]
        for g, rs in sorted(groups.items(), key=lambda kv: str(kv[0])):
            m = metrics(rs, "hybrid_rank")
            L.append(f"| {g} | {m['n']} | {pct(m['hit5'])} | {pct(m['hit30'])} |")
        L.append("")
    L += ["## Câu ngoài phạm vi", "",
          f"- Kết hợp: gửi 5 đoạn sang model ở {pct(sum(1 for r in oos if r['hybrid_top5']) / len(oos) if oos else None)} câu (chưa có cổng đủ bằng chứng).",
          f"- Chỉ từ khoá: gửi ít nhất 1 đoạn ở {pct(sum(r['keyword_sent'] > 0 for r in oos) / len(oos) if oos else None)} câu.",
          f"- Bị chặn trước khi tìm (pregate / hỏi lại): {sum(1 for r in rows if r['blocked'])} câu.", "",
          "## Dữ liệu cho cổng đủ bằng chứng", "",
          "Một ngưỡng duy nhất trên điểm này tách câu trong và ngoài phạm vi tốt đến đâu (chưa có reranker).", "",
          "| Điểm | TB trong phạm vi | TB ngoài phạm vi | AUC | Ngưỡng tốt nhất | Đúng ở ngưỡng đó |", "|---|---|---|---|---|---|"]
    for name, key in (("Cosine bge-m3 cao nhất", "top_cos"), ("Điểm RRF cao nhất", "top_rrf")):
        pos = [r[key] for r in ins if r[key] is not None]
        neg = [r[key] for r in oos if r[key] is not None]
        bt = best_threshold(pos, neg)
        L.append(f"| {name} | {statistics.mean(pos):.3f} | {statistics.mean(neg):.3f} | "
                 f"{auc(pos, neg):.2f} | {bt[0]:.3f} | {pct(bt[1])} |" if pos and neg else f"| {name} | — | — | — | — | — |")
    missed = [r for r in ins if r["hybrid_rank"] is None or r["hybrid_rank"] > 5]
    L += ["", f"## Câu trong phạm vi mà kết hợp không đưa đoạn đúng vào top 5 ({len(missed)})", ""]
    L += [f"- `{r['id']}` [{r['style']}] {r['question']} → hạng {r['hybrid_rank'] or '>30'}" for r in missed]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
