"""The tutor's "Gợi ý": before answering only, never during an exam, never the answer."""
import pytest

from app.gateway import GatewayError
from app.schemas.units import Hint
from app.services import practice

POINTER = "Hãy xem lại 2.1 Tỷ lệ hiện mắc trong Dịch tễ học cơ bản, trang 58."
GOOD = '{"hint": "Hãy xác định mẫu số trước."}'


def open_quiz_item(client) -> None:
    """u-dt-01, past the first card: the learner is on the quiz item of q-dt-01, unanswered."""
    client.get("/v1/units/u-dt-01/next")
    client.post("/v1/units/u-dt-01/advance", json={"unit_item_id": "u1-c1"})


def ask(client, question_id: str = "q-dt-01"):
    return client.post(f"/v1/items/{question_id}/hint")


def test_a_hint_from_the_model_is_shown_with_the_source(learner_api, fake_gw, conn):
    open_quiz_item(learner_api)
    fake_gw.responses = [GOOD]
    r = ask(learner_api)
    assert r.status_code == 200, r.text
    Hint.model_validate(r.json())
    assert r.json()["text"] == "Hãy xác định mẫu số trước." and r.json()["citations"][0]["passage_id"] == "dt-p01"
    assert r.json()["generated"] is True                                      # a model wrote it: the screen marks it as AI
    call = fake_gw.calls[0]
    assert (call["task"], call["prompt_version"]) == ("hint", "hint-v1")
    message = call["messages"][0]["content"]
    assert "Một xã có 2.000 dân" in message and all(text in message for text in ("2,5%", "5%", "0,25%", "25%"))
    asked, sources = message.split("\n\nPassages:")
    # the question as the learner sees it: no rationale, no explanation, nothing marking the answer
    assert "50 ÷ 2.000" not in asked and "is_correct" not in asked and "đúng" not in asked.lower()
    assert "[dt-p01]" in sources
    row = conn.execute("select m.text, m.state, m.prompt_version, m.model_version, m.corpus_version, s.kind "
                       "from chat_message m join chat_session s on s.id = m.session_id where m.role = 'assistant'").fetchone()
    assert row == {"text": "Hãy xác định mẫu số trước.", "state": "answered", "prompt_version": "hint-v1",
                   "model_version": "fake", "corpus_version": "demo-2026-10-09", "kind": "tutor"}
    assert learner_api.get("/v1/chat/sessions").json()["items"] == []         # not in the learner's chat list
    assert conn.execute("select count(*) c from activity_event where kind = 'chat_turn'").fetchone()["c"] == 1


@pytest.mark.parametrize("reply", [
    '{"hint": "Đáp án là 2,5%."}',                       # gives the answer
    '{"hint": "Hãy chọn phương án A."}',                 # names an option
    '{"insufficient": true}',
    "Mình nghĩ bạn nên xem lại mẫu số.",                 # not JSON
    '{"hint": "%s"}' % ("x" * 500),                      # too long
    '{"hint": ""}',
])
def test_any_other_reply_is_replaced_by_a_pointer_to_the_source(learner_api, fake_gw, conn, reply):
    open_quiz_item(learner_api)
    fake_gw.responses = [reply, reply]                   # the JSON helper is not used here, but a retry must not crash
    r = ask(learner_api)
    assert r.status_code == 200 and r.json()["text"] == POINTER and r.json()["citations"][0]["page"] == 58
    assert r.json()["generated"] is False                                     # written by code: no AI mark
    assert conn.execute("select state from chat_message where role = 'assistant'").fetchone()["state"] == "insufficient_evidence"


def test_a_model_that_cannot_be_reached_still_gives_the_pointer(learner_api, fake_gw):
    def down(task, messages):
        raise GatewayError("timeout")

    open_quiz_item(learner_api)
    fake_gw.responses = down
    assert ask(learner_api).json()["text"] == POINTER


def test_no_hint_once_the_question_is_answered_or_when_it_is_not_in_progress(learner_api, fake_gw):
    r = ask(learner_api)                                 # nothing opened yet
    assert r.status_code == 409 and r.json()["error"] == {
        "code": "hint_unavailable", "message_vi": "Gợi ý chỉ có trước khi bạn trả lời câu hỏi.", "details": None}
    open_quiz_item(learner_api)
    learner_api.post("/v1/units/u-dt-01/responses", json={"unit_item_id": "u1-q1", "chosen": "a"})
    assert ask(learner_api).status_code == 409
    assert ask(learner_api, "q-dt-02").status_code == 409                    # a later item of the unit: not the current one
    assert ask(learner_api, "q-nope").json()["error"]["code"] == "question_not_found"
    assert fake_gw.calls == []


def test_no_hint_during_an_exam(learner_api, fake_gw, clock):
    open_quiz_item(learner_api)
    conn_question = "q-dt-07"                             # in de-thi-thu-1
    attempt = learner_api.post("/v1/exams/de-thi-thu-1/attempts", json={}).json()
    r = ask(learner_api, conn_question)
    assert r.status_code == 409 and r.json()["error"]["message_vi"] == "Không có gợi ý trong khi làm bài thi."
    assert fake_gw.calls == []
    learner_api.post(f"/v1/attempts/{attempt['attempt_id']}/submit")
    assert ask(learner_api, conn_question).json()["error"]["message_vi"] == "Gợi ý chỉ có trước khi bạn trả lời câu hỏi."


def test_a_question_waiting_in_a_practice_set_can_have_a_hint(learner_api, fake_gw, conn, learner, clock):
    built = practice.build(conn, learner, "session", "FND", 1, False, clock())
    conn.commit()
    fake_gw.responses = [GOOD, GOOD]
    first = built["question_ids"][0]
    assert ask(learner_api, first).status_code == 200
    learner_api.post(f"/v1/practice-sets/{built['id']}/responses", json={"question_id": first, "chosen": "a"})
    assert ask(learner_api, first).status_code == 409
    learner_api.post(f"/v1/practice-sets/{built['id']}/complete")
    assert ask(learner_api, built["question_ids"][1]).status_code == 409      # the set is closed


def test_the_prompt_and_the_log_carry_no_name(learner_api, fake_gw, conn):
    open_quiz_item(learner_api)
    fake_gw.responses = [GOOD]
    ask(learner_api)
    call = fake_gw.calls[0]
    for secret in ("Minh", "HV-DEMO"):
        assert secret not in call["system"] and secret not in call["messages"][0]["content"]
    assert conn.execute("select learner_pid from chat_session").fetchone()["learner_pid"] == "HV-DEMO-001"


def test_another_learner_cannot_use_my_open_question(api, learner_api, fake_gw, tokens_for_new_learner):
    open_quiz_item(learner_api)
    assert api.post("/v1/items/q-dt-01/hint", headers=tokens_for_new_learner()).status_code == 409
    assert fake_gw.calls == []


def test_mock_mode_still_serves_the_example(mock_client):
    assert mock_client.post("/v1/items/q-dt-01/hint").status_code == 200
