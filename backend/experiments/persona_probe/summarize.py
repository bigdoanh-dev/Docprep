"""Summarise a persona-probe run: one table per question, rates over the repeats. Standard library only.

  python summarize.py out/<run>/results.jsonl > out/<run>/summary.md
"""
import json
import re
import statistics
import sys
from collections import Counter, defaultdict


def fmt_pct(x):
    return f"{x:.0%}" if x is not None else "—"


def mean_or_none(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None


def n_sentences(text: str) -> int:
    return len([c for c in re.split(r"\s*(?:\[\d+\])+\s*", text or "") if c.strip()])


def main(path: str) -> None:
    rows = [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]
    by_q = defaultdict(list)
    for r in rows:
        by_q[r["question"]].append(r)
    print("# Persona probe: tổng hợp\n")
    print("- **Trả lời**: số lần trả lời được / số lần chạy. Profile phải xấp xỉ C0, vì hồ sơ không được đổi quyết định đủ tài liệu.")
    print("- **Tầng B dùng**: số lần bản viết lại qua mọi kiểm tra / số lần trả lời. Các lần còn lại hiển thị tầng A; lý do ở cột cuối.")
    print("- **Câu A → B**: số câu trung vị của tầng A và của bản tầng B trong cùng lượt (chỉ tính lượt tầng B được dùng).")
    print("- **Bao phủ**: tỷ lệ ý chính của tầng A còn có trong bản tầng B, cùng lượt (LLM judge). Phải ≈ 100%.\n")
    for q, rs in by_q.items():
        print(f"## {q}\n")
        for r in rs:
            if "note" in r:
                print(f"- {r['condition']}: _{r['note']}_")
        print("\n| Điều kiện | Mức | Trả lời | Tầng B dùng | Câu A → B | Ký tự/câu | Câu có số | Câu có lý do | Bao phủ | Bỏ ở post-check | Lý do quay về A |")
        print("|---|---|---|---|---|---|---|---|---|---|---|")
        groups = defaultdict(list)
        for r in rs:
            if "note" not in r:
                groups[r["condition"]].append(r)
        for cond, g in groups.items():
            ok = [r for r in g if "error" not in r]
            ans = [r for r in ok if r["state"] == "answered"]
            judged = [r for r in ans if r.get("adapted") is not None]
            used = [r for r in judged if r["adapted"]]
            a_to_b = (f"{statistics.median(n_sentences(r['base_text']) for r in used):g} → "
                      f"{statistics.median(r['sentences'] for r in used):g}") if used else "—"
            cov = mean_or_none([(r.get("coverage") or {}).get("coverage") for r in used])
            reasons = Counter(r["adapt_failure"] for r in judged if r.get("adapt_failure"))
            errors = len(g) - len(ok)
            print(f"| {cond}{f' ({errors} lỗi)' if errors else ''} | {g[0].get('level') or '—'} | {len(ans)}/{len(ok)} | "
                  f"{f'{len(used)}/{len(judged)}' if judged else '—'} | {a_to_b} | "
                  f"{round(statistics.mean(r['avg_chars'] for r in ans)) if ans else '—'} | "
                  f"{fmt_pct(mean_or_none([r['with_numbers'] / r['sentences'] for r in ans if r['sentences']]))} | "
                  f"{fmt_pct(mean_or_none([r['with_reason'] / r['sentences'] for r in ans if r['sentences']]))} | "
                  f"{fmt_pct(cov)} | {sum(r['claims_removed'] or 0 for r in ok)}/{sum(r['claims_checked'] or 0 for r in ok)} | "
                  f"{', '.join(f'{k} ×{v}' for k, v in reasons.items()) or '—'} |")
        print()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")   # Windows consoles default to a code page without Vietnamese
    main(sys.argv[1])
