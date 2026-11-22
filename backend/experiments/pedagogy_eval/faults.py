"""The stage-B checker (step 15 of the chat flow) tested by planting faults.

Stage B may only re-present stage A's verified claims; code and an entailment call (check_v1) must
catch any departure. This takes real stage B replies (C3 rows of a run.py run that were accepted),
plants one fault in each, and replays adapt.render with that reply and the REAL checker:

  clean                 the reply unchanged                    must pass  (false-rejection rate)
  drop_claim            a claim's sentences removed            code: claim_missing
  number_changed        a number in a restatement altered      code: number_changed
  answer_not_first      an addition moved first                code: direct_answer_not_first
  meaning_flip          a restatement given a subtly different meaning, same numbers (negation,
                        other population, quantifier, condition, action)   checker: not_entailed
  fabricated_addition   an addition with a made-up fact and a quote not in any passage   tier-1: dropped
  misquoted_addition    an addition with a REAL quote but a sentence the quote does not say   checker: dropped

The two model-made faults are written by Gemini (another family than the Haiku checker), told to keep
every number. Writes faults.jsonl and faults.md in the run directory. Run inside the chat container.
"""
import copy
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "retrieval_eval"))
from common import ask_json, gateway  # noqa: E402
from rerank_eval import make  # noqa: E402

from app.chat import adapt  # noqa: E402
from app.chat.personalize import Policy  # noqa: E402
from app.chat.pipeline import parse_model_json  # noqa: E402
from app.chat.postcheck import Claim  # noqa: E402
from app.chat.retrieval import get_passages  # noqa: E402
from app.db import connect  # noqa: E402

FLIP_SYSTEM = """You make test cases for a fact checker of Vietnamese medical text. Rewrite the given Vietnamese sentence so that it reads naturally but says something DIFFERENT that its source would not support, with a subtle change of this kind: {kind}.
Keep every number exactly as written; do not add numbers. The meaning must really change: a careful reader of the original would call the new sentence wrong. If you cannot do that for this sentence, set "meaning_changed" to false.
Output JSON only: {{"text": "<rewritten sentence>", "meaning_changed": true | false}}"""
FLIP_KINDS = ["phủ định hoặc đảo ý (nên ↔ không nên, có ↔ không)", "đổi đối tượng (trẻ em ↔ người lớn, phụ nữ có thai ...)",
              "đổi lượng từ (ít nhất một ↔ tất cả, thường ↔ luôn luôn)", "đổi điều kiện hoặc thời điểm áp dụng",
              "đổi hành động hoặc thuốc thành một hành động khác cùng nhóm"]
MISQUOTE_SYSTEM = """You make test cases for a fact checker of Vietnamese medical text. Given a quote from a guideline, write ONE Vietnamese sentence on the same topic that sounds plausible but states something the quote does NOT say (an extra claim, a wrong reason, or a wrong generalisation). Keep any number from the quote unchanged and add no new number.
Output JSON only: {"text": "<sentence>"}"""
EXPECT = {"drop_claim": "claim_missing", "answer_not_first": "direct_answer_not_first"}
# A restatement the checker rejects is shown as its claim, so for these the fault is caught when the
# planted sentence is no longer shown (or the whole layout fell back to stage A).
PLANTED_SENTENCE = ("number_changed", "meaning_flip")


def restated(reply):
    return [i for i, s in enumerate(reply["sentences"]) if s.get("claims") and s.get("kind") != "check"]


def additions(reply):
    return [i for i, s in enumerate(reply["sentences"]) if not s.get("claims")]


def bump(text: str) -> str | None:
    """Raises the first figure of the sentence by one; a step label ("Bước 1:") is not a figure."""
    label = adapt._STEP_LABEL.match(text)
    start = label.end() if label else 0
    m = re.search(r"\d+", text[start:])
    if not m:
        return None
    a, b = start + m.start(), start + m.end()
    return text[:a] + str(int(text[a:b]) + 1) + text[b:]


def plant(kind: str, reply: dict, rng, gemini, passages) -> tuple[dict, str] | None:
    """The faulty reply and the text planted (for additions), or None when this reply cannot host it."""
    r = copy.deepcopy(reply)
    S = r["sentences"]
    if kind == "clean":
        return r, ""
    if kind == "drop_claim":
        claims = sorted({c for i in restated(r) for c in S[i]["claims"]})
        if len(claims) < 2:
            return None
        k = rng.choice(claims[1:])
        r["sentences"] = [s for s in S if k not in (s.get("claims") or []) or s.get("kind") == "check"]
        return r, ""
    if kind == "number_changed":
        idx = [i for i in restated(r) if re.search(r"\d", S[i]["text"])]
        if not idx:
            return None
        i = rng.choice(idx)
        S[i]["text"] = bump(S[i]["text"])
        return r, S[i]["text"]
    if kind == "answer_not_first":
        add = additions(r)
        if not add:
            return None
        s = S.pop(add[0])
        S.insert(0, s)
        return r, ""
    if kind == "meaning_flip":
        i = rng.choice(restated(r))
        data = ask_json(gemini, FLIP_SYSTEM.format(kind=rng.choice(FLIP_KINDS)), S[i]["text"], "fault-flip-v1")
        if (not data or not isinstance(data.get("text"), str) or data.get("meaning_changed") is not True
                or data["text"].strip() == S[i]["text"].strip()):
            return None
        S[i]["text"] = data["text"].strip()
        return r, S[i]["text"]
    if kind == "fabricated_addition":
        fake = "Theo hướng dẫn, mọi trường hợp đều phải dùng kháng sinh dự phòng ngay từ đầu."
        S.append({"text": fake, "claims": [], "evidence": [{"passage_id": passages[0].id, "quote": fake}]})
        return r, fake
    if kind == "misquoted_addition":
        p = rng.choice(passages)
        sentences = [x.strip() for x in re.split(r"(?<=[.;:])\s+", p.text) if len(x.split()) >= 8]
        if not sentences:
            return None
        quote = rng.choice(sentences)
        data = ask_json(gemini, MISQUOTE_SYSTEM, quote, "fault-misquote-v1")
        if not data or not isinstance(data.get("text"), str):
            return None
        S.append({"text": data["text"].strip(), "claims": [], "evidence": [{"passage_id": p.id, "quote": quote}]})
        return r, data["text"].strip()
    raise ValueError(kind)


def main() -> int:
    run = Path(sys.argv[1])
    rows = [json.loads(l) for l in (run / "answers.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = [r for r in rows if r["condition"] == "C3_scaffold" and r["adapted"] and isinstance(r.get("render_reply"), dict)]
    checker, gemini, rng = gateway(), make("google"), random.Random(15)
    ask_check = lambda task, system, user: parse_model_json(
        checker.complete(task, system, [{"role": "user", "content": user}], "fault-check").text)
    results = []
    with connect() as conn:
        for row in rows:
            ids = [p["id"] for p in row["passages"]] + [p["id"] for p in row.get("bridge") or []]
            found = get_passages(conn, ids)
            passages = [found[i] for i in ids if i in found]
            claims = [Claim(c["text"], c["passage_ids"]) for c in row["claims"]]
            policy = Policy(1, 2, True, 9, check_question=True)
            for kind in ("clean", "drop_claim", "number_changed", "answer_not_first", "meaning_flip",
                         "fabricated_addition", "misquoted_addition"):
                got = plant(kind, row["render_reply"], rng, gemini, passages)
                if got is None:
                    continue
                reply, planted = got
                ask = lambda task, system, user, reply=reply: reply if task == "render" else ask_check(task, system, user)
                layout = adapt.render(ask, row["question"], claims, passages, policy)
                shown = [c.text for c in layout.claims] if layout.claims is not None else None
                if kind == "clean":                                   # here "caught" = wrongly rejected
                    caught = layout.claims is None or layout.replaced > 0
                elif kind in EXPECT:
                    caught = layout.failure == EXPECT[kind]
                elif kind in PLANTED_SENTENCE:                        # caught: the planted sentence is not shown
                    caught = shown is None or planted not in shown
                else:                                                 # an addition: caught when not shown
                    caught = shown is not None and planted not in shown
                    if shown is None:
                        caught = None                                 # the whole layout fell back for another reason
                results.append({"question_id": row["question_id"], "profile": row["profile"], "kind": kind,
                                "planted": planted, "failure": layout.failure, "caught": caught})
                print(row["question_id"], row["profile"], kind, layout.failure, caught, flush=True)
    (run / "faults.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in results) + "\n",
                                      encoding="utf-8")
    by = defaultdict(list)
    for r in results:
        by[r["kind"]].append(r)
    L = ["# Kiểm tra bộ kiểm tầng B (bước 15) bằng cách cài lỗi", "",
         f"{len(rows)} câu trả lời tầng B thật (C3) được chấp nhận, mỗi câu cài một loại lỗi; bộ kiểm thật (Haiku, check_v1) chạy lại.", "",
         "| Loại lỗi | Ai phải bắt | Số ca | Bắt được |", "|---|---|---|---|"]
    who = {"clean": "không ai (phải cho qua)", "drop_claim": "code", "number_changed": "code hoặc NLI", "answer_not_first": "code",
           "meaning_flip": "NLI", "fabricated_addition": "code (trích dẫn)", "misquoted_addition": "NLI"}
    for kind, rs in by.items():
        valid = [r for r in rs if r["caught"] is not None]
        n_ok = sum(bool(r["caught"]) for r in valid)
        cell = (f"chặn nhầm {n_ok}/{len(valid)}" if kind == "clean" else f"{n_ok}/{len(valid)}"
                + (f" (+{len(rs) - len(valid)} ca cả bản quay về tầng A vì lý do khác)" if len(rs) > len(valid) else ""))
        L.append(f"| {kind} | {who[kind]} | {len(rs)} | {cell} |")
    missed = [r for r in results if r["kind"] not in ("clean",) and r["caught"] is False and r["planted"]]
    L += ["", f"## Lỗi lọt qua ({len(missed)})", ""] + [f"- [{r['kind']}] {r['planted']}" for r in missed]
    (run / "faults.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
