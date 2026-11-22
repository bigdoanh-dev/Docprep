"""Pedagogical evaluation, the human check: a sheet of 20 answers for people in the team to score, and
the agreement between their scores and the judges'.

  python human.py sheet <run>       writes <run>/human_sheet.csv (20 answers, 5 per condition, shuffled,
                                    condition hidden) and <run>/human_key.json (which row is which)
  python human.py agree <run>       reads the filled sheet and prints, per dimension, the Spearman
                                    correlation and the share within one point, human vs each judge

The sheet has the question, the learner profile and the answer; the rubric is in README.md. A human
rater scores 1–5 per dimension or leaves it empty when it does not apply. No model calls.
"""
import csv
import json
import random
import sys
from pathlib import Path

import yaml

from judge import DIMENSIONS, describe

HERE = Path(__file__).resolve().parent


def sheet(run: Path) -> None:
    answers = [json.loads(l) for l in (run / "answers.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    profiles = {p["id"]: p for p in yaml.safe_load((HERE / "cases.yaml").read_text(encoding="utf-8"))["profiles"]}
    rng = random.Random(23)
    picked = []
    for c in ("C0_base", "C1_v1", "C2_bloom", "C3_scaffold"):
        idx = [i for i, a in enumerate(answers) if a["condition"] == c]
        picked += rng.sample(idx, min(5, len(idx)))
    rng.shuffle(picked)
    with open(run / "human_sheet.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["row", "cau_hoi", "ho_so_nguoi_hoc", "cau_tra_loi", *DIMENSIONS, "nhan_xet"])
        for n, i in enumerate(picked, 1):
            a = answers[i]
            w.writerow([n, a["question"], describe(a, profiles[a["profile"]]), a["text"], *[""] * len(DIMENSIONS), ""])
    (run / "human_key.json").write_text(json.dumps({n: i for n, i in enumerate(picked, 1)}), encoding="utf-8")
    print(run / "human_sheet.csv")


def spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3:
        return None

    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2
            i = j + 1
        return r
    rx, ry = ranks(x), ranks(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else None


def agree(run: Path) -> None:
    key = {int(k): v for k, v in json.loads((run / "human_key.json").read_text(encoding="utf-8")).items()}
    with open(run / "human_sheet.csv", encoding="utf-8-sig") as f:
        human = {int(r["row"]): r for r in csv.DictReader(f)}
    for judge in ("google", "anthropic"):
        path = run / f"judged-{judge}.jsonl"
        if not path.exists():
            continue
        judged = {r["i"]: r for r in map(json.loads, path.read_text(encoding="utf-8").splitlines()) if r.get("scores")}
        print(f"\n{judge}: dimension | n | Spearman | within one point")
        for d in DIMENSIONS:
            pairs = [(float(human[n][d]), judged[i]["scores"][d]) for n, i in key.items()
                     if human.get(n, {}).get(d, "").strip() and i in judged and judged[i]["scores"].get(d) is not None]
            if not pairs:
                print(f"{d} | 0 | — | —"); continue
            rho = spearman([a for a, _ in pairs], [b for _, b in pairs])
            near = sum(abs(a - b) <= 1 for a, b in pairs) / len(pairs)
            print(f"{d} | {len(pairs)} | {'—' if rho is None else f'{rho:.2f}'} | {near:.0%}")


if __name__ == "__main__":
    {"sheet": sheet, "agree": agree}[sys.argv[1]](Path(sys.argv[2]))
