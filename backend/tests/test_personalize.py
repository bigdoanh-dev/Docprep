"""Learner policy and layout stage (app/chat/personalize.py v2, app/chat/adapt.py).

Stage A (the grounded answer) never sees the learner and alone decides whether the passages answer.
Stage B teaches stage A's verified claims toward the learner's Bloom frontier, with scaffolding; it may
not drop a claim, change a number, say what the claims do not, or add what no passage states. Any
failure shows stage A unchanged."""
import dataclasses
import json
import re

import pytest

from app.chat import personalize
from app.chat.normalise import normalise
from app.chat.personalize import FRONTIER_MOVES, Misconception, Policy, Signals, policy_for, profile, profile_text
from app.chat.pipeline import INSUFFICIENT_COPY, generate, prepare_answer
from app.chat.worker import TurnModelUnavailable, TurnStopped
from app.gateway import FakeGateway, GatewayError
from app.repo import consent, content
from tests.conftest import birth_dose_json

CFG = {"enabled": True, "min_responses": 6, "min_level_items": 2, "pass_accuracy": 0.7, "scaffolding": True,
       "weak_mastery": 0.4, "max_misconceptions": 2, "bridge_passages": 2,
       "additions_by_frontier": {1: 2, 2: 2, 3: 2, 4: 1, 5: 1, 6: 0}}
Q = "Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?"
WEAK = Policy(secure=1, frontier=2, scaffold=True, additions=3, check_question=True)
RESTATED = "Trẻ sơ sinh được tiêm mũi vắc xin viêm gan B trong vòng 24 giờ đầu sau sinh."
ADDED = "Đây là mũi tiêm viêm gan B dành cho trẻ sơ sinh."
MISTAKE = Misconception("Mũi viêm gan B sơ sinh tiêm khi nào?", "Trong tháng đầu", "Phải tiêm trong 24 giờ đầu.",
                        "Trong vòng 24 giờ")


# ---- the Bloom profile -----------------------------------------------------------------------------

@pytest.mark.parametrize("rungs,expected", [
    ({1: (4, 4), 2: (4, 3), 3: (4, 1)}, (2, 3)),        # holds Nhớ and Hiểu, teach toward Vận dụng
    ({1: (4, 2), 3: (4, 4)}, (0, 1)),                    # a gap low down comes first
    ({2: (3, 3), 4: (3, 3)}, (4, 5)),                    # every observed level held: the next one
    ({6: (2, 2)}, (6, 6)),
    ({1: (1, 0), 2: (4, 4)}, (2, 3)),                    # one answer is not a level observed
])
def test_secure_and_frontier_come_from_the_answers_per_level(rungs, expected):
    assert profile(rungs, CFG) == expected


def test_too_little_known_means_no_policy():
    assert policy_for(Signals({}), CFG) is None
    assert policy_for(Signals({1: (3, 3), 2: (2, 0)}), CFG) is None       # 5 answers < min_responses
    assert policy_for(Signals({1: (1, 1), 2: (1, 0), 3: (1, 1), 4: (1, 0), 5: (1, 1), 6: (1, 1)}), CFG) is None


def test_each_frontier_has_its_own_way_of_explaining():
    for frontier in range(1, 7):
        rungs = {lvl: (3, 3) for lvl in range(1, frontier)} | {frontier: (6, 0)}
        p = policy_for(Signals(rungs), CFG)
        assert p.frontier == frontier and FRONTIER_MOVES[frontier] in profile_text(p)


def test_a_weak_learner_gets_scaffolds_not_simpler_words():
    s = Signals({1: (4, 4), 2: (4, 1)}, (("FND", "Khái niệm cơ bản"),), (MISTAKE,))
    p = policy_for(s, CFG)
    text = profile_text(p)
    assert (p.secure, p.frontier, p.check_question) == (1, 2, True)
    assert p.prerequisites == (("FND", "Khái niệm cơ bản"),) and p.misconceptions == (MISTAKE,)
    assert p.additions == 2 + 1 + 1                                    # frontier's own, bridge, misconception
    assert "không viết lại cho đơn giản hơn chỉ vì người học còn yếu" in text
    assert "Trong tháng đầu" in text and "Phải tiêm trong 24 giờ đầu." in text and "tự kiểm tra" in text
    assert "dễ hiểu" not in text and "câu ngắn" not in text


def test_scaffolds_fade_as_the_learner_rises():
    s = Signals({lvl: (3, 3) for lvl in range(1, 5)} | {5: (3, 0)}, (("FND", "Khái niệm cơ bản"),), (MISTAKE,))
    p = policy_for(s, CFG)
    assert p.frontier == 5 and p.prerequisites == () and p.check_question     # no bridge above Vận dụng
    top = policy_for(Signals({lvl: (3, 3) for lvl in range(1, 7)}), CFG)
    assert top.frontier == 6 and not top.check_question and top.additions == 0


def test_bloom_only_is_the_ablation_without_scaffolds():
    s = Signals({1: (4, 4), 2: (4, 1)}, (("FND", "Khái niệm cơ bản"),), (MISTAKE,))
    p = policy_for(s, CFG, scaffold=False)
    assert not p.scaffold and p.prerequisites == () and p.misconceptions == () and not p.check_question
    assert FRONTIER_MOVES[2] in profile_text(p) and "tự kiểm tra" not in profile_text(p)


def test_profile_block_says_what_to_do_not_who_the_learner_is():
    text = profile_text(WEAK)
    assert "Luôn giữ ý trả lời trực tiếp câu hỏi trước" in text and "không bao giờ bỏ ý nào" in text
    assert "tối đa 3 câu bổ sung" in text and "Không tự nghĩ ra ví dụ" in text
    assert not re.search(r"\d\.\d|mastery|theta|%", text)
    assert "Không thêm câu bổ sung" in profile_text(Policy(6, 6, True, 0))


# ---- reading the learner's records -----------------------------------------------------------------

def _answer(conn, learner, qid, correct, chosen=None):
    conn.execute("""insert into item_response(learner_id, question_id, question_version, context, chosen, correct)
                    values (%s, %s, 1, 'diagnostic', %s, %s)""", (learner["id"], qid, chosen, correct))


def test_signals_use_reviewed_then_machine_labels_then_the_band(conn, learner):
    for q in ("q-dt-02", "q-dt-08", "q-dt-01", "q-dt-03"):                # bands 1, 1, 2, 2
        _answer(conn, learner, q, True)
    conn.execute("insert into question_bloom_label(question_id, question_version, level) values ('q-dt-08', 1, 1)")
    conn.execute("insert into question_bloom_label(question_id, question_version, level) values ('q-dt-01', 1, 5)")
    rungs = personalize.signals(conn, learner["id"], ["FND"]).rungs
    assert rungs == {2: (1, 1), 1: (1, 1), 5: (1, 1), 3: (1, 1)}
    assert personalize.signals(conn, learner["id"], ["CI-04"]).rungs == {}


def test_a_wrong_answer_brings_its_rationale(conn, learner):
    _answer(conn, learner, "q-dt-01", False, "b")
    m = personalize.signals(conn, learner["id"], ["FND"]).misconceptions
    assert len(m) == 1 and m[0].chosen == "5%" and "mẫu số" in m[0].why_wrong and m[0].correct == "2,5%"


def test_a_weak_prerequisite_is_found_through_the_map(conn, learner):
    conn.execute("update competency_node set prerequisite_codes = '{FND}' where code = 'CI-04'")
    conn.execute("insert into mastery(learner_id, competency_code, theta, n_responses) values (%s, 'FND', -2, 20)",
                 (learner["id"],))
    weak = personalize.signals(conn, learner["id"], ["CI-04"]).weak_prerequisites
    assert [code for code, _ in weak] == ["FND"]
    conn.execute("update mastery set theta = 2 where learner_id = %s", (learner["id"],))
    assert personalize.signals(conn, learner["id"], ["CI-04"]).weak_prerequisites == ()


def test_the_bridge_passages_come_from_the_prerequisite_only(conn, learner):
    p = Policy(1, 2, True, 3, prerequisites=(("FND", "Khái niệm cơ bản"),))
    bridged = personalize.with_bridge(conn, p, normalise("tỷ lệ hiện mắc mẫu số dân số", content.glossary(conn)))
    assert bridged.bridge and {b.competency_code for b in bridged.bridge} == {"FND"}
    nothing = personalize.with_bridge(conn, p, normalise("xyzzy", content.glossary(conn)))
    assert nothing.bridge == () and nothing.prerequisites == () and nothing.additions == 2


# ---- stage A is the same with or without a learner -----------------------------------------------

def _prepared(conn, learner_id=None):
    return [v for k, v in prepare_answer(conn, Q, learner_id=learner_id) if k == "prepared"][0]


def _make_known(conn, learner):
    """Answers on CI-04 (the passage's competency): band 1 all right, band 2 mostly wrong."""
    qs = conn.execute("select id, bloom_level from question where competency_code = 'CI-04' and status = 'approved' "
                      "order by id").fetchall()
    by_band = {b: [q["id"] for q in qs if q["bloom_level"] == b] for b in (1, 2)}
    for band, outcomes in ((1, (True,) * 4), (2, (True, False, False, False))):
        for i, ok in enumerate(outcomes):
            _answer(conn, learner, by_band[band][i % len(by_band[band])], ok)


def test_the_answer_prompt_never_carries_the_profile(conn, learner, clock):
    _make_known(conn, learner)
    consent.give(conn, learner["id"], "personalization", "v1", clock.now)
    base, p = _prepared(conn), _prepared(conn, learner["id"])
    assert (p.user, p.system, p.passages, p.check_text) == (base.user, base.system, base.passages, base.check_text)
    assert "Hồ sơ người học" not in p.user and (p.policy.secure, p.policy.frontier) == (2, 3) and p.question == Q


def test_without_or_after_withdrawing_consent_there_is_no_policy(conn, learner, clock):
    _make_known(conn, learner)
    assert _prepared(conn, learner["id"]).policy is None
    consent.give(conn, learner["id"], "personalization", "v1", clock.now)
    consent.withdraw(conn, learner["id"], "personalization", clock.now)
    assert _prepared(conn, learner["id"]).policy is None


# ---- stage B ---------------------------------------------------------------------------------------

def _quote(conn) -> str:
    return re.search(r'"quote":"([^"]+)"', birth_dose_json(conn))[1]


def model(conn, sentences=None, verdict=lambda i, text: "yes", answer=None, render_error=None):
    """A scripted model: stage A's answer, the layout, then the checker's verdicts."""
    def reply(task, messages):
        if task == "answer":
            return answer or birth_dose_json(conn)
        if task == "render":
            if render_error:
                raise render_error
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


@pytest.mark.parametrize("error", [GatewayError("down"), TurnModelUnavailable("model_unavailable")],
                         ids=["gateway", "chat worker (quota, overload)"])
def test_a_model_error_in_the_layout_stage_falls_back(conn, learner, error):
    """In the chat worker a refused call arrives as TurnModelUnavailable, not GatewayError: it must not
    throw away stage A's checked answer."""
    out = turn(conn, model(conn, render_error=error))
    assert out.adapted is False and out.adapt_failure == "model_error"
    assert out.state == "answered" and out.text == stage_a_text(conn)


@pytest.mark.parametrize("code", ["ai_cancelled", "ai_timeout", "ai_interrupted"])
def test_a_stopped_turn_still_stops_in_the_layout_stage(conn, learner, code):
    """A cancellation, a deadline or an uncertain call is not a refused call: the turn ends."""
    with pytest.raises(TurnStopped, match=code):
        turn(conn, model(conn, render_error=TurnStopped(code)))


def test_an_unsupported_addition_is_dropped_and_the_rest_kept(conn, learner):
    made_up = added(conn, "Ví dụ: bé An được tiêm lúc 2 giờ tuổi.", quote="bé An được tiêm lúc 2 giờ tuổi")
    rejected = added(conn, "Mũi này giúp phòng bệnh suốt đời.")
    gw = model(conn, [restated(), made_up, rejected],
               verdict=lambda i, t: "no" if "suốt đời" in t else "yes")
    out = turn(conn, gw)
    assert out.adapted is True and out.text == f"{RESTATED} [1]"


def test_additions_beyond_the_policy_are_dropped(conn, learner):
    none_allowed = Policy(6, 6, True, 0)
    out = turn(conn, model(conn, [restated(), added(conn)]), policy=none_allowed)
    assert out.adapted is True and out.text == f"{RESTATED} [1]"


def check(text="Mũi viêm gan B sơ sinh phải tiêm trong khoảng thời gian nào?", claims=(0,)):
    return {"text": text, "claims": list(claims), "evidence": [], "kind": "check"}


def test_the_self_check_question_closes_the_answer_without_a_citation(conn, learner):
    gw = model(conn, [restated(), check()])
    out = turn(conn, gw)
    assert out.adapted is True
    assert out.text == f"{RESTATED} [1] Tự kiểm tra: Mũi viêm gan B sơ sinh phải tiêm trong khoảng thời gian nào? "
    checked = re.findall(r"^Claim \d+: (.*)$", gw.calls[2]["messages"][0]["content"], re.M)
    assert checked == [RESTATED]                                    # a question is not entailment-checked


@pytest.mark.parametrize("bad", [
    pytest.param(check("Mũi này tiêm trong 12 giờ đầu phải không?"), id="a new number"),
    pytest.param(check("Hãy nhớ tiêm trong 24 giờ."), id="not a question"),
    pytest.param(check(claims=()), id="answered by no claim"),
])
def test_a_bad_self_check_is_dropped_and_the_rest_kept(conn, learner, bad):
    out = turn(conn, model(conn, [restated(), bad]))
    assert out.adapted is True and out.text == f"{RESTATED} [1]"


def test_no_self_check_unless_the_policy_asks(conn, learner):
    out = turn(conn, model(conn, [restated(), check()]), policy=Policy(6, 6, True, 0))
    assert out.text == f"{RESTATED} [1]"


def test_a_bridge_passage_may_back_an_addition_and_is_cited(conn, learner):
    from app.chat.retrieval import get_passages
    bridge = get_passages(conn, ["dt-p01"])["dt-p01"]
    quote = bridge.text.split(".")[0]
    policy = dataclasses.replace(WEAK, prerequisites=(("FND", "Khái niệm cơ bản"),), bridge=(bridge,))
    gw = model(conn, [restated(), {"text": "Nền tảng: " + quote + ".", "claims": [],
                                   "evidence": [{"passage_id": "dt-p01", "quote": quote}]}])
    out = turn(conn, gw, policy=policy)
    assert out.adapted is True and [c["passage_id"] for c in out.citations] == ["tc-p02", "dt-p01"]
    assert "[dt-p01]" in gw.calls[1]["messages"][0]["content"]


def test_a_step_label_is_not_a_changed_number_but_a_figure_still_is(conn, learner):
    ok = turn(conn, model(conn, [restated("Bước 1: " + RESTATED)]))
    assert ok.adapted is True and ok.text.startswith("Bước 1: Trẻ sơ sinh")
    bad = turn(conn, model(conn, [restated("Bước 1: " + RESTATED.replace("24", "48"))]))
    assert bad.adapted is False and bad.adapt_failure == "number_changed"
    mid = turn(conn, model(conn, [restated(RESTATED + " Đây là bước 2.")]))
    assert mid.adapt_failure == "number_changed"               # only a label at the start is ignored


def test_a_rejected_restatement_is_shown_as_its_claim_and_the_rest_kept(conn, learner):
    """Three claims, three restatements; the checker rejects one: that one is shown as its verified claim."""
    three = json.loads(birth_dose_json(conn).strip().removeprefix("```json").removesuffix("```"))
    claim = three["claims"][0]
    three["claims"] = [claim, {**claim, "text": claim["text"] + " "}, {**claim, "text": " " + claim["text"]}]
    gw = model(conn, [restated(claims=(0,)), restated("Bước đầu tiên là " + RESTATED.lower(), claims=(1,)),
                      restated(claims=(2,))],
               answer=json.dumps(three, ensure_ascii=False), verdict=lambda i, t: "no" if "Bước đầu tiên" in t else "yes")
    out = turn(conn, gw)
    assert out.adapted is True and "Bước đầu tiên" not in out.text and out.text.count("[1]") == 3
