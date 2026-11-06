"""Reports: blueprint coverage (P0 T19) and tagging eval against human tags (P0 T18)."""

import sqlite3
from collections import Counter

from yhdp.blueprint import Blueprint, load_blueprint
from yhdp.ingest.tag import BLOOM, MCQ_ELIGIBLE
from yhdp.store.tags import effective_tags, tag_pairs


def coverage(con: sqlite3.Connection, bp: Blueprint | None = None) -> str:
    """Vấn đề × document table of primary-tagged chunks, with MCQ-eligible counts and gaps."""
    bp = bp or load_blueprint()
    tags = effective_tags(con)
    docs = sorted({t["doc_id"] for t in tags.values()})
    primary: Counter = Counter()
    eligible: Counter = Counter()
    mentioned: Counter = Counter()
    human = sum(t["source"] == "human" for t in tags.values())
    for t in tags.values():
        rec = t["record"]
        vd = rec["blueprint"]["van_de"]
        p = next(v["id"] for v in vd if v["primary"])
        primary[(p, t["doc_id"])] += 1
        eligible[p] += rec["mcq_eligible"]
        for v in vd:
            mentioned[v["id"]] += 1
    total = con.execute("SELECT count(*) FROM chunks").fetchone()[0]
    lines = ["# Blueprint coverage", "",
             (f"{len(tags)}/{total} chunks tagged ({human} by reviewers, the rest by the model). "
             "Cells count chunks whose **primary** vấn đề is that row; *MCQ* counts those at "
             "Bloom ≥ Áp dụng; *any* also counts secondary mentions."), ""]
    de_muc = {d.id: d for d in bp.de_muc}
    head = "| Vấn đề | " + " | ".join(docs) + " | Total | MCQ | Any |"
    sep = "|---|" + "---:|" * (len(docs) + 3)
    gaps = []
    for d in bp.de_muc:
        lines += [f"## Đề mục {d.id} ({d.weight[0]}–{d.weight[1]}% of the exam): {d.name}", "",
                  head, sep]
        for v in (v for v in bp.van_de if v.de_muc == d.id):
            row = [primary[(v.id, doc)] for doc in docs]
            if not sum(row):
                gaps.append(v)
            cells = " | ".join(str(n) if n else "·" for n in row)
            lines.append(f"| {v.id}. {v.name} | {cells} | **{sum(row)}** | {eligible[v.id]} | "
                         f"{mentioned[v.id]} |")
        lines.append("")
    lines += [f"## Gaps: {len(gaps)} of {len(bp.van_de)} vấn đề have no primary chunk", ""]
    lines += [f"- {v.id}. {v.name} (đề mục {v.de_muc}: {de_muc[v.de_muc].name})" for v in gaps]
    return "\n".join(lines) + "\n"


def cohen_kappa(a: list[str], b: list[str], labels: tuple[str, ...]) -> float:
    n = len(a)
    if not n:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[label] * cb[label] for label in labels) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def _primary(rec: dict) -> int:
    return next(v["id"] for v in rec["blueprint"]["van_de"] if v["primary"])


def _top_mien(rec: dict) -> str:
    return max(rec["blueprint"]["mien"], key=lambda m: m["conf"])["id"]


def tag_eval(con: sqlite3.Connection) -> str:
    """Model (auto) tags scored against reviewer (human) tags on the same chunk content."""
    pairs = tag_pairs(con)
    lines = ["# P0 tagging eval", ""]
    if not pairs:
        return "\n".join(lines + ["No chunk has both a model tag and a reviewer tag yet."]) + "\n"

    def block(title: str, subset: list) -> list[str]:
        n = len(subset)
        if not n:
            return [f"### {title}: no chunks", ""]
        vd = sum(_primary(a) == _primary(h) for _, a, h, _ in subset)
        tp = fp = fn = 0
        for _, a, h, _ in subset:
            sa = {v["id"] for v in a["blueprint"]["van_de"]}
            sh = {v["id"] for v in h["blueprint"]["van_de"]}
            tp, fp, fn = tp + len(sa & sh), fp + len(sa - sh), fn + len(sh - sa)
        f1 = 2 * tp / (2 * tp + fp + fn) if tp else 0.0
        mien = sum(_top_mien(a) == _top_mien(h) for _, a, h, _ in subset)
        ba = [a["bloom_ceiling"]["level"] for _, a, _, _ in subset]
        bh = [h["bloom_ceiling"]["level"] for _, _, h, _ in subset]
        mcq = sum((x in MCQ_ELIGIBLE) == (y in MCQ_ELIGIBLE) for x, y in zip(ba, bh, strict=True))
        return [f"### {title} (n = {n})", "",
                "| Metric | Value | P0 target |", "|---|---:|---:|",
                f"| Primary vấn đề accuracy | {vd / n:.0%} | ≥ 85% |",
                f"| Vấn đề set F1 | {f1:.2f} | |",
                f"| Top miền accuracy | {mien / n:.0%} | |",
                f"| Bloom Cohen's κ | {cohen_kappa(ba, bh, BLOOM):.2f} | ≥ 0.6 |",
                f"| MCQ-eligibility agreement | {mcq / n:.0%} | |", ""]

    lines += block("All reviewed chunks", pairs)
    lines += block("Audit sample (model was confident, unqueued)",
                   [p for p in pairs if p[3] in ("audit", "unqueued")])
    for doc in sorted({cid.split("#")[0] for cid, *_ in pairs}):
        lines += block(f"Document {doc}", [p for p in pairs if p[0].startswith(doc + "#")])
    confusions = Counter((_primary(a), _primary(h)) for _, a, h, _ in pairs
                         if _primary(a) != _primary(h))
    bloom_conf = Counter((a["bloom_ceiling"]["level"], h["bloom_ceiling"]["level"])
                         for _, a, h, _ in pairs
                         if a["bloom_ceiling"]["level"] != h["bloom_ceiling"]["level"])
    lines += ["## Most common corrections", "", "Vấn đề (model → reviewer):", ""]
    lines += [f"- {a} → {h}: {n}" for (a, h), n in confusions.most_common(10)] or ["- none"]
    lines += ["", "Bloom (model → reviewer):", ""]
    lines += [f"- {a} → {h}: {n}" for (a, h), n in bloom_conf.most_common(10)] or ["- none"]
    return "\n".join(lines) + "\n"
