"""Pedagogical evaluation, step 2: a rubric judge on every answer, blind to the condition.

Dimensions (1–5; null when it does not apply), from the revised Bloom taxonomy, scaffolding
(Wood, Bruner & Ross 1976; fading: van de Pol et al. 2010) and the MRBench tutor dimensions
(Maurya et al. 2025: mistake identification, providing guidance, actionability, coherence, tutor tone,
humanlikeness), adapted to an answer that is not a dialogue turn:

  bloom_target    explains at the learner's target level (facts / meaning / steps / distinctions / criteria)
  scaffolding     supports the climb in a way that fits the profile: bridge to weak prior knowledge,
                  steps, a check for understanding; less for a strong learner (over-scaffolding scores low)
  prerequisite    connects to the weak prior knowledge named in the profile (null if none named)
  misconception   names the learner's known confusion and states what the guideline says (null if none)
  actionability   the learner knows what to think about or do next
  coherence       one clear line of explanation, no contradiction or jumble
  tone            professional, encouraging, not condescending (a weak learner is not talked down to)
  faithfulness    everything stated is supported by the passages (5) … invents facts (1)

Two judges from different model families (Claude Haiku made the answers; Gemini Flash-Lite is the
less self-biased one). Both are reported; neither is ground truth: human.py samples 20 answers for
people in the team to score with the same rubric, and agreement.py compares them.
"""
import argparse
import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "retrieval_eval"))
from common import ask_json  # noqa: E402
from rerank_eval import make  # noqa: E402

from app.chat.personalize import BLOOM_VI, profile  # noqa: E402
from app.config import settings  # noqa: E402

DIMENSIONS = ["bloom_target", "scaffolding", "prerequisite", "misconception", "actionability", "coherence", "tone",
              "faithfulness"]
TARGET_VI = {1: "nêu đúng khái niệm, sự kiện, con số cốt lõi", 2: "giải thích ý nghĩa, vì sao, cơ chế",
             3: "các bước làm theo thứ tự và điều kiện áp dụng", 4: "phân biệt các trường hợp, quan hệ giữa các yếu tố",
             5: "tiêu chí, ngưỡng, thứ tự ưu tiên để ra quyết định", 6: "tổng hợp thành quy trình hoặc kế hoạch"}
SYSTEM = """You are an expert medical educator grading a tutor's answer for a Vietnamese preventive-medicine student, against a rubric. The user gives the student's question, the learner profile (what the tutor knew about the student), the source passages, and the answer.
Score each dimension 1–5 (5 best), or null when the dimension does not apply:
- bloom_target: does the answer explain at the profile's TARGET Bloom level, in the way described for it? A plain list of facts for a learner whose target is Apply or Analyse scores low.
- scaffolding: does it support the learner's climb in a way that fits the profile: building on what they hold, ordered steps where useful, a check for understanding? For a strong learner, heavy scaffolding is a fault (score low); concise and expert-level scores high.
- prerequisite: if the profile names weak prior knowledge: does the answer connect to it correctly? null if the profile names none.
- misconception: if the profile names a past confusion: does the answer identify it and state what is correct? null if none.
- actionability: after reading, does the learner know what to think about or do next?
- coherence: one clear line of explanation, no contradiction, repetition or jumble.
- tone: professional and encouraging; never condescending; a weak learner is not talked down to.
- faithfulness: is everything in the answer supported by the passages? 5 = fully, 1 = invents facts.
Be strict and use the whole scale. Output JSON only: {"scores": {"bloom_target": n, "scaffolding": n, "prerequisite": n|null, "misconception": n|null, "actionability": n, "coherence": n, "tone": n, "faithfulness": n}, "comment": "<one Vietnamese sentence>"}"""


def describe(row: dict, prof: dict) -> str:
    rungs = {int(k): tuple(v) for k, v in prof["rungs"].items()}
    secure, frontier = profile(rungs, settings()["personalization"])
    held = ", ".join(BLOOM_VI[l] for l in range(1, secure + 1)) or "chưa mức nào"
    lines = [f"- Đã vững (thang Bloom, ở chủ đề này): {held}.",
             f"- Mức cần hướng tới: {BLOOM_VI[frontier]} ({TARGET_VI[frontier]})."]
    if row["prerequisites"]:
        lines.append(f"- Kiến thức nền còn yếu: {', '.join(row['prerequisites'])}.")
    if row["misconception"]:
        m = row["misconception"]
        lines.append(f"- Từng nhầm: chọn \"{m['chosen']}\" ở câu \"{m['stem']}\" (đúng: \"{m['correct']}\").")
    return "\n".join(lines)


def judge_one(gw, row: dict, prof: dict) -> dict | None:
    passages = [*row["passages"], *(row.get("bridge") or [])]
    blocks = "\n\n".join(f"[{p['id']}]\n{p['text'][:1200]}" for p in passages)
    user = (f"Câu hỏi của sinh viên: {row['question']}\n\nHồ sơ người học:\n{describe(row, prof)}\n\n"
            f"Đoạn tài liệu nguồn:\n{blocks}\n\nCâu trả lời cần chấm:\n{row['text']}")
    data = ask_json(gw, SYSTEM, user, "pedagogy-judge-v1")
    raw = data.get("scores") if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        return None
    scores = {d: (raw.get(d) if isinstance(raw.get(d), (int, float)) and 1 <= raw.get(d) <= 5 else None)
              for d in DIMENSIONS}
    return {"scores": scores, "comment": str(data.get("comment", ""))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", help="a run directory of run.py")
    ap.add_argument("--judges", default="google,anthropic")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    run = Path(args.run)
    rows = [json.loads(l) for l in (run / "answers.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    profiles = {p["id"]: p for p in yaml.safe_load((HERE / "cases.yaml").read_text(encoding="utf-8"))["profiles"]}
    order = list(range(len(rows)))
    random.Random(7).shuffle(order)                     # blind: the conditions are mixed
    for name in args.judges.split(","):
        gw = make(name)
        with ThreadPoolExecutor(args.workers) as pool:
            got = dict(zip(order, pool.map(lambda i: judge_one(gw, rows[i], profiles[rows[i]["profile"]]), order)))
        out = [{"i": i, "question_id": rows[i]["question_id"], "profile": rows[i]["profile"],
                "condition": rows[i]["condition"], **(got[i] or {"scores": None})} for i in range(len(rows))]
        (run / f"judged-{name}.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n",
                                                  encoding="utf-8")
        print(name, "judged", sum(1 for r in out if r["scores"]), "of", len(out), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
