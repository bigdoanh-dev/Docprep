"""Six-level Bloom labels for the real (non-synthetic) approved questions, made by two models.

The bank stores three grouped bands (1 = Nhớ/Hiểu, 2 = Vận dụng, 3 = Phân tích/Đánh giá) and an
optional six-level `bloom_level_6` that nobody has filled yet. Each question (stem, options with
their rationales, explanation) is labelled by Claude Haiku and by Gemini Flash-Lite independently,
using the revised taxonomy (Anderson & Krathwohl 2001) with the cognitive process the learner must
perform to pick the key. Output: labels.jsonl with both labels, the agreed label, and whether the
label fits the stored band.

MACHINE-MADE, NOT REVIEWED (decided 2026-11-23: no expert review for now). apply.py writes the
agreed label into question_bloom_label so the chat can use it; reviewed labels go to bloom_level_6.
Run inside the chat container (see ../retrieval_eval/README.md for the tar/PYTHONPATH pattern).
"""
import argparse
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.db import connect
from common import ask_json
from rerank_eval import make

HERE = Path(__file__).resolve().parent
SYSTEM = """You classify exam questions for Vietnamese preventive-medicine students by the revised Bloom taxonomy (Anderson & Krathwohl 2001), by the cognitive process a student must perform to choose the correct option:
1 Nhớ (Remember): recall a fact, definition, schedule, number or list as stated.
2 Hiểu (Understand): explain, interpret, classify, summarise or give the meaning of something in other words.
3 Vận dụng (Apply): carry out or use a procedure, rule or formula in a given situation (calculate, choose the step to do).
4 Phân tích (Analyse): break a situation into parts, distinguish relevant from irrelevant data, find the cause or the relation between factors, differentiate similar conditions.
5 Đánh giá (Evaluate): judge or decide using criteria: choose the best or most appropriate option among plausible ones, prioritise, critique.
6 Sáng tạo (Create): put elements together into a new plan, design or proposal.
A question with a scenario is not automatically level 3+: if the scenario only decorates a recall, it is level 1. Judge what is needed to reject the distractors, using their rationales.
Output JSON only: {"level": <1-6>, "reason": "<one Vietnamese sentence>"}"""
BAND_RANGE = {1: {1, 2}, 2: {3}, 3: {4, 5}}


def text_of(q: dict) -> str:
    opts = "\n".join(f"{o['key']}. {o['text']}{' (đáp án)' if o.get('is_correct') else ''} — lý do: {o.get('rationale', '')}"
                     for o in q["options"])
    return f"Câu hỏi: {q['stem']}\n\nCác phương án:\n{opts}\n\nGiải thích: {q['explanation']}"


def label(gw, q: dict) -> dict | None:
    data = ask_json(gw, SYSTEM, text_of(q), "bloom6-label-v1")
    if not isinstance(data, dict) or data.get("level") not in (1, 2, 3, 4, 5, 6):
        return None
    return {"level": data["level"], "reason": str(data.get("reason", ""))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "labels.jsonl"))
    args = ap.parse_args()
    with connect() as conn:
        qs = conn.execute("""select id, version, stem, options, explanation, competency_code, bloom_level
                             from question where not is_synthetic and status = 'approved' order by id""").fetchall()
    models = {"haiku": make("anthropic"), "gemini": make("google")}
    got = {}
    for name, gw in models.items():
        with ThreadPoolExecutor(3) as pool:
            got[name] = list(pool.map(lambda q: label(gw, q), qs))
    rows = []
    for i, q in enumerate(qs):
        h, g = got["haiku"][i], got["gemini"][i]
        levels = [x["level"] for x in (h, g) if x]
        # Agreed label: both the same; otherwise the lower one (do not claim a higher level than both see).
        agreed = min(levels) if levels else None
        rows.append({"id": q["id"], "version": q["version"], "competency": q["competency_code"], "band": q["bloom_level"],
                     "haiku": h, "gemini": g, "agreed": agreed, "models_agree": len(set(levels)) == 1 and len(levels) == 2,
                     "fits_band": agreed in BAND_RANGE[q["bloom_level"]] if agreed else None,
                     "stem": q["stem"]})
    Path(args.out).write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    both = [r for r in rows if r["haiku"] and r["gemini"]]
    within1 = sum(abs(r["haiku"]["level"] - r["gemini"]["level"]) <= 1 for r in both)
    print(f"{len(rows)} questions; both labelled {len(both)}; exact agreement {sum(r['models_agree'] for r in both)}"
          f"; within one level {within1}; agreed label fits the stored band {sum(bool(r['fits_band']) for r in rows)}")
    print("agreed levels:", dict(sorted(Counter(r["agreed"] for r in rows).items(), key=lambda kv: str(kv[0]))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
