import json

import pytest
import yaml

from app.api import deps
from app.config import BACKEND_DIR, model_provider
from app.scripted_gateway import ScriptedGateway, scenarios
from tests.conftest import sse_events


@pytest.mark.parametrize("environment", ["production", "staging", ""])
def test_scripted_cannot_run_outside_explicit_dev_test(monkeypatch, environment):
    monkeypatch.setenv("APP_ENV", environment)
    monkeypatch.setenv("MODEL_PROVIDER", "scripted")
    with pytest.raises(RuntimeError):
        model_provider()
    with pytest.raises(RuntimeError):
        ScriptedGateway()


def test_every_scripted_quote_really_belongs_to_the_demo_corpus():
    docs = yaml.safe_load((BACKEND_DIR / "seed/content/documents.yaml").read_text(encoding="utf-8"))
    passages = {p["id"]: p["text"] for d in docs for p in d["passages"]}
    for scenario in scenarios():
        assert scenario["quote"] in passages[scenario["passage_id"]]


@pytest.mark.parametrize("question,expected", [
    ("Tỷ lệ hiện mắc là gì?", "answered"),
    ("Tỷ lệ mới mắc là gì?", "answered"),
    ("Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?", "answered"),
    ("Giải thích máy tính lượng tử", "insufficient_evidence"),
    ("Tỷ lệ hiện mắc trong câu hỏi chưa có kịch bản", "insufficient_evidence"),
    ("Con tôi 3 tuổi đang sốt, tôi nên cho uống thuốc gì?", "declined"),
    ("Tỷ lệ mắc là gì?", "needs_clarification"),
])
def test_scripted_uses_real_pipeline_and_persists_without_network(learner_api, monkeypatch, question, expected):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("MODEL_PROVIDER", "scripted")
    def no_network(*args, **kwargs):
        raise AssertionError("The offline Alpha must not construct an external model client")
    monkeypatch.setattr("app.gateway.AnthropicGateway.__init__", no_network)
    deps.get_gateway.cache_clear()
    learner_api.app.dependency_overrides.pop(deps.get_gateway, None)
    try:
        sid = learner_api.post("/v1/chat/sessions", json={}).json()["id"]
        response = learner_api.post(f"/v1/chat/sessions/{sid}/messages", json={"text": question})
        assert response.status_code == 200
        events = sse_events(response.text)
        assert events[-1][0] == "final" and events[-1][1]["state"] == expected
        answer = next(data for name, data in events if name == "answer")
        if expected == "answered":
            assert answer["citations"]
            for citation in answer["citations"]:
                assert learner_api.get(f"/v1/passages/{citation['passage_id']}").status_code == 200
        history = learner_api.get(f"/v1/chat/sessions/{sid}/messages").json()["items"]
        assert [m["role"] for m in history] == ["user", "assistant"]
        assert history[-1]["state"] == expected
    finally:
        deps.get_gateway.cache_clear()


def test_scripted_does_not_use_a_fixture_when_its_source_is_missing(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    result = ScriptedGateway().complete("answer", "", [{"role": "user", "content":
        "Câu hỏi: Tỷ lệ hiện mắc là gì?\n\nPassages:\n[other] (other)\nA different document."}], "answer-v1")
    assert json.loads(result.text) == {"insufficient": True}


def test_alpha_seed_is_repeatable_and_keeps_existing_password_and_profile(conn, monkeypatch):
    from seed.alpha import run
    monkeypatch.setenv("APP_ENV", "test")
    run(conn, with_cohort=False)
    conn.execute("update learner set focus_module_ids = array['g2'] where pseudonym_id='HV-DEMO-001'")
    before = conn.execute("select email, password_hash from staff_user where email like '%@alpha.local' order by email").fetchall()
    run(conn, with_cohort=False)
    assert conn.execute("select email, password_hash from staff_user where email like '%@alpha.local' order by email").fetchall() == before
    assert conn.execute("select focus_module_ids from learner where pseudonym_id='HV-DEMO-001'").fetchone()["focus_module_ids"] == ["g2"]


def test_quiz_chat_unknown_question_does_not_reuse_an_unrelated_script(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    scenario = scenarios()[0]
    prompt = ("Câu hỏi: Một câu quiz\nCâu hỏi của học viên: Giải thích máy tính lượng tử\n\n"
              f"Passages:\n[{scenario['passage_id']}] (Nguồn demo)\n{scenario['quote']}")
    result = ScriptedGateway().complete("quiz_chat", "", [{"role": "user", "content": prompt}], "quiz-chat-v1")
    assert json.loads(result.text) == {"insufficient": True}
