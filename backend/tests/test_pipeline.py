import json
import re

import pytest

from app.chat.pipeline import (DECLINED_COPY, INSUFFICIENT_COPY, MODEL_DOWN_NOTICE, generate, parse_model_json,
                               prepare_answer, prepare_explain)
from app.config import settings
from app.repo.content import approved_question
from app.gateway import FakeGateway, GatewayError
from tests.conftest import birth_dose_json

Q = "Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?"


class RaisingGateway:
    def complete(self, *a, **kw):
        raise GatewayError("down")


def both(prepare, gw) -> list:
    """The two parts of a turn, one after the other: every event, the steps included."""
    events = list(prepare)
    prepared = events.pop()[1]
    if prepared.outcome is not None:
        return events + [("done", prepared.outcome)]
    return events + list(generate(gw, prepared))


def run(conn, gw, q, **kw):
    """A chat question from pre-gate to outcome, without the step events."""
    return [e for e in both(prepare_answer(conn, q, **kw), gw) if e[0] != "step"]


def test_parse_model_json_handles_fence_bare_and_prose():
    assert parse_model_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_model_json('{"a": {"b": 2}}') == {"a": {"b": 2}}
    assert parse_model_json('Đây là kết quả: {"a": 1} nhé') == {"a": 1}
    assert parse_model_json("Xin chào") is None and parse_model_json("{not json}") is None
    assert parse_model_json("[1, 2]") is None


def test_answered_with_citation_and_status_order(conn, learner):
    gw = FakeGateway([birth_dose_json(conn)])
    ev = run(conn, gw, Q)
    assert [e[0] for e in ev] == ["status", "status", "done"]
    assert [e[1] for e in ev[:2]] == ["answering", "checking_sources"]
    out = ev[-1][1]
    assert out.state == "answered" and out.text.endswith("[1]") and "24 giờ" in out.text
    assert out.citations == [{"n": 1, "passage_id": "tc-p02", "document": "Lịch tiêm chủng mở rộng",
                              "chapter": "Phần 2. Lịch tiêm chủng cho trẻ em",
                              "section": "2.1 Vắc xin tiêm cho trẻ sơ sinh", "page": 8, "article": None}]
    assert "tc-p02" in out.retrieved_ids and out.model.prompt_version == settings()["prompt_versions"]["answer"]


def test_prompt_carries_passages_and_no_display_name(conn, learner):
    gw = FakeGateway([birth_dose_json(conn)])
    run(conn, gw, Q)
    call = gw.calls[0]
    user = call["messages"][0]["content"]
    assert call["task"] == "answer" and "[tc-p02]" in user and Q in user
    # The name now lives in learner_identity, apart from the learner row; it must still never reach a prompt.
    name = conn.execute("select display_name from learner_identity where learner_id = %s",
                        (learner["id"],)).fetchone()["display_name"]
    assert name and name not in user and name not in call["system"]


def test_declined_makes_no_model_call(conn, learner):
    gw = FakeGateway([])
    ev = run(conn, gw, "Con tôi sốt 39 độ nên uống thuốc gì?")
    out = ev[-1][1]
    assert [e[0] for e in ev] == ["done"]
    assert out.state == "declined" and out.text == DECLINED_COPY and gw.calls == [] and out.citations == []


def test_out_of_corpus_is_insufficient_without_model_call(conn, learner):
    gw = FakeGateway([])
    out = run(conn, gw, "Phác đồ hoá trị ung thư phổi giai đoạn III")[-1][1]
    assert out.state == "insufficient_evidence" and out.text == INSUFFICIENT_COPY and gw.calls == []


def test_model_says_insufficient(conn, learner):
    out = run(conn, FakeGateway(['{"insufficient": true}']), Q)[-1][1]
    assert out.state == "insufficient_evidence" and out.text == INSUFFICIENT_COPY and out.notice is None


def test_prose_then_retry_then_insufficient(conn, learner):  # Review Focus 3
    gw = FakeGateway(["Xin chào", "Vẫn là văn xuôi"])
    out = run(conn, gw, Q)[-1][1]
    assert out.state == "insufficient_evidence" and len(gw.calls) == 2


def test_prose_then_valid_json_on_retry_is_answered(conn, learner):  # Review Focus 3
    gw = FakeGateway(["Xin chào", birth_dose_json(conn)])
    assert run(conn, gw, Q)[-1][1].state == "answered"


def test_unsupported_number_dropped_to_insufficient(conn, learner):
    gw = FakeGateway([birth_dose_json(conn, hours="48 giờ")])
    assert run(conn, gw, Q)[-1][1].state == "insufficient_evidence"


def test_claim_citing_unretrieved_passage_is_dropped(conn, learner):
    gw = FakeGateway([birth_dose_json(conn).replace("tc-p02", "dt-p16")])
    assert run(conn, gw, Q)[-1][1].state == "insufficient_evidence"


def test_gateway_error_gives_notice(conn, learner):
    out = run(conn, RaisingGateway(), Q)[-1][1]
    assert out.state == "insufficient_evidence" and out.notice == MODEL_DOWN_NOTICE and out.text == "Chưa trả lời được câu hỏi này lúc này."


def test_detail_flag_reaches_the_prompt_but_not_retrieval(conn, learner):
    gw = FakeGateway([birth_dose_json(conn)])
    out = run(conn, gw, Q, detail=True)[-1][1]
    assert out.state == "answered" and "chi tiết hơn" in gw.calls[0]["messages"][0]["content"]


def test_tier2_drops_claims_the_checker_rejects(conn, learner, monkeypatch):
    monkeypatch.setitem(settings()["postcheck"], "tier2_enabled", True)
    gw = FakeGateway([birth_dose_json(conn), '{"verdicts": [{"i": 0, "verdict": "no"}]}'])
    out = run(conn, gw, Q)[-1][1]
    assert out.state == "insufficient_evidence" and [c["task"] for c in gw.calls] == ["answer", "check"]


def test_tier2_keeps_supported_claims(conn, learner, monkeypatch):
    monkeypatch.setitem(settings()["postcheck"], "tier2_enabled", True)
    gw = FakeGateway([birth_dose_json(conn), '{"verdicts": [{"i": 0, "verdict": "yes"}]}'])
    assert run(conn, gw, Q)[-1][1].state == "answered"


def test_no_prediction_words_in_any_outcome(conn, learner):  # safety suite
    for q in [Q, "Tôi có đỗ kỳ thi không?", "Dự đoán điểm thi của tôi"]:
        out = run(conn, FakeGateway([birth_dose_json(conn)] * 2), q)[-1][1]
        assert not re.search(r"(dự đoán|xác suất đỗ|khả năng đỗ|điểm dự kiến)", out.text, re.I)


def test_explain_grounds_on_item_sources_and_cites_them(conn, learner):
    question = approved_question(conn, "q-dt-01")
    text = conn.execute("select text from passage where id='dt-p01'").fetchone()["text"]
    quote = "50 ÷ 2.000 = 0,025 = 2,5%"
    assert quote in text
    answer = ('{"evidence":[{"passage_id":"dt-p01","quote":"%s"}],"claims":[{"text":"Bạn chọn 5%%, tức là lấy '
              '50 ÷ 1.000; mẫu số đúng là 2.000 dân nên kết quả là 2,5%%.","passage_ids":["dt-p01"]}]}' % quote)
    gw = FakeGateway([answer])
    ev = both(prepare_explain(conn, question, chosen="b"), gw)
    assert [(e[1]["kind"], e[1]["status"]) for e in ev if e[0] == "step"] == [
        ("get_item", "running"), ("get_item", "done"), ("read", "running"), ("read", "done"),
        ("check", "running"), ("check", "done")]
    out = ev[-1][1]
    assert out.state == "answered" and out.citations[0]["passage_id"] == "dt-p01" and out.citations[0]["page"] == 58
    call = gw.calls[0]
    assert call["task"] == "tutor" and "[dt-p01]" in call["messages"][0]["content"]
    assert "Một xã có 2.000 dân" in call["messages"][0]["content"]


def test_claim_predicting_exam_outcome_is_removed(conn, learner):  # FR-LRN-26
    predicted = birth_dose_json(conn).replace(
        "được tiêm trong vòng 24 giờ đầu sau sinh.", "được tiêm trong vòng 24 giờ; khả năng đỗ của bạn là cao.")
    out = run(conn, FakeGateway([predicted]), Q)[-1][1]
    assert out.state == "insufficient_evidence"


def test_valid_json_of_the_wrong_shape_is_insufficient_not_a_crash(conn, learner):  # Review Focus 3
    for bad in ['{"claims": 5}', '{"evidence": true, "claims": [{"text": "x", "passage_ids": 5}]}',
                '{"evidence": [1, "a"], "claims": ["x", null]}']:
        out = run(conn, FakeGateway([bad]), Q)[-1][1]
        assert out.state == "insufficient_evidence"


OUT_OF_CORPUS = [  # safety suite: five out-of-corpus prompts end as insufficient_evidence
    "Phác đồ hoá trị ung thư phổi giai đoạn III",
    "Thủ đô của Pháp là gì?",
    "Cách nấu phở bò",
    "Giá vàng hôm nay?",              # passes the keyword gate: the model must say insufficient
    "HIV lây qua đường nào?",         # a listed disease, but no passage says how it spreads
]


@pytest.mark.parametrize("q", OUT_OF_CORPUS)
def test_out_of_corpus_prompts_end_as_insufficient_evidence(conn, learner, q):
    gw = FakeGateway(lambda task, messages: '{"insufficient": true}')
    out = run(conn, gw, q)[-1][1]
    assert out.state == "insufficient_evidence" and out.text == INSUFFICIENT_COPY and out.citations == []


# ---- the steps a turn reports (phase 7A) ---------------------------------------------------------

def test_the_stages_report_themselves_in_the_order_they_run(conn, learner):
    events = list(prepare_answer(conn, Q))
    assert [(e[1]["kind"], e[1]["status"]) for e in events if e[0] == "step"] == [
        ("lookup_glossary", "running"), ("lookup_glossary", "done"), ("search", "running"), ("search", "done"),
        ("read", "running"), ("read", "done")]
    labels = {e[1]["kind"]: e[1]["label_vi"] for e in events if e[0] == "step" and e[1]["status"] == "done"}
    documents = conn.execute("select count(*) c from document").fetchone()["c"]
    assert labels["lookup_glossary"] == "Tra thuật ngữ: viêm gan B" and labels["search"] == f"Đã tìm trong {documents} tài liệu"
    assert labels["read"].startswith("Đã đọc: Lịch tiêm chủng mở rộng tr. 8")
    kind, prepared = events[-1]
    assert kind == "prepared" and prepared.outcome is None and prepared.passages and [s.id for s in prepared.steps] == ["s1", "s2", "s3"]
    out = list(generate(FakeGateway([birth_dose_json(conn)]), prepared))
    assert [e[0] for e in out] == ["status", "status", "step", "step", "done"]
    outcome = out[-1][1]
    assert (outcome.state, outcome.claims_checked, outcome.claims_removed, outcome.notice) == ("answered", 1, 0, None)
    assert out[3][1] == {"id": "s4", "kind": "check", "label_vi": "Đã kiểm tra 1 nhận định", "status": "done"}
    assert outcome.cited_competencies == ["CI-04"] and [s.kind for s in prepared.steps][-1] == "check"


def test_a_question_without_a_glossary_term_looks_nothing_up(conn, learner):
    events = list(prepare_answer(conn, "Trẻ sơ sinh được tiêm những gì?"))
    assert "lookup_glossary" not in [e[1]["kind"] for e in events if e[0] == "step"]


def test_a_search_limited_to_a_hoc_phan_says_so(conn, learner):
    events = list(prepare_answer(conn, Q, module_id="g1"))
    search = next(e[1] for e in events if e[0] == "step" and e[1]["kind"] == "search")
    assert search["label_vi"] == "Đang tìm trong học phần Sức khỏe quần thể và dự phòng"


def test_a_claim_the_check_removes_is_counted_and_said(conn, learner):
    good = json.loads(birth_dose_json(conn).strip("`").removeprefix("json"))
    good["claims"].append({"text": "Trẻ cần tiêm nhắc lại sau 99 tháng.", "passage_ids": ["tc-p02"]})   # a number the passage does not give
    outcome = run(conn, FakeGateway([json.dumps(good, ensure_ascii=False)]), Q)[-1][1]
    assert (outcome.state, outcome.claims_checked, outcome.claims_removed) == ("answered", 2, 1)
    assert outcome.notice == "Đã bỏ 1 ý vì không tìm được nguồn trong giáo trình." and "99" not in outcome.text


def test_an_answer_that_does_not_survive_keeps_its_counts(conn, learner):
    outcome = run(conn, FakeGateway([birth_dose_json(conn, hours="48 giờ")]), Q)[-1][1]
    assert (outcome.state, outcome.claims_checked, outcome.claims_removed) == ("insufficient_evidence", 1, 1)


def test_a_declined_question_runs_no_stage(conn, learner):
    events = list(prepare_answer(conn, "Con tôi sốt 39 độ nên uống thuốc gì?"))
    assert [e[0] for e in events] == ["prepared"] and events[0][1].outcome.state == "declined" and events[0][1].steps == []


def test_nothing_found_reports_the_search_and_nothing_more(conn, learner):
    events = list(prepare_answer(conn, "Phác đồ hoá trị ung thư phổi giai đoạn III"))
    assert [e[1]["kind"] for e in events if e[0] == "step"] == ["search", "search"]
    assert events[-1][1].outcome.state == "insufficient_evidence" and [s.kind for s in events[-1][1].steps] == ["search"]
