"""Pedagogical evaluation, step 3: the summary of the judges' scores (summary.md in the run directory).
No model calls."""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from judge import DIMENSIONS

CONDITIONS = ["C0_base", "C1_v1", "C2_bloom", "C3_scaffold"]
LABEL = {"C0_base": "C0 không cá nhân hoá", "C1_v1": "C1 bản cũ (mastery 3 mức)", "C2_bloom": "C2 chỉ Bloom",
         "C3_scaffold": "C3 Bloom + scaffolding"}


def table(rows, key=lambda r: r["condition"], keys=CONDITIONS, label=LABEL) -> list[str]:
    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r.get("scores"):
            for d in DIMENSIONS:
                if r["scores"].get(d) is not None:
                    by[key(r)][d].append(r["scores"][d])
    out = ["| | " + " | ".join(DIMENSIONS) + " |", "|---" * (len(DIMENSIONS) + 1) + "|"]
    for k in keys:
        cells = [f"{statistics.mean(by[k][d]):.2f}" if by[k][d] else "—" for d in DIMENSIONS]
        out.append(f"| {label.get(k, k)} | " + " | ".join(cells) + " |")
    return out


def main() -> int:
    run = Path(sys.argv[1])
    answers = [json.loads(l) for l in (run / "answers.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    L = ["# Đánh giá sư phạm", "",
         f"{len({a['question_id'] for a in answers})} câu hỏi × {len({a['profile'] for a in answers})} hồ sơ người học "
         "giả lập × 4 điều kiện, cùng các ý đã kiểm của tầng A. Điểm 1–5, trung bình; — là không áp dụng.", "",
         "## Tầng B có chạy được không", "", "| Điều kiện | Dùng bản cá nhân hoá | Quay về tầng A (lý do) |", "|---|---|---|"]
    for c in CONDITIONS[1:]:
        rows = [a for a in answers if a["condition"] == c]
        fails = defaultdict(int)
        for a in rows:
            if not a["adapted"]:
                fails[a["failure"]] += 1
        L.append(f"| {LABEL[c]} | {sum(bool(a['adapted']) for a in rows)}/{len(rows)} | "
                 f"{', '.join(f'{k} {v}' for k, v in fails.items()) or '—'} |")
    for judge in ("google", "anthropic"):
        f = run / f"judged-{judge}.jsonl"
        if not f.exists():
            continue
        judged = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        name = "Gemini Flash-Lite (khác họ model với người viết)" if judge == "google" else "Claude Haiku (cùng họ với người viết)"
        L += ["", f"## Giám khảo: {name}", "", f"Chấm được {sum(1 for r in judged if r.get('scores'))}/{len(judged)}.", ""]
        L += table(judged)
        L += ["", "### Theo hồ sơ người học (C3 so với C0)", ""]
        profs = sorted({r["profile"] for r in judged})
        for c in ("C0_base", "C3_scaffold"):
            L += ["", f"**{LABEL[c]}**", ""]
            L += table([r for r in judged if r["condition"] == c], key=lambda r: r["profile"], keys=profs, label={})
    (run / "summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
