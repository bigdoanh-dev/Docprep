"""Export human-reviewed reference labels, predict independently, and measure agreement."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from uuid import UUID

from app.content import db, service, tagger
from app.gateway import GatewayError
from pydantic import ValidationError


def kappa(pairs, categories=None):
    """Cohen's kappa. Ordered categories opt into quadratic disagreement weights."""
    if not pairs:
        return None
    left, right = (Counter(s) for s in zip(*pairs))
    levels = list(categories) if categories is not None else sorted(left.keys() | right.keys())
    positions = {value: i for i, value in enumerate(levels)}

    def distance(a, b):
        return (positions[a] - positions[b]) ** 2 if categories is not None else int(a != b)

    n = len(pairs)
    observed = sum(distance(a, b) for a, b in pairs) / n
    expected = sum(left[a] * right[b] * distance(a, b) for a in left for b in right) / (n * n)
    return round(1 - observed / expected, 4) if expected else None


def compact(labels):
    issue, = [x["id"] for x in labels["van_de"] if x["primary"]]
    return {"issue": issue, "domains": sorted(x["id"] for x in labels["mien"]),
            "bloom": labels["bloom_ceiling"]["level"]}


def references(conn, revision_ids, taxonomy, pilot=None):
    """Only current effective human decisions count. Synthetic acceptance of source baseline is excluded."""
    rows = conn.execute("""
        select c.id,c.source_chunk_id,c.source_content_hash,c.content_sha256,c.text,c.location,c.kind,
               d.external_doc_id,r.source_availability,s.confirmed_tag_set_id,
               dec.id as decision_id,dec.reviewer_id
        from document_chunk c join source_document_revision r on r.id=c.revision_id
        join source_document d on d.id=r.document_id join chunk_state s on s.chunk_id=c.id
        join chunk_review_decision dec on dec.id=s.classification_decision_id and dec.chunk_id=c.id
        join chunk_review_decision content_dec on content_dec.id=s.content_approval_decision_id
        join chunk_tag_set tags on tags.id=s.confirmed_tag_set_id and tags.chunk_id=c.id
        where c.revision_id=any(%s) and tags.taxonomy_version=%s
          and s.classification_status='classified' and s.content_status='approved'
          and content_dec.policy_version='human-v1' and content_dec.purpose='content' and content_dec.decision='accept'
          and dec.policy_version='human-v1' and dec.purpose='classification' and dec.decision='accept'
        order by d.external_doc_id,c.seq
    """, (revision_ids, taxonomy)).fetchall()
    expected = {(r["doc_id"], r["chunk_id"], r["content_hash"]) for r in pilot["samples"]} if pilot else None
    out = []
    seen = set()
    for row in rows:
        key = row["external_doc_id"], row["source_chunk_id"], row["source_content_hash"]
        if expected is not None and key not in expected:
            continue
        if row["source_content_hash"] in seen:
            continue
        seen.add(row["source_content_hash"])
        out.append({"id": str(row["id"]), "content_sha256": row["content_sha256"], "text": row["text"],
                    "location": row["location"], "kind": row["kind"],
                    "stratum": "ocr" if row["location"].get("image_indices") else "word",
                    "decision_id": str(row["decision_id"]), "reviewer_id": str(row["reviewer_id"]),
                    "gold": compact(service.tag_view(conn, row["confirmed_tag_set_id"]))})
    return out


def _summary(gold_rows, predictions, domains):
    valid = []
    failure = Counter()
    for row in gold_rows:
        chosen = predictions.get(row["id"], {})
        if chosen.get("content_sha256") != row["content_sha256"]:
            failure["missing_or_hash_mismatch"] += 1
        elif chosen.get("prediction") is None:
            failure[chosen.get("status", "abstain")] += 1
        else:
            valid.append((row["gold"], chosen["prediction"]))
    n = len(valid)
    raw_total = len(gold_rows)
    positions = {level: i for i, level in enumerate(service.BLOOM)}
    issue_errors = Counter((a["issue"], b["issue"]) for a, b in valid if a["issue"] != b["issue"])
    per_domain = {}
    tp = fp = fn = 0
    for domain in domains:
        pairs = [(domain in a["domains"], domain in b["domains"]) for a, b in valid]
        tp += sum(a and b for a, b in pairs)
        fp += sum(not a and b for a, b in pairs)
        fn += sum(a and not b for a, b in pairs)
        positives = sum(a for a, _ in pairs)
        per_domain[domain] = {"gold_positive": positives, "predicted_positive": sum(b for _, b in pairs),
                              "kappa": kappa(pairs) if 0 < positives < n else None}
    return {
        "samples": raw_total, "scored": n, "coverage": n / raw_total if raw_total else None,
        "excluded": dict(failure),
        "issue_kappa": kappa([(a["issue"], b["issue"]) for a, b in valid]),
        "issue_exact": sum(a["issue"] == b["issue"] for a, b in valid) / n if n else None,
        "issue_confusions": [{"reviewer": a, "model": b, "count": count}
                             for (a, b), count in issue_errors.most_common()],
        "bloom_quadratic_kappa": kappa([(a["bloom"], b["bloom"]) for a, b in valid], service.BLOOM),
        "bloom_exact": sum(a["bloom"] == b["bloom"] for a, b in valid) / n if n else None,
        "bloom_gap_at_least_two": sum(abs(positions[a["bloom"]] - positions[b["bloom"]]) >= 2
                                      for a, b in valid) / n if n else None,
        "domain_set_exact": sum(a["domains"] == b["domains"] for a, b in valid) / n if n else None,
        "domain_micro_f1": 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else None,
        "domain_kappa": per_domain,
    }


def read(path):
    return path.read_text(encoding="utf-8")


def write(path, value):
    with path.open("x", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        file.write("\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest="action", required=True)
    export = commands.add_parser("export-gold")
    export.add_argument("--revision", type=UUID, action="append", required=True)
    export.add_argument("--taxonomy", required=True)
    export.add_argument("--pilot", type=Path)
    predict = commands.add_parser("predict")
    predict.add_argument("--gold", required=True, type=Path)
    predict.add_argument("--provider", choices=("google", "ollama"), required=True)
    predict.add_argument("--limit", type=int, default=20)
    predict.set_defaults(fallback_local=False)
    score = commands.add_parser("score")
    score.add_argument("--gold", required=True, type=Path)
    score.add_argument("--predictions", required=True, type=Path)
    for cmd in (export, predict, score):
        cmd.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    if args.output.exists():
        p.error("Use a new output file")
    if args.action == "export-gold":
        with db.connect() as conn:
            snapshot = conn.execute("select payload from taxonomy_snapshot where version=%s", (args.taxonomy,)).fetchone()
            if not snapshot:
                p.error("Taxonomy not found")
            pilot = json.loads(read(args.pilot)) if args.pilot else None
            rows = references(conn, args.revision, args.taxonomy, pilot)
        if not rows:
            p.error("No chunks with human-reviewed classification and content in the selected revisions")
        write(args.output, {"taxonomy_version": args.taxonomy, "taxonomy": snapshot["payload"], "rows": rows})
        return
    raw = read(args.gold)
    gold = json.loads(raw)
    gold_hash = hashlib.sha256(raw.encode()).hexdigest()
    if not gold["rows"] or not all(r.get("decision_id") and r.get("reviewer_id") for r in gold["rows"]):
        p.error("Use the nonempty result from export-gold")
    if args.action == "predict":
        if not 1 <= args.limit <= 100:
            p.error("Limit must be in 1..100")
        gateway, = tagger._gateways(args)
        outputs = []
        for row in gold["rows"][:args.limit]:
            result = {k: row[k] for k in ("id", "content_sha256")}
            try:
                # Pass only fields needed for inference. Reviewer labels and provenance remain outside the prompt.
                prediction = tagger.predict(gateway, {k: row[k] for k in ("text", "location", "kind")}, gold["taxonomy"])
                result.update(prediction=compact(prediction[0]) if prediction else None,
                              model=prediction[1]["model"] if prediction else None,
                              status="predicted" if prediction else "abstain")
            except (GatewayError, ValidationError, ValueError):
                result.update(prediction=None, status="model_error_or_invalid")
            outputs.append(result)
        write(args.output, {"gold_sha256": gold_hash, "provider": args.provider, "rows": outputs})
        return
    result = json.loads(read(args.predictions))
    if result["gold_sha256"] != gold_hash:
        p.error("Predictions were not generated for this reference snapshot")
    predictions = {r["id"]: r for r in result["rows"]}
    domains = [s["id"] for group in gold["taxonomy"]["mien"] for s in group["sub"]]
    report = {part: _summary([r for r in gold["rows"] if part == "all" or part == r["stratum"]],
                             predictions, domains) for part in ("all", "word", "ocr")}
    write(args.output, {"gold_sha256": gold_hash, "provider": result["provider"], "results": report})


if __name__ == "__main__":
    main()
