"""LLM reranking of the hybrid top 30, and a gate on its scores, measured on the silver set.

No GPU or server: the reranker is a model reached by API key. Each question's hybrid top 30 is shown
to the model, which scores every passage 0–3; passages are re-sorted by that score (ties keep the RRF
order) and the best score is the gate: below the threshold, nothing would be sent to the answer model.

The silver labels were made by Claude Haiku, so a Haiku reranker partly agrees with itself; Gemini
(another model family) is the fair test. Both can be run; the summary says which is which.
"""
import argparse
import json
import re
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from app.db import connect
from common import ask_json, hybrid
from run_eval import auc, best_threshold, rank_of

HERE = Path(__file__).resolve().parent
SYSTEM = """You rank search results for a Vietnamese preventive-medicine study chatbot. Given a student's question and numbered passages from clinical guidelines, score every passage:
3 = states the answer to the question; 2 = states a main part of the answer; 1 = same topic but does not answer it; 0 = unrelated.
Judge only from the passages. Score every passage.
Output JSON only: {"scores": {"P1": <0-3>, "P2": <0-3>, ...}}"""


def make(provider: str):
    from app.ollama_gateway import OllamaConfig
    if provider == "google":
        from app.google_gateway import GoogleConfig, GoogleGateway
        return GoogleGateway(OllamaConfig.load(), GoogleConfig.load())
    from common import gateway
    return gateway()


def score(gw, question: str, cands) -> tuple[list[int] | None, float]:
    blocks = "\n\n".join(f"[P{i + 1}] ({c.document_title} › {c.chapter or ''} › {c.section or ''})\n{c.text[:1200]}"
                         for i, c in enumerate(cands))
    t = time.monotonic()
    data = ask_json(gw, SYSTEM, f"Câu hỏi: {question}\n\n{blocks}", "rerank-llm-v1")
    secs = time.monotonic() - t
    raw = data.get("scores") if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        return None, secs
    got = {int(m.group(1)): v for k, v in raw.items() if (m := re.fullmatch(r"P?(\d+)", str(k).strip()))}
    return [int(got.get(i + 1, 0)) if str(got.get(i + 1, 0)).isdigit() else 0 for i in range(len(cands))], secs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default=str(HERE / "silver_set.jsonl"))
    ap.add_argument("--provider", choices=["google", "anthropic"], default="google")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--out", default=str(HERE / "out"))
    args = ap.parse_args()
    items = [json.loads(l) for l in open(args.set, encoding="utf-8") if l.strip()]
    from common import gateway
    embedder, gw = gateway(), make(args.provider)

    with connect() as conn:
        pools = [hybrid(conn, embedder, it["question"], 30) for it in items]
    with ThreadPoolExecutor(args.workers) as pool:
        scored = list(pool.map(lambda ip: score(gw, ip[0]["question"], ip[1]), zip(items, pools)))

    rows = []
    for it, cands, (scores, secs) in zip(items, pools, scored):
        ids = [c.id for c in cands]
        gold = set(it.get("gold") or [])
        if scores is None:
            rows.append({"id": it["id"], "type": it["type"], "failed": True}); continue
        order = sorted(range(len(ids)), key=lambda i: (-scores[i], i))     # ties keep the RRF order
        rows.append({"id": it["id"], "type": it["type"], "style": it.get("style"), "question": it["question"],
                     "rrf_rank": rank_of(ids, gold), "rerank_rank": rank_of([ids[i] for i in order], gold),
                     "top_score": max(scores), "n3": scores.count(3), "secs": round(secs, 1)})
    out = Path(args.out) / f"{datetime.now():%Y%m%d-%H%M%S}-rerank-{args.provider}"
    out.mkdir(parents=True)
    (out / "results.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    text = summary(rows, args.provider)
    (out / "summary.md").write_text(text, encoding="utf-8")
    print(out); print(text)
    return 0


def summary(rows, provider) -> str:
    ok = [r for r in rows if not r.get("failed")]
    ins = [r for r in ok if r["type"] == "in_scope"]
    oos = [r for r in ok if r["type"] == "out_of_scope"]

    def m(key):
        ranks = [r[key] for r in ins]
        hit = lambda k: sum(1 for x in ranks if x is not None and x <= k) / len(ranks)
        return hit(1), hit(5), statistics.mean((1 / x) if x and x <= 10 else 0 for x in ranks)

    L = [f"# Rerank bằng LLM ({provider})", "",
         f"{len(ins)} câu trong phạm vi, {len(oos)} ngoài phạm vi; {len(rows) - len(ok)} lượt chấm lỗi."
         + (" Nhãn silver do Claude Haiku gắn: reranker Haiku được lợi một phần." if provider == "anthropic" else ""), "",
         "| Thứ tự | Hit@1 | Hit@5 | MRR@10 |", "|---|---|---|---|"]
    for name, key in (("RRF hiện tại", "rrf_rank"), ("Sau rerank", "rerank_rank")):
        h1, h5, mrr = m(key)
        L.append(f"| {name} | {h1:.0%} | {h5:.0%} | {mrr:.2f} |")
    pos, neg = [r["top_score"] for r in ins], [r["top_score"] for r in oos]
    L += ["", "## Cổng theo điểm cao nhất (0–3)", "", f"AUC {auc(pos, neg):.2f}.", "",
          "| Cho qua khi điểm cao nhất ≥ | Câu hợp lệ bị chặn nhầm | Câu ngoài phạm vi bị chặn đúng |", "|---|---|---|"]
    for t in (1, 2, 3):
        L.append(f"| {t} | {sum(p < t for p in pos)}/{len(pos)} | {sum(n < t for n in neg)}/{len(neg)} |")
    secs = [r["secs"] for r in ok]
    L += ["", f"Thời gian mỗi lượt rerank: trung vị {statistics.median(secs):.1f} giây, chậm nhất {max(secs):.1f} giây."]
    lost = [r for r in ins if (r["rerank_rank"] or 99) > 5 and (r["rrf_rank"] or 99) <= 5]
    L += ["", f"Câu RRF có đoạn đúng trong top 5 nhưng rerank làm rớt: {len(lost)}"]
    L += [f"- `{r['id']}` {r['question']} (RRF hạng {r['rrf_rank']} → {r['rerank_rank'] or '>30'})" for r in lost]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
