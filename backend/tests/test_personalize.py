"""Learner policy and layout stage (app/chat/personalize.py, app/chat/adapt.py).

Stage A (the grounded answer) never sees the learner and alone decides whether the passages answer.
Stage B lays out stage A's verified claims for the learner; it may not drop a claim, change a number,
say what the claims do not, or add what no passage states. Any failure shows stage A unchanged."""
import dataclasses
import json
import re

import pytest

from app.chat.personalize import Policy, Signals, policy_for, profile_text
from app.chat.pipeline import INSUFFICIENT_COPY, generate, prepare_answer
from app.gateway import FakeGateway, GatewayError
from app.repo import consent
from tests.conftest import birth_dose_json

CFG = {"enabled": True, "min_responses": 10, "low": 0.4, "high": 0.75, "recall_applied_gap": 0.3,
       "min_bloom_items": 8, "additions": {"co_ban": 3, "trung_binh": 0, "nang_cao": 0}, "reason_additions": 2}
Q = "Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?"
WEAK = Policy("co_ban", 3, plain_wording=True, give_reasons=False, thresholds_first=False)
RESTATED = "Trẻ sơ sinh được tiêm mũi vắc xin viêm gan B trong vòng 24 giờ đầu sau sinh."
ADDED = "Đây là mũi tiêm viêm gan B dành cho trẻ sơ sinh."


# ---- rules -----------------------------------------------------------------------------------------

def test_too_little_known_means_no_policy():
    assert policy_for(Signals(None, 0, None, None), CFG) is None
    assert policy_for(Signals(0.1, 9, 0.9, 0.1), CFG) is None      # below min_responses


@pytest.mark.parametrize("mastery,level,additions", [(0.2, "co_ban", 3), (0.39, "co_ban", 3),
                                                     (0.4, "trung_binh", 0), (0.74, "trung_binh", 0),
                                                     (0.75, "nang_cao", 0), (0.95, "nang_cao", 0)])
def test_mastery_sets_the_level(mastery, level, additions):
    p = policy_for(Signals(mastery, 50, None, None), CFG)
    assert (p.level, p.additions) == (level, additions)
    assert p.plain_wording == (level == "co_ban") and p.thresholds_first == (level == "nang_cao")
    assert not p.give_reasons                                       # no Bloom data, no "why" rule


def test_remembers_but_does_not_apply_asks_for_reasons():
    p = policy_for(Signals(0.5, 50, 0.87, 0.33), CFG)
    assert p.give_reasons and p.additions == 2
    assert not policy_for(Signals(0.5, 50, 0.80, 0.60), CFG).give_reasons   # gap 0.2 < 0.3


def test_profile_block_says_what_to_do_not_who_the_learner_is():
    text = profile_text(WEAK)
    assert "Luôn giữ ý trả lời trực tiếp câu hỏi trước" in text and "không bao giờ bỏ ý nào" in text
    assert "đủ ý" in text and "tối đa 3 câu bổ sung" in text and "Không tự nghĩ ra ví dụ" in text
    assert "0.2" not in text and "mastery" not in text and "theta" not in text
    assert "Không thêm câu bổ sung" in profile_text(Policy("nang_cao", 0, False, False, True))


# ---- stage A is the same with or without a learner -----------------------------------------------

def _prepared(conn, learner_id=None):
    return [v for k, v in prepare_answer(conn, Q, learner_id=learner_id) if k == "prepared"][0]


def _make_known(conn, learner, theta: float, n: int = 40):
    code = conn.execute("select competency_code from passage where id='tc-p02'").fetchone()["competency_code"]
    conn.execute("""insert into mastery(learner_id, competency_code, theta, n_responses) values (%s,%s,%s,%s)
                    on conflict (learner_id, competency_code) do update set theta=excluded.theta, n_responses=excluded.n_responses""",
                 (learner["id"], code, theta, n))


def test_the_answer_prompt_never_carries_the_profile(conn, learner, clock):
    _make_known(conn, learner, -1.5)                                # mastery ≈ 0.18
    consent.give(conn, learner["id"], "personalization", "v1", clock.now)
    base, p = _prepared(conn), _prepared(conn, learner["id"])
    assert (p.user, p.system, p.passages, p.check_text) == (base.user, base.system, base.passages, base.check_text)
    assert "Hồ sơ người học" not in p.user and p.policy.level == "co_ban" and p.question == Q


def test_without_or_after_withdrawing_consent_there_is_no_policy(conn, learner, clock):
    _make_known(conn, learner, -1.5)
    assert _prepared(conn, learner["id"]).policy is None
    consent.give(conn, learner["id"], "personalization", "v1", clock.now)
    consent.withdraw(conn, learner["id"], "personalization", clock.now)
    assert _prepared(conn, learner["id"]).policy is None


# ---- stage B ---------------------------------------------------------------------------------------

def _quote(conn) -> str:
    return re.search(r'"quote":"([^"]+)"', birth_dose_json(conn))[1]


def model(conn, sentences=None, verdict=lambda i, text: "yes", answer=None, render_error=False):
    """A scripted model: stage A's answer, the layout, then the checker's verdicts."""
    def reply(task, messages):
        if task == "answer":
            return answer or birth_dose_json(conn)
        if task == "render":
            if render_error:
                raise GatewayError("down")
            return json.dumps({"sentences": sentences}, ensure_ascii=False)
        claims = re.findall(r"^Claim (\d+): (.*)$", messages[0]["content"], re.M)
        return json.dumps({"verdicts": [{"i": int(i), "verdict": verdict(int(i), t)} for i, t in claims]})
    return FakeGateway(reply)


def turn(conn, gw, policy=WEAK):
    prepared = dataclasses.replace(_prepared(conn), policy=policy)
    return [v for k, v in generate(gw, prepared) if k == "done"][0]


def restated(text=RESTATED, claims=(0,)):
    return {"text": text, "claims": list(claims), "evidence": []}


def added(conn, text=ADDED, quote=None):
    return {"text": text, "claims": [], "evidence": [{"passage_id": "tc-p02", "quote": quote or _quote(conn)}]}


def stage_a_text(conn):
    return turn(conn, FakeGateway([birth_dose_json(conn)]), policy=None).text


def test_insufficient_passages_end_before_the_profile_is_ever_sent(conn, learner):
    """Wrong-topic passages: stage A declines, the layout stage never runs, the profile is never sent."""
    gw = model(conn, answer='{"insufficient": true}')
    out = turn(conn, gw)
    assert out.state == "insufficient_evidence" and out.text == INSUFFICIENT_COPY and out.adapted is None
    assert [c["task"] for c in gw.calls] == ["answer"]
    assert not any("Hồ sơ người học" in c["messages"][0]["content"] for c in gw.calls)


def test_a_good_layout_is_shown_with_its_citations(conn, learner):
    gw = model(conn, [restated(), added(conn)])
    out = turn(conn, gw)
    assert out.adapted is True and out.state == "answered"
    assert out.text == f"{RESTATED} [1] {ADDED} [1]"
    assert [c["passage_id"] for c in out.citations] == ["tc-p02"]
    assert out.claims_checked == 1 and out.claims_removed == 0 and out.notice is None
    assert [c["task"] for c in gw.calls] == ["answer", "render", "check"]
    render_msg = gw.calls[1]["messages"][0]["content"]
    assert render_msg.startswith(f"Câu hỏi: {Q}\n") and "Hồ sơ người học" in render_msg and "[0] " in render_msg


@pytest.mark.parametrize("sentences,reason", [
    pytest.param(lambda c: [added(c)], "direct_answer_not_first", id="only an addition"),
    pytest.param(lambda c: [added(c), restated()], "direct_answer_not_first", id="direct answer not first"),
    pytest.param(lambda c: [restated(RESTATED.replace("24", "12"))], "number_changed", id="number changed"),
    pytest.param(lambda c: [restated(claims=(0, 3))], "malformed", id="claim that does not exist"),
    pytest.param(lambda c: "not a list", "malformed", id="malformed"),
])
def test_a_layout_that_breaks_a_rule_falls_back_to_stage_a(conn, learner, sentences, reason):
    out = turn(conn, model(conn, sentences(conn)))
    assert out.adapted is False and out.adapt_failure == reason
    assert out.state == "answered" and out.text == stage_a_text(conn) == out.base_text


def test_a_dropped_claim_falls_back_to_stage_a(conn, learner):
    """Two verified claims, the layout restates only one: coverage fails."""
    two = json.loads(birth_dose_json(conn).strip().removeprefix("```json").removesuffix("```"))
    two["claims"] = two["claims"] * 2
    gw = model(conn, [restated()], answer=json.dumps(two, ensure_ascii=False))
    out = turn(conn, gw)
    assert out.adapted is False and out.adapt_failure == "claim_missing" and out.text.count("[1]") == 2


def test_a_restatement_the_checker_rejects_falls_back(conn, learner):
    out = turn(conn, model(conn, [restated()], verdict=lambda i, t: "partial"))
    assert out.adapted is False and out.adapt_failure == "not_entailed" and out.text == stage_a_text(conn)


def test_a_model_error_in_the_layout_stage_falls_back(conn, learner):
    out = turn(conn, model(conn, render_error=True))
    assert out.adapted is False and out.adapt_failure == "model_error"
    assert out.state == "answered" and out.text == stage_a_text(conn)


def test_an_unsupported_addition_is_dropped_and_the_rest_kept(conn, learner):
    made_up = added(conn, "Ví dụ: bé An được tiêm lúc 2 giờ tuổi.", quote="bé An được tiêm lúc 2 giờ tuổi")
    rejected = added(conn, "Mũi này giúp phòng bệnh suốt đời.")
    gw = model(conn, [restated(), made_up, rejected],
               verdict=lambda i, t: "no" if "suốt đời" in t else "yes")
    out = turn(conn, gw)
    assert out.adapted is True and out.text == f"{RESTATED} [1]"


def test_additions_beyond_the_policy_are_dropped(conn, learner):
    none_allowed = Policy("nang_cao", 0, False, False, True)
    out = turn(conn, model(conn, [restated(), added(conn)]), policy=none_allowed)
    assert out.adapted is True and out.text == f"{RESTATED} [1]"
