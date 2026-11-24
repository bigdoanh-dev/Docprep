"""Offline lexical ablation using answer quotes from the existing retrieval evaluation sets."""
import argparse
import json
import math
import re
import unicodedata
import zipfile
from collections import Counter
from pathlib import Path

import yaml


def normalize(text):
    text = unicodedata.normalize("NFKD", text.lower().replace("đ", "d"))
    return " ".join(re.findall(r"\w+", "".join(c for c in text if not unicodedata.combining(c))))


def variants(items, cases, k):
    df = Counter()
    for row in items:
        df.update(row["terms"])
    metrics = {}
    for label, boost in (("body", None), ("with_header", 0.0), ("with_augmentation", 0.03)):
        hits = reciprocal = scored = 0
        for case in cases:
            doc, quote = normalize(case.get("document", "")), normalize(case.get("answer_quote", ""))
            # Comparable positives must be re-grounded on the same text and document,
            # never on passage IDs tied to an old release.
            if len(quote.split()) < 4:
                continue
            gold = {r["id"] for r in items if doc == r["doc"] and f" {quote} " in f" {r['body']} "}
            if not gold:
                continue
            scored += 1
            weights = {w: math.log(1 + (len(items) + 1) / (df[w] + 1))
                       for w in normalize(case["question"]).split() if len(w) > 1}
            norm = sum(weights.values()) or 1
            def coverage(words):
                return sum(v for w, v in weights.items() if w in words) / norm
            ranks = []
            for r in items:
                accepted = r["terms"] if boost is not None else r["body_terms"]
                score = coverage(accepted)
                if score:
                    if boost is not None:
                        score += 0.15 * coverage(r["header_terms"]) + boost * coverage(r["metadata_terms"])
                    ranks.append((-score, r["id"]))
            rank = next((i for i, (_, uid) in enumerate(sorted(ranks)[:k], 1) if uid in gold), None)
            if rank:
                hits += 1
                reciprocal += 1 / rank
        metrics[label] = {"eligible": scored, "hit": hits, f"hit_at_{k}": round(hits / scored, 4) if scored else None,
                          f"mrr_at_{k}": round(reciprocal / scored, 4) if scored else None}
    return metrics


def index(uid, title, body, header, metadata=""):
    body, header, metadata = map(normalize, (body, header, metadata))
    bt, ht = set(body.split()), set(header.split())
    return {"id": uid, "doc": normalize(title), "body": body, "body_terms": bt,
            "header_terms": ht, "terms": bt | ht, "metadata_terms": set(metadata.split())}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive", type=Path)
    p.add_argument("new", type=Path)
    p.add_argument("--cases", type=Path, default=Path(__file__).with_name("silver_set.jsonl"))
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--k", type=int, default=5)
    args = p.parse_args()
    cases = [r for r in map(json.loads, args.cases.read_text(encoding="utf-8").splitlines())
             if r.get("type") == "in_scope" and r.get("question")]
    old, new = [], []
    with zipfile.ZipFile(args.archive) as z:
        for source in yaml.safe_load(z.read("data/sources.yaml")):
            doc_id, title = source["doc_id"], source["title"]
            folder = args.new / doc_id
            name = f"data/derived/{doc_id}/chunks.jsonl"
            if not (folder / "chunks.jsonl").is_file() or name not in z.namelist():
                continue
            for r in map(json.loads, z.read(name).splitlines()):
                old.append(index(r["chunk_id"], title, r["text"], title + " " + " ".join(r["loc"]["section_path"])))
            for r in map(json.loads, (folder / "chunks.jsonl").read_text(encoding="utf-8").splitlines()):
                aug = r["location"]["augmentation"]
                tag_text = " ".join(aug["keywords"] + [q["question"] for q in aug["questions"]])
                new.append(index(r["chunk_id"], title, r["text"], aug["contextual_header"], tag_text))
    def eligible(rows, case):
        doc, quote = normalize(case.get("document", "")), normalize(case.get("answer_quote", ""))
        return len(quote.split()) >= 4 and any(
            r["doc"] == doc and f" {quote} " in f" {r['body']} " for r in rows
        )
    both = [case for case in cases if eligible(old, case) and eligible(new, case)]
    report = {"case_file": args.cases.name, "in_scope_cases": len(cases), "comparable_cases": len(both),
              "old_quote_matches": sum(eligible(old, c) for c in cases),
              "new_quote_matches": sum(eligible(new, c) for c in cases),
              "old_chunks": len(old), "new_chunks": len(new), "old": variants(old, both, args.k),
              "new": variants(new, both, args.k), "method": "Offline lexical scoring. Not runtime search or a clinical validation."}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
