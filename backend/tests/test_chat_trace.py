"""A chat turn shows its work: one step per stage that ran, kept with the answer; and the turn holds
no database connection while the model answers."""
from app.schemas.chat import ChatMessageList, FinalEvent, StepEvent
from tests.conftest import birth_dose_json, make_wrong_unit_answer, sse_events

Q = "Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?"


def ask(client, text, **extra):
    sid = client.post("/v1/chat/sessions", json={}).json()["id"]
    r = client.post(f"/v1/chat/sessions/{sid}/messages", json={"text": text, **extra})
    assert r.status_code == 200, r.text
    return sid, sse_events(r.text)


def test_the_stream_shows_each_stage_then_the_answer(learner_api, conn, fake_gw):
    fake_gw.responses = [birth_dose_json(conn)]
    sid, events = ask(learner_api, Q)
    names = [(e, d.get("kind") or d.get("status")) for e, d in events]
    assert names == [("step", "lookup_glossary"), ("step", "lookup_glossary"), ("step", "search"), ("step", "search"),
                     ("step", "read"), ("step", "read"), ("status", "answering"), ("status", "checking_sources"),
                     ("step", "check"), ("step", "check"), ("answer", None), ("final", None)]
    steps = [d for e, d in events if e == "step"]
    for d in steps:
        StepEvent.model_validate(d)
    assert [d["status"] for d in steps] == ["running", "done"] * 4 and [d["id"] for d in steps] == ["s1", "s1", "s2", "s2", "s3", "s3", "s4", "s4"]
    final = events[-1][1]
    FinalEvent.model_validate(final)
    assert final["state"] == "answered" and final["trace_summary"] == {"sources": 1, "claims_checked": 1, "claims_removed": 0}
    row = conn.execute("select trace, claims_checked, claims_removed from chat_message where role = 'assistant'").fetchone()
    assert [s["kind"] for s in row["trace"]] == ["lookup_glossary", "search", "read", "check"]
    assert all(s["status"] == "done" for s in row["trace"]) and row["trace"][2]["label_vi"].startswith("Đã đọc: Lịch tiêm chủng mở rộng tr. 8")
    assert (row["claims_checked"], row["claims_removed"]) == (1, 0)
    body = learner_api.get(f"/v1/chat/sessions/{sid}/messages").json()
    ChatMessageList.model_validate(body)
    assert body["items"][1]["trace_summary"] == final["trace_summary"] and body["items"][0]["trace_summary"] is None
    # a reopened conversation shows the same steps as the live one: their done form, as sent
    sent_done = [d for d in steps if d["status"] == "done"]
    assert body["items"][1]["trace"] == sent_done and body["items"][0]["trace"] == []
    assert [s["id"] for s in body["items"][1]["trace"]] == ["s1", "s2", "s3", "s4"]


def test_no_step_is_stored_for_a_stage_that_did_not_run(learner_api, conn, fake_gw):
    _sid, declined = ask(learner_api, "Con tôi sốt 39 độ nên uống thuốc gì?")              # declined: nothing ran
    _sid, nothing = ask(learner_api, "Phác đồ hoá trị ung thư phổi giai đoạn III?")        # nothing found: no read, no check
    assert [e for e, _ in declined] == ["answer", "final"] and declined[-1][1]["trace_summary"] is None
    assert [(e, d.get("kind")) for e, d in nothing] == [("step", "search"), ("step", "search"), ("answer", None), ("final", None)]
    rows = conn.execute("select state, trace from chat_message where role = 'assistant' order by id").fetchall()
    assert rows[0] == {"state": "declined", "trace": None}
    assert rows[1]["state"] == "insufficient_evidence" and [s["kind"] for s in rows[1]["trace"]] == ["search"]
    assert nothing[-1][1]["trace_summary"] is None and fake_gw.calls == []


def test_an_answer_that_lost_a_claim_says_so(learner_api, conn, fake_gw):
    import json
    good = json.loads(birth_dose_json(conn).strip("`").removeprefix("json"))
    good["claims"].append({"text": "Trẻ cần tiêm nhắc lại sau 99 tháng.", "passage_ids": ["tc-p02"]})
    fake_gw.responses = [json.dumps(good, ensure_ascii=False)]
    _sid, events = ask(learner_api, Q)
    answer, final = events[-2][1], events[-1][1]
    assert answer["notice"] == "Đã bỏ 1 ý vì không tìm được nguồn trong giáo trình." and "99" not in answer["text"]
    assert final["trace_summary"] == {"sources": 1, "claims_checked": 2, "claims_removed": 1}


def test_no_connection_is_held_while_the_model_answers(learner_api, conn, fake_gw):
    seen = {}

    def reply(task, messages):
        stats = learner_api.app.state.pool.get_stats()
        seen["checked_out"] = stats["pool_size"] - stats["pool_available"]
        return birth_dose_json(conn)

    fake_gw.responses = reply
    _sid, events = ask(learner_api, Q)
    assert events[-1][1]["state"] == "answered" and seen["checked_out"] == 0


def test_the_turn_is_stored_even_when_the_model_step_breaks(learner_api, conn, fake_gw):
    def boom(task, messages):
        raise RuntimeError("unforeseen")

    fake_gw.responses = boom
    _sid, events = ask(learner_api, Q)
    assert [e for e, _ in events][-2:] == ["answer", "final"] and events[-1][1]["state"] == "insufficient_evidence"
    assert events[-2][1]["notice"] == "Có lỗi xảy ra. Vui lòng thử lại." and events[-2][1]["text"] == "Chưa trả lời được câu hỏi này lúc này."
    row = conn.execute("select state, trace from chat_message where role = 'assistant'").fetchone()
    assert row["state"] == "insufficient_evidence" and [s["kind"] for s in row["trace"]] == ["lookup_glossary", "search", "read"]


def test_giai_thich_them_on_an_item_shows_its_own_steps(learner_api, conn, fake_gw):
    make_wrong_unit_answer(learner_api)
    quote = "50 ÷ 2.000 = 0,025 = 2,5%"
    fake_gw.responses = ['{"evidence":[{"passage_id":"dt-p01","quote":"%s"}],"claims":[{"text":"Mẫu số đúng là 2.000 dân nên '
                         'kết quả là 2,5%%.","passage_ids":["dt-p01"]}]}' % quote]
    events = sse_events(learner_api.post("/v1/items/q-dt-01/explain").text)
    assert [d["kind"] for e, d in events if e == "step" and d["status"] == "done"] == ["get_item", "read", "check"]
    assert events[-1][1]["state"] == "answered"
    assert [s["kind"] for s in conn.execute("select trace from chat_message where role = 'assistant'").fetchone()["trace"]] == [
        "get_item", "read", "check"]
