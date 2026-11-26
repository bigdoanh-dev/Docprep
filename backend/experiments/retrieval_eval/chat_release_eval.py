"""Compare corpus releases using real Chat API turns and read-only runtime traces."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
from time import monotonic
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
import psycopg
from psycopg.rows import dict_row

from app.repo import embeddings


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


def preflight(conn, version, channel, embedding_model, embedding_revision, gold):
    active = conn.execute("""select r.id,r.version,r.status from corpus_activation a
                             join corpus_release r on r.id=a.release_id where a.channel=%s""", (channel,)).fetchone()
    if not active or active["version"] != version or active["status"] != "ready":
        raise ValueError("Expected release is not active and ready on the evaluation channel")
    members = {r["passage_id"] for r in conn.execute(
        "select passage_id from corpus_release_member where release_id=%s", (active["id"],),
    )}
    if not members or gold - members:
        raise ValueError("Empty corpus or reference passages do not belong to this release")
    if not embeddings.ready(conn, embedding_model, embedding_revision, version):
        raise ValueError("The requested embedding index is not ready")


def send_turn(client, question, module_id):
    response = client.post("chat/sessions", json={"module_id": module_id})
    response.raise_for_status()
    session = response.json()["id"]
    with client.stream("POST", f"chat/sessions/{session}/messages", json={"text": question, "mode": "auto"},
                       headers={"Idempotency-Key": str(uuid4())}) as response:
        response.raise_for_status()
        if not response.headers.get("content-type", "").startswith("text/event-stream"):
            raise ValueError("Chat response is not SSE")
        event, payload = None, []
        for line in response.iter_lines():
            if line.startswith("event:"):
                event = line.partition(":")[2].strip()
            elif line.startswith("data:"):
                payload.append(line.partition(":")[2].lstrip())
            elif not line:
                if event == "final" and payload:
                    return session, json.loads("\n".join(payload))
                event, payload = None, []
    raise ValueError("Chat response had no final event")


def persisted(conn, final, session, version):
    row = conn.execute("""select m.corpus_version,m.citations,m.trace,m.model_version,m.prompt_version,
                                 m.retrieved_passage_ids,m.latency_ms,
                                 (select count(*) from ai_model_call c where c.turn_id=t.id) as model_calls
                          from ai_turn t join chat_message m on m.ai_turn_id=t.id
                          where t.id=%s and m.id=%s and m.session_id=%s and t.status='completed'""",
                       (UUID(final["turn_id"]), final["message_id"], session)).fetchone()
    if not row or row["corpus_version"] != version:
        raise ValueError("Chat did not persist a result from the expected release")
    trace = next((step["_retrieval_eval"] for step in (row["trace"] or []) if "_retrieval_eval" in step), None)
    return row, trace


def score_case(trace, citations, state, expected):
    gold = set(expected.get("passages", []))
    cited = [item["passage_id"] for item in citations]
    return {
        "before_hit_at_5": bool(set(trace["before_rerank"][:5]) & gold) if gold and trace else None,
        "after_hit_at_5": bool(set(trace["after_rerank"][:5]) & gold)
        if gold and trace and not trace.get("rerank_failure") else None,
        "candidate_pool_hit": bool(set(trace["before_rerank"]) & gold) if gold and trace else None,
        "citation_hit": bool(set(cited) & gold) if gold else None,
        "citation_precision": sum(pid in gold for pid in cited) / len(cited) if gold and cited else None,
        "state_match": state in expected["states"],
    }


def report(rows):
    metrics = {}
    for name in ("candidate_pool_hit", "before_hit_at_5", "after_hit_at_5", "citation_hit",
                 "citation_precision", "state_match"):
        values = [r["metrics"][name] for r in rows if r.get("metrics", {}).get(name) is not None]
        metrics[name] = {"scored": len(values), "value": round(sum(values) / len(values), 4) if values else None}
    timing = sorted(r["wall_ms"] for r in rows if "wall_ms" in r)
    return {"cases": len(rows), "statuses": dict(Counter(r["status"] for r in rows)), "metrics": metrics,
            "rerank_gated": sum(bool((r.get("trace") or {}).get("rerank_gated")) for r in rows),
            "wall_ms_median": timing[len(timing) // 2] if timing else None}


def run(args):
    api = urlsplit(args.api)
    if api.username or api.password or api.query or api.fragment or api.scheme not in ("http", "https") or (
        api.scheme == "http" and api.hostname not in {"127.0.0.1", "::1", "localhost"}
    ):
        raise ValueError("Use an HTTPS API or local HTTP for the evaluation learner token")
    raw = args.cases.read_bytes()
    cases = json.loads(raw)
    if not cases or len({row["id"] for row in cases}) != len(cases):
        raise ValueError("Use a nonempty case list with unique IDs")
    cases_for_variant = [row for row in cases if args.variant in row["expected"]]
    if not cases_for_variant:
        raise ValueError("No cases for this variant")
    gold = set()
    for case in cases_for_variant:
        expected = case["expected"][args.variant]
        if not expected.get("states") or ("answered" in expected["states"] and not expected.get("passages")):
            raise ValueError("Each case needs expected states and every answerable case needs reference passages")
        gold.update(expected.get("passages", []))
    target = args.api.rstrip("/") + "/"
    rows = []
    with psycopg.connect(os.environ["CHAT_EVAL_DATABASE_URL"], row_factory=dict_row) as conn:
        conn.read_only = True
        preflight(conn, args.version, args.channel, args.embedding_model, args.embedding_revision, gold)
        conn.rollback()
        with httpx.Client(base_url=target, trust_env=False, timeout=120,
                          headers={"Authorization": "Bearer " + os.environ["CHAT_EVAL_TOKEN"]}) as client:
            for case in cases_for_variant:
                expected = case["expected"][args.variant]
                row = {"id": case["id"], "group": case.get("group", "general"), "status": "error"}
                started = monotonic()
                try:
                    session, event = send_turn(client, case["question"], case.get("module_id"))
                    row.update(turn_id=event.get("turn_id"), answer_state=event.get("state"))
                    if event.get("turn_status") != "completed":
                        row.update(status="turn_failed", error_code=(event.get("error") or {}).get("code"))
                    else:
                        message, trace = persisted(conn, event, session, args.version)
                        if trace and (trace["embedding_model"], trace["embedding_revision"]) != (
                            args.embedding_model, args.embedding_revision
                        ):
                            raise ValueError("Chat used a different embedding than the one evaluated")
                        if trace and not trace["rerank"]["enabled"]:
                            raise ValueError("Reranking is off")
                        status = "hybrid_not_observed" if not trace else (
                            "rerank_fallback" if trace.get("rerank_failure") else "complete"
                        )
                        row.update(status=status,
                                   trace=trace, cited_ids=[c["passage_id"] for c in message["citations"] or []],
                                   model=message["model_version"], prompt=message["prompt_version"],
                                   model_calls=message["model_calls"],
                                   metrics=score_case(trace, message["citations"] or [], event.get("state"), expected))
                except httpx.HTTPStatusError as exc:
                    row.update(status="http_error", http_status=exc.response.status_code)
                except (httpx.RequestError, ValueError) as exc:
                    row.update(status="invalid_run", error=type(exc).__name__)
                finally:
                    conn.rollback()
                row["wall_ms"] = round((monotonic() - started) * 1000)
                rows.append(row)
    return {"variant": args.variant, "release": args.version, "case_sha256": hashlib.sha256(raw).hexdigest(),
            "summary": report(rows), "rows": rows}


def compare(baseline, candidate):
    if baseline["case_sha256"] != candidate["case_sha256"] or baseline["release"] == candidate["release"]:
        raise ValueError("Comparison needs the same case set and distinct releases")
    if (baseline["variant"], candidate["variant"]) != ("baseline", "candidate"):
        raise ValueError("Expected a baseline run and a candidate run")
    a, b = ({r["id"]: r for r in result["rows"]} for result in (baseline, candidate))
    paired = sorted(a.keys() & b.keys())
    configuration_keys = ("provider", "embedding_model", "embedding_revision", "rerank", "rerank_model")
    mismatch = []
    eligible = []
    for case in paired:
        x, y = a[case], b[case]
        if x["status"] != "complete" or y["status"] != "complete":
            continue
        tx, ty = x["trace"], y["trace"]
        if any(tx[k] != ty[k] for k in configuration_keys if k != "rerank_model") or (
            tx["rerank_model"] and ty["rerank_model"] and tx["rerank_model"] != ty["rerank_model"]
        ) or (x["model"] and y["model"] and (x["model"], x["prompt"]) != (y["model"], y["prompt"])):
            mismatch.append(case)
        else:
            eligible.append(case)
    return {"paired_cases": len(paired), "paired_with_compatible_hybrid": len(eligible),
            "configuration_mismatches": mismatch,
            "baseline": report([a[k] for k in eligible]), "candidate": report([b[k] for k in eligible]),
            "baseline_all": report(list(a.values())), "candidate_all": report(list(b.values())),
            "candidate_only": report([b[k] for k in sorted(b.keys() - a.keys())])}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    go = sub.add_parser("run")
    go.add_argument("--api", required=True, help="API base ending in /api/v1")
    go.add_argument("--channel", required=True)
    go.add_argument("--version", required=True)
    go.add_argument("--embedding-model", required=True)
    go.add_argument("--embedding-revision", required=True)
    go.add_argument("--variant", choices=("baseline", "candidate"), required=True)
    go.add_argument("--cases", type=Path, required=True)
    join = sub.add_parser("compare")
    join.add_argument("--baseline", type=Path, required=True)
    join.add_argument("--candidate", type=Path, required=True)
    for cmd in (go, join):
        cmd.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        p.error("Use a new output file")
    answer = run(args) if args.action == "run" else compare(read(args.baseline), read(args.candidate))
    write(args.output, answer)


if __name__ == "__main__":
    main()
