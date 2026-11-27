"""Label pending chunks through a chat app (Gemini/ChatGPT web) instead of the API, in batches.

export  writes batch-NNN.txt (prompt + chunks, ready to paste) and a manifest with the chunk identity.
import  reads the answers saved by the operator, validates every label against the taxonomy exactly as the
        API tagger does, and stores them as proposals. Nothing is approved here: chunks stay unclassified.

Only the public source corpus leaves the system; no learner data is involved.
"""
import argparse
import getpass
import json
import os
import re
from collections import Counter
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from app.errors import ApiError

from . import auth, db, importer, service, tagger

MANIFEST = "manifest.json"
BATCH_RULES = """

# CÁCH TRẢ LỜI CHO LÔ NÀY
Bên dưới là một mảng JSON các đoạn cần gắn nhãn; mỗi đoạn có "id", "section_path", "kind", "text".
Gắn nhãn TỪNG đoạn một cách độc lập theo hướng dẫn ở trên. Trả về DUY NHẤT một mảng JSON đặt trong
một khối ```json, đủ tất cả "id" theo đúng thứ tự, không bỏ sót, không thêm đoạn mới. Mỗi phần tử:
{"id": "c01", "primary_issue": 22, "secondary_issues": [], "domains": ["2.3"], "bloom": "Áp dụng",
 "content_type": "chẩn_đoán", "population": [], "rationale": "..."}
Đoạn thiếu căn cứ để phân loại: {"id": "c07", "abstain": true}.
Giá trị cho phép — bloom: {bloom}; content_type: {types}; population: {populations}.

# CÁC ĐOẠN
"""


def _short(i):
    return f"c{i:02d}"


def export(conn, revisions, taxonomy, version, out, batch_size):
    rows = [r for r in tagger.pending_rows(conn, revisions) if tagger.needs_model(r)]
    out.mkdir(parents=True, exist_ok=False)
    rules = BATCH_RULES.replace("{bloom}", ", ".join(service.BLOOM)).replace(
        "{types}", ", ".join(service.TYPES)).replace("{populations}", ", ".join(service.POPULATIONS))
    prompt = tagger.system_prompt(taxonomy) + rules
    manifest = {"taxonomy_version": version, "prompt_version": tagger.PROMPT_VERSION,
                "revisions": [str(r) for r in revisions], "batches": {}}
    for start in range(0, len(rows), batch_size):
        name = f"batch-{start // batch_size + 1:03d}"
        batch = rows[start:start + batch_size]
        chunks = [{"id": _short(i), "section_path": " › ".join(r["location"].get("section_path", [])),
                   "kind": r["kind"], "text": r["text"]} for i, r in enumerate(batch, 1)]
        (out / f"{name}.txt").write_text(prompt + json.dumps(chunks, ensure_ascii=False, indent=1) + "\n",
                                         encoding="utf-8")
        manifest["batches"][name] = {_short(i): {"chunk_id": str(r["id"]), "row_version": r["row_version"],
                                                 "content_sha256": r["content_sha256"]}
                                     for i, r in enumerate(batch, 1)}
    (out / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"chunks": len(rows), "batches": len(manifest["batches"]), "folder": str(out)}


def extract_answers(text):
    """The JSON array from a chat answer: a ```json block if present, else the outermost [...]."""
    fenced = re.findall(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.S)
    candidate = fenced[-1] if fenced else text[text.find("["):text.rfind("]") + 1]
    answers = json.loads(candidate)
    if not isinstance(answers, list):
        raise ValueError("Answer is not a JSON array")
    return answers


def import_batch(conn, actor, manifest, name, text, taxonomy, apply, source):
    """Validate one batch answer and (with apply) save proposals. Returns per-id outcomes."""
    expected = manifest["batches"][name]
    outcomes = {}
    try:
        answers = extract_answers(text)
    except (ValueError, json.JSONDecodeError) as error:
        return {sid: "answer_not_json" for sid in expected}, str(error)
    seen = Counter(a.get("id") for a in answers if isinstance(a, dict))
    for answer in answers:
        sid = answer.get("id") if isinstance(answer, dict) else None
        if sid not in expected or seen[sid] > 1:
            continue  # unknown or duplicated ids are reported below as missing/duplicate
        body = {k: v for k, v in answer.items() if k != "id"}
        try:
            labels = tagger.parse_prediction(body, taxonomy)
        except (ValidationError, ValueError, TypeError):
            outcomes[sid] = "invalid_label"
            continue
        if labels is None:
            outcomes[sid] = "abstain"
            continue
        ref = expected[sid]
        row = conn.execute("""select c.id, c.content_sha256, s.row_version from document_chunk c
                              join chunk_state s on s.chunk_id=c.id where c.id=%s""", (ref["chunk_id"],)).fetchone()
        if not row or row["content_sha256"] != ref["content_sha256"] or row["row_version"] != ref["row_version"]:
            outcomes[sid] = "chunk_changed_since_export"
            continue
        try:
            service.validate_tags(conn, labels, manifest["taxonomy_version"])
        except (ApiError, ValueError, KeyError):
            outcomes[sid] = "invalid_label"
            continue
        provenance = {"strategy": "manual_chat", "model": source, "prompt_version": manifest["prompt_version"],
                      "batch": name}
        if not apply:
            outcomes[sid] = "valid"
        elif tagger.save_proposal(conn, actor, row, manifest["taxonomy_version"], labels, provenance):
            outcomes[sid] = "proposed"
        else:
            outcomes[sid] = "already_changed"
    for sid in expected:
        if seen[sid] > 1:
            outcomes[sid] = "duplicate_id"
        outcomes.setdefault(sid, "missing_in_answer")
    return outcomes, None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("export")
    p.add_argument("package", type=Path, help="data.zip (taxonomy)")
    p.add_argument("--revision", type=UUID, action="append", required=True)
    p.add_argument("--taxonomy", required=True)
    p.add_argument("--output", type=Path, required=True, help="New folder for batch files")
    p.add_argument("--batch-size", type=int, default=40)
    p = sub.add_parser("import")
    p.add_argument("package", type=Path)
    p.add_argument("--export", type=Path, required=True, help="Folder created by export")
    p.add_argument("--answers", type=Path, required=True, help="Folder with batch-NNN.txt/.json answers")
    p.add_argument("--source", required=True, help='Model as used, e.g. "gemini-pro (gemini.google.com)"')
    p.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    package = importer.Package(args.package)
    try:
        taxonomy = package.taxonomy
    finally:
        package.close()
    if args.command == "export":
        if not 5 <= args.batch_size <= 80:
            parser.error("Batch size must be in 5..80")
        with db.connect() as conn:
            db.check_ready(conn)
            taxonomy = tagger.snapshot_payload(conn, args.taxonomy, taxonomy)
            if taxonomy is None:
                parser.error("Select a taxonomy snapshot that is the ZIP taxonomy or an extension of it")
            print(json.dumps(export(conn, args.revision, taxonomy, args.taxonomy, args.output, args.batch_size),
                             ensure_ascii=False))
        return
    manifest = json.loads((args.export / MANIFEST).read_text(encoding="utf-8"))
    if manifest["prompt_version"] != tagger.PROMPT_VERSION:
        parser.error("Export was made with another prompt version; export again")
    report, totals = {}, Counter()
    with db.connect() as conn:
        db.check_ready(conn)
        user = auth.password_user(conn, os.environ.get("CONTENT_USERNAME") or input("Content username: "),
                                  os.environ.get("CONTENT_PASSWORD") or getpass.getpass("Content password: "))
        user["roles"] = auth.roles(conn, user["id"])
        auth.require(user, "editor")
        taxonomy = tagger.snapshot_payload(conn, manifest["taxonomy_version"], taxonomy)
        if taxonomy is None:
            parser.error("Taxonomy version of the export is missing or does not match the ZIP")
    for name in sorted(manifest["batches"]):
        files = [f for f in (args.answers / f"{name}.json", args.answers / f"{name}.txt") if f.is_file()]
        if not files:
            report[name] = {"status": "no_answer_file"}
            continue
        with db.connect() as conn:
            outcomes, error = import_batch(conn, user["id"], manifest, name, files[0].read_text(encoding="utf-8"),
                                           taxonomy, args.apply, args.source)
        counts = Counter(outcomes.values())
        totals.update(counts)
        report[name] = {"counts": dict(counts), "error": error,
                        "redo": sorted(s for s, o in outcomes.items() if o not in ("proposed", "valid", "abstain"))}
    result = {"apply": args.apply, "source": args.source, "totals": dict(totals), "batches": report}
    (args.answers / ("import-report.json" if args.apply else "check-report.json")).write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"apply": args.apply, "totals": dict(totals)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
