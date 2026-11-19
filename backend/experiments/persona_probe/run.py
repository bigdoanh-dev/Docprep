"""Persona probe: does the chat pipeline lay out its answer for the learner, keep every key point,
and stay grounded?

Dev/test only, synthetic learners (profiles.yaml). Each turn runs the real two-stage pipeline:
stage A (retrieval, grounded answer, post-check: never sees the learner) and, for a profile with a
policy, stage B (app/chat/adapt.py: layout + entailment and coverage checks, falling back to stage A).
Only the Signals come from profiles.yaml instead of the mastery table (Chat may not write Business tables).

Per question: retrieval once, then `--repeats` turns per condition:
  C0         no learner (today's answer)
  <profile>  the same passages with that profile's policy (a profile without a policy is C0)
Coverage judge (LLM): for each turn stage B laid out, which key points of the same turn's stage A
answer does the layout keep? (Stage A picks different claims run to run, so comparing with another
run's answer would blame stage B for stage A's variation.) Each fallback records its reason.
"""
import argparse
import dataclasses
import json
import re
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

from app.chat.personalize import Signals, policy_for
from app.chat.pipeline import MODEL_DOWN_NOTICE, generate, parse_model_json, prepare_answer
from app.chat.normalise import normalise
from app.db import connect
from app.repo import content, corpus, embeddings
from app.ollama_gateway import OllamaConfig

MAX_MODEL_DOWN_IN_A_ROW = 3   # quota or outage: stop instead of recording failures as results


def make_gateway(provider: str):
    if provider == "anthropic":   # model and effort from YHDP_ANTHROPIC_MODEL / YHDP_ANTHROPIC_EFFORT
        from app.anthropic_gateway import AnthropicConfig, HostedGateway
        return HostedGateway(OllamaConfig.load(), AnthropicConfig.load())
    from app.google_gateway import GoogleConfig, GoogleGateway
    return GoogleGateway(OllamaConfig.load(), GoogleConfig.load())

HERE = Path(__file__).resolve().parent
NUMBER = re.compile(r"\d")
REASON = re.compile(r"\b(vì|do|nên|nếu|khi|để|nhằm|trường hợp|điều kiện)\b", re.IGNORECASE)
JUDGE_SYSTEM = """You compare two Vietnamese answers to the same study question.
First list the key points of the REFERENCE answer: each separate fact that helps answer the question
(at most 8, one short line each). Then, for each key point, decide whether the CANDIDATE answer states
the same fact, in any wording. A point stated only partly, or with a different number, is not covered.
Output JSON only: {"points": [{"point": "<key point>", "covered": true | false}]}"""


def signals_of(profile: dict, topic: str) -> Signals:
    b = profile["business"]
    bloom = b.get("bloom_accuracy") or {}
    recall = [bloom[k] for k in ("nho", "hieu") if k in bloom]
    applied = [bloom[k] for k in ("ap_dung", "phan_tich") if k in bloom]
    return Signals(b.get("mastery", {}).get(topic), b.get("n_responses", 0),
                   statistics.mean(recall) if recall else None, statistics.mean(applied) if applied else None)


def hybrid(conn, gw, text: str):
    """Retrieval as the chat worker does it for a real provider: bge-m3 vector + full text, fused by RRF."""
    vector = gw.embed([text])
    return embeddings.search(conn, normalise(text, content.glossary(conn)), vector, corpus.selected(conn))


def claims_of(text: str) -> list[str]:
    return [c.strip() for c in re.split(r"\s*(?:\[\d+\])+\s*", text) if c.strip()]


def judge(gw, question: str, reference: str, candidate: str) -> dict | None:
    user = f"Question: {question}\n\nREFERENCE:\n{reference}\n\nCANDIDATE:\n{candidate}"
    try:
        data = parse_model_json(gw.complete("check", JUDGE_SYSTEM, [{"role": "user", "content": user}],
                                            "judge-coverage-v1").text)
    except Exception as e:
        return {"error": repr(e)}
    points = data.get("points") if isinstance(data, dict) else None
    if not isinstance(points, list) or not points:
        return None
    covered = sum(1 for p in points if isinstance(p, dict) and p.get("covered") is True)
    return {"covered": covered, "total": len(points), "coverage": covered / len(points),
            "missing": [p.get("point") for p in points if isinstance(p, dict) and p.get("covered") is not True]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "out"))
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--pause", type=float, default=4.0, help="seconds between turns (free-tier rate limit)")
    ap.add_argument("--only", nargs="*", help="question ids to run")
    ap.add_argument("--provider", choices=["google", "anthropic"], default="google")
    args = ap.parse_args()

    profiles = yaml.safe_load((HERE / "profiles.yaml").read_text(encoding="utf-8"))["profiles"]
    questions = yaml.safe_load((HERE / "questions.yaml").read_text(encoding="utf-8"))["questions"]
    if args.only:
        questions = [q for q in questions if q["id"] in args.only]
    out = Path(args.out) / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True)
    gw = make_gateway(args.provider)
    down_in_a_row = 0

    results = out / "results.jsonl"

    def save(new):   # after every question, so a stopped run keeps what it finished
        with results.open("a", encoding="utf-8") as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in new)

    with connect() as conn:
        for q in questions:
            prepared = [v for k, v in prepare_answer(conn, q["text"], found=hybrid(conn, gw, q["text"]))
                        if k == "prepared"][0]
            if prepared.outcome is not None:
                save([{"question": q["id"], "condition": "-", "note": f"ended before model: {prepared.outcome.state}"}])
                continue
            q_rows = []
            conditions = [("C0", None)]
            for p in profiles:
                policy = policy_for(signals_of(p, q["topic"]))
                if policy is None:
                    q_rows.append({"question": q["id"], "condition": p["id"], "note": "no policy: same turn as C0"})
                else:
                    conditions.append((p["id"], policy))
            for name, policy in conditions:
                for i in range(args.repeats):
                    try:
                        o = [v for k, v in generate(gw, dataclasses.replace(prepared, policy=policy)) if k == "done"][0]
                        claims = claims_of(o.text) if o.state == "answered" else []
                        row = {"question": q["id"], "topic": q["topic"], "condition": name, "run": i,
                               "level": policy.level if policy else None, "state": o.state, "adapted": o.adapted,
                               "adapt_failure": o.adapt_failure, "base_text": o.base_text,
                               "text": o.text, "claims_checked": o.claims_checked, "claims_removed": o.claims_removed,
                               "sentences": len(claims), "avg_chars": round(statistics.mean(map(len, claims))) if claims else 0,
                               "with_numbers": sum(bool(NUMBER.search(c)) for c in claims),
                               "with_reason": sum(bool(REASON.search(c)) for c in claims)}
                    except Exception as e:  # one failed call must not lose the rest of the run
                        row = {"question": q["id"], "topic": q["topic"], "condition": name, "run": i, "error": repr(e)}
                    q_rows.append(row)
                    print(q["id"], name, i, row.get("state", row.get("error")), row.get("adapted"), row.get("sentences"), file=sys.stderr)
                    down = "error" in row or MODEL_DOWN_NOTICE in (row.get("text") or "") or (
                        row.get("state") != "answered" and o.notice == MODEL_DOWN_NOTICE)
                    down_in_a_row = down_in_a_row + 1 if down else 0
                    if down_in_a_row >= MAX_MODEL_DOWN_IN_A_ROW:
                        save(q_rows)
                        print(f"stopped: the model failed {down_in_a_row} times in a row (quota or outage)", file=sys.stderr)
                        return 2
                    time.sleep(args.pause)
            # Coverage of the layout against the same turn's stage A: what stage B kept of what it was given.
            # (Comparing with another C0 run mixes in stage A's own run-to-run variation.)
            for r in (r for r in q_rows if r.get("adapted")):
                r["coverage"] = judge(gw, q["text"], r["base_text"], r["text"])
                time.sleep(args.pause)
            save(q_rows)
            print(q["id"], "saved", file=sys.stderr)

    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
