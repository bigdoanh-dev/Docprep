"""Pedagogical evaluation, step 1: the answers to judge.

For each question, retrieval (hybrid + LLM rerank, as in chat) and stage A run once; then, for each
synthetic learner profile, stage B lays out the SAME verified claims under four conditions:

  C0 base       stage A as is (no personalization)
  C1 v1         the earlier personalization (mastery 0–1 in three levels; frozen copy in legacy/)
  C2 bloom      v2 Bloom profile and frontier only (scaffolding off: the ablation)
  C3 scaffold   v2 Bloom + scaffolding (prerequisite bridge, misconception, self-check)

so differences come from stage B alone. Profiles are synthetic (dev/test only): the same Bloom
profile is applied to whatever competency the passages cover. A profile's misconception is written
for each question by the model as a bank-style item (wrong option + why it is wrong) from the
passages, since the real bank has no items on these chapters yet. The raw stage B replies are kept
for the stage-B checker test (faults.py). Run inside the chat container (see README.md).
"""
import argparse
import dataclasses
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "legacy"))
sys.path.insert(0, str(HERE.parent / "retrieval_eval"))

import adapt_v1  # noqa: E402
import personalize_v1  # noqa: E402
from app.chat import adapt, pipeline, rerank  # noqa: E402
from app.chat.normalise import normalise  # noqa: E402
from app.chat.personalize import Misconception, Signals, policy_for, with_bridge  # noqa: E402
from app.chat.pipeline import _assemble, parse_model_json, prepare_answer  # noqa: E402
from app.chat.retrieval import Found  # noqa: E402
from app.db import connect  # noqa: E402
from app.repo import content  # noqa: E402
from common import gateway, hybrid  # noqa: E402

V1_CFG = {"enabled": True, "min_responses": 10, "low": 0.4, "high": 0.75, "recall_applied_gap": 0.3,
          "min_bloom_items": 8, "additions": {"co_ban": 3, "trung_binh": 0, "nang_cao": 0}, "reason_additions": 2}
MISCONCEPTION_SYSTEM = """You write one multiple-choice item for a Vietnamese preventive-medicine question bank, from the passages only.
Given a student's question and passages, write an item on the same point with the correct option and ONE wrong option that students commonly choose, and the rationale a reviewer would write for why that wrong option is wrong. Everything must follow from the passages.
Output JSON only: {"stem": "...", "correct": "...", "wrong": "...", "why_wrong": "..."}"""


class Recorder:
    """The model call used by stage B, keeping the last render reply (for faults.py)."""
    def __init__(self, gw):
        self.gw, self.render = gw, None

    def __call__(self, task, system, user):
        data = parse_model_json(self.gw.complete(task, system, [{"role": "user", "content": user}],
                                                 f"{task}-pedagogy-eval").text)
        if task == "render":
            self.render = data
        return data


def stage_a(conn, gw, question: str):
    """Retrieval as in chat, then stage A; returns (prepared, claims) or None when it did not answer."""
    pool = Found(hybrid(conn, gw, question, rerank.cfg()["pool"]))
    ask = lambda system, user: parse_model_json(gw.complete("rerank", system, [{"role": "user", "content": user}],
                                                            "rerank-v1").text)
    found = rerank.apply(ask, question, pool).found
    prepared = [v for k, v in prepare_answer(conn, question, found=found) if k == "prepared"][0]
    if prepared.outcome is not None:
        return None
    captured = {}

    def capture(_ask, q, claims, passages, policy):
        captured["claims"] = claims
        return adapt.Layout(None, "captured")
    real, adapt.render = adapt.render, capture
    try:
        out = [v for k, v in pipeline.generate(gw, dataclasses.replace(prepared, policy=_DUMMY)) if k == "done"][0]
    finally:
        adapt.render = real
    return (prepared, captured["claims"], out.text) if "claims" in captured else None


_DUMMY = policy_for(Signals({1: (9, 9)}), {"min_responses": 1, "min_level_items": 1, "pass_accuracy": 0.7,
                                           "scaffolding": False, "additions_by_frontier": {2: 0}})


def misconception(gw, question: str, passages) -> Misconception | None:
    blocks = "\n\n".join(f"[{p.id}]\n{p.text[:1500]}" for p in passages)
    data = parse_model_json(gw.complete("check", MISCONCEPTION_SYSTEM, [{"role": "user", "content":
                                        f"Câu hỏi: {question}\n\n{blocks}"}], "eval-misconception-v1").text) or {}
    if all(isinstance(data.get(k), str) and data[k].strip() for k in ("stem", "correct", "wrong", "why_wrong")):
        return Misconception(data["stem"], data["wrong"], data["why_wrong"], data["correct"])
    return None


def prerequisites_of(conn, codes: list[str]) -> tuple[tuple[str, str], ...]:
    rows = conn.execute("""select distinct p.code, p.name from competency_node n
                           join competency_node p on p.code = any(n.prerequisite_codes)
                           where n.code = any(%s) and not (p.code = any(%s)) order by p.code""", (codes, codes))
    return tuple((r["code"], r["name"]) for r in rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "out"))
    args = ap.parse_args()
    spec = yaml.safe_load((HERE / "cases.yaml").read_text(encoding="utf-8"))
    gw = gateway()
    out = Path(args.out) / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True)
    rows = []
    with connect() as conn:
        for q in spec["questions"]:
            got = stage_a(conn, gw, q["text"])
            if got is None:
                print(q["id"], "stage A did not answer; skipped"); continue
            prepared, claims, base_text = got
            codes = list(dict.fromkeys(p.competency_code for p in prepared.passages if p.competency_code))
            prereqs = prerequisites_of(conn, codes)
            mistake = misconception(gw, q["text"], prepared.passages)
            by_id = {p.id: p for p in prepared.passages}
            norm = normalise(q["text"], content.glossary(conn))
            for prof in spec["profiles"]:
                rungs = {int(k): tuple(v) for k, v in prof["rungs"].items()}
                sig = Signals(rungs, prereqs if prof.get("weak_prerequisites") else (),
                              (mistake,) if prof.get("misconception") and mistake else ())
                v1 = personalize_v1.policy_for(personalize_v1.Signals(**prof["v1"]), V1_CFG)
                policies = {"C1_v1": v1, "C2_bloom": policy_for(sig, scaffold=False),
                            "C3_scaffold": with_bridge(conn, policy_for(sig, scaffold=True), norm)}
                base = {"question_id": q["id"], "question": q["text"], "profile": prof["id"], "codes": codes,
                        "prerequisites": [n for _, n in sig.weak_prerequisites],
                        "misconception": dataclasses.asdict(sig.misconceptions[0]) if sig.misconceptions else None,
                        "passages": [{"id": p.id, "text": p.text} for p in prepared.passages],
                        "claims": [dataclasses.asdict(c) for c in claims]}
                rows.append({**base, "condition": "C0_base", "text": base_text, "adapted": None, "failure": None})
                for cond, pol in policies.items():
                    rec = Recorder(gw)
                    module = adapt_v1 if cond == "C1_v1" else adapt
                    layout = module.render(rec, q["text"], claims, prepared.passages, pol)
                    ids = {**by_id, **{p.id: p for p in getattr(pol, "bridge", ())}}
                    if layout.claims is not None:
                        text = _assemble(layout.claims, ids)[0]
                    else:
                        text = base_text
                    rows.append({**base, "condition": cond, "text": text, "adapted": layout.claims is not None,
                                 "failure": layout.failure, "policy": repr(pol), "render_reply": rec.render,
                                 "bridge": [{"id": p.id, "text": p.text} for p in getattr(pol, "bridge", ())]})
                print(q["id"], prof["id"], [(r["condition"], r["failure"]) for r in rows[-4:]], flush=True)
    (out / "answers.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                                       encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
