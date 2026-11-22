"""Proposes a prerequisite map over the competency tree (competency_node), by two models.

Each model sees every competency (code, group, name) and lists, for each, the competencies a learner
must already master to learn it. An edge is kept only when both models propose it, and never when
it would make a cycle. Output: proposals.json (both models' raw answers) and the kept map, written to
config/prerequisites.yaml, which migration 0021 loads into competency_node.prerequisite_codes.

MACHINE-MADE, NOT REVIEWED (decided 2026-11-23). The tree is coarse (core issues, not concepts), so
"độ nhạy/độ đặc hiệu → sàng lọc" lives inside FND (Khái niệm cơ bản), not as two nodes.
"""
import json
from pathlib import Path

from app.db import connect
from common import ask_json
from rerank_eval import make

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "config" / "prerequisites.yaml"
SYSTEM = """You design a prerequisite map for a Vietnamese preventive-medicine (Y học dự phòng) curriculum for primary care.
The user lists the competencies (code | group | name). For each competency, list the OTHER competencies from the list that a learner must already understand to learn this one well: knowledge it directly builds on (for example basic epidemiology concepts before outbreak control; fever before fever with rash).
Rules: only direct prerequisites, at most 3 per competency, only codes from the list, no group codes (G1...), none for a competency that builds on nothing. Being related or in the same group is not enough.
Output JSON only: {"prerequisites": {"<code>": ["<code>", ...], ...}}"""


def acyclic(edges: dict[str, list[str]]) -> dict[str, list[str]]:
    kept: dict[str, list[str]] = {}

    def reaches(a: str, b: str, seen=None) -> bool:
        seen = seen or set()
        if a == b:
            return True
        seen.add(a)
        return any(reaches(n, b, seen) for n in kept.get(a, []) if n not in seen)

    for code in sorted(edges):
        for pre in edges[code]:
            if not reaches(pre, code):
                kept.setdefault(code, []).append(pre)
    return kept


def main() -> int:
    with connect() as conn:
        nodes = conn.execute("select code, parent_code, name from competency_node where level = 2 or code = 'FND' order by code").fetchall()
    codes = {n["code"] for n in nodes}
    listing = "\n".join(f"{n['code']} | {n['parent_code'] or '-'} | {n['name']}" for n in nodes)
    raw, maps = {}, []
    for name in ("anthropic", "google"):
        data = ask_json(make(name), SYSTEM, listing, "prereq-map-v1") or {}
        raw[name] = data
        got = data.get("prerequisites") if isinstance(data.get("prerequisites"), dict) else {}
        maps.append({k: {v for v in vs if v in codes and v != k} for k, vs in got.items() if k in codes and isinstance(vs, list)})
    both = {c: sorted(maps[0].get(c, set()) & maps[1].get(c, set())) for c in codes}
    kept = acyclic({c: v for c, v in both.items() if v})
    (HERE / "proposals.json").write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    names = {n["code"]: n["name"] for n in nodes}
    lines = ["# Prerequisite map over competency_node (level 2). MACHINE-MADE, NOT REVIEWED:",
             "# kept only where Claude Haiku and Gemini Flash-Lite both proposed the edge",
             "# (experiments/prerequisites/propose.py, 2026-11-23). Loaded by migration 0021.", ""]
    for c in sorted(kept):
        lines.append(f"{c}: [{', '.join(kept[c])}]   # {names[c]} ← " + "; ".join(names[p] for p in kept[c]))
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    n_a, n_g = sum(len(v) for v in maps[0].values()), sum(len(v) for v in maps[1].values())
    print(f"edges: haiku {n_a}, gemini {n_g}, both {sum(len(v) for v in both.values())}, kept {sum(len(v) for v in kept.values())}")
    print(OUT.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
