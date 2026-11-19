"""Layout stage: the checked claims, laid out for one learner (stage B).

Stage A (pipeline.generate up to the post-check) decides whether the passages answer the question and
which claims are shown; it never sees the learner. Only when it has answered does this stage run:
one model call rewrites and orders the verified claims as the learner's policy asks, and may add a
few sentences a passage states (a definition, reason, condition or example). Code then requires:

- coverage: every verified claim is restated by at least one sentence (a policy never removes);
- a restated sentence keeps only numbers its claims have, and the checker (check_v1, an entailment
  call) says "yes": its claims state it;
- an addition quotes its passage word for word (the tier-1 check), and the checker says "yes";
- the first sentence restates a claim: the direct answer comes first.

An addition that fails is dropped. Anything else that fails, a malformed reply or a model error,
returns a Layout without claims and the reason, and the caller shows stage A's claims as they are.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.chat.compose import Part, compose
from app.chat.personalize import Policy, profile_text
from app.chat.postcheck import Claim, Evidence, check_tier1, numbers_in, resolve_ids
from app.chat.retrieval import Passage
from app.gateway import GatewayError, ModelUnavailable

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
# ask(task, system, user) -> parsed JSON or None; pipeline passes its own model call (one retry on bad JSON).
Ask = Callable[[str, str, str], dict | None]


@dataclass(frozen=True)
class Sentence:
    text: str
    claims: list[int]          # indices into the verified claims; empty for an addition
    evidence: list[Evidence]   # an addition's quotes


def _read(name: str) -> str:
    return (PROMPTS / f"{name}.txt").read_text(encoding="utf-8")


def claims_block(claims: list[Claim]) -> str:
    return "Ý đã kiểm chứng:\n" + "\n".join(f"[{i}] {c.text}" for i, c in enumerate(claims)) + "\n\n"


def _sentences(data: dict | None, n_claims: int) -> list[Sentence] | None:
    raw = data.get("sentences") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return None
    out = []
    for s in raw:
        if not isinstance(s, dict) or not isinstance(s.get("text"), str) or not s["text"].strip():
            continue
        ids = s.get("claims") if isinstance(s.get("claims"), list) else []
        if any(not isinstance(i, int) or not 0 <= i < n_claims for i in ids):
            return None                                  # a claim that does not exist: the reply is not trusted
        ev = [Evidence(e["passage_id"], e["quote"]) for e in (s.get("evidence") or [])
              if isinstance(e, dict) and isinstance(e.get("passage_id"), str) and isinstance(e.get("quote"), str)]
        out.append(Sentence(s["text"].strip(), list(dict.fromkeys(ids)), ev))
    return out


def _entailed(ask: Ask, items: list[tuple[str, str]]) -> list[bool]:
    """One check_v1 call: does each source state its sentence? Only "yes" counts. Fails closed."""
    blocks = [f"Claim {i}: {text}\nCited passages:\n{source}" for i, (text, source) in enumerate(items)]
    data = ask("check", _read("check_v1"), "\n\n".join(blocks))
    raw = data.get("verdicts") if isinstance(data, dict) else None
    verdicts = {v.get("i"): v.get("verdict") for v in (raw if isinstance(raw, list) else []) if isinstance(v, dict)}
    return [verdicts.get(i) == "yes" for i in range(len(items))]


@dataclass(frozen=True)
class Layout:
    claims: list[Claim] | None    # the learner's layout; None: show stage A's claims
    failure: str | None = None    # why stage A is shown, for the trace and the experiments


def render(ask: Ask, question: str, claims: list[Claim], passages: list[Passage], policy: Policy) -> Layout:
    """The claims laid out for the learner, each with the passages it rests on, or why not."""
    by_id = {p.id: p for p in passages}
    user = compose([Part("question", f"Câu hỏi: {question}\n\n"), Part("learner_profile", profile_text(policy)),
                    Part("verified_claims", claims_block(claims))], passages).user
    try:
        sentences = _sentences(ask("render", _read("render_v1"), user), len(claims))
        if not sentences:
            return Layout(None, "malformed")
        sentences = [Sentence(s.text, s.claims, resolve_ids([], s.evidence, list(by_id))[1]) for s in sentences]
        if not sentences[0].claims:
            return Layout(None, "direct_answer_not_first")
        restated = [s for s in sentences if s.claims]
        if {i for s in restated for i in s.claims} != set(range(len(claims))):
            return Layout(None, "claim_missing")
        if any(not numbers_in(s.text) <= numbers_in(" ".join(claims[i].text for i in s.claims)) for s in restated):
            return Layout(None, "number_changed")
        added = []
        for s in (s for s in sentences if not s.claims):
            pids = list(dict.fromkeys(e.passage_id for e in s.evidence))
            if len(added) < policy.additions and pids and check_tier1(
                    [Claim(s.text, pids)], s.evidence, {p.id: p.text for p in passages}):
                added.append((s, pids))
        kept_additions = {id(s) for s, _ in added}
        sentences = [s for s in sentences if s.claims or id(s) in kept_additions]
        sources = {id(s): pids for s, pids in added}
        checks = _entailed(ask, [(s.text, "\n".join(f"[c{i}] {claims[i].text}" for i in s.claims) if s.claims
                                  else "\n".join(f"[{pid}] {by_id[pid].text}" for pid in sources[id(s)]))
                                 for s in sentences])
    except (GatewayError, ModelUnavailable):   # the worker raises the latter for a refused call
        return Layout(None, "model_error")
    out = []
    for s, ok in zip(sentences, checks):
        if s.claims and not ok:
            return Layout(None, "not_entailed")          # a restatement says something its claims do not
        if ok:
            pids = (list(dict.fromkeys(pid for i in s.claims for pid in claims[i].passage_ids)) if s.claims
                    else sources[id(s)])
            out.append(Claim(s.text, pids))
    return Layout(out)
