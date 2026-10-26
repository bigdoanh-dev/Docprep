"""The queue in front of the model: a turn that has to wait is told its real place, and only then."""
import time
from threading import Thread, Timer

from app.api.streams import stream_events
from app.config import settings
from app.schemas.chat import StatusEvent
from app.services import chat as chat_service
from tests.conftest import birth_dose_json, sse_events

Q = "Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?"
BUSY = "Hệ thống đang bận. Vui lòng thử lại sau ít phút."
UNANSWERED = "Chưa trả lời được câu hỏi này lúc này."           # the turn was not answered: it says nothing about the documents


def release_once_someone_waits(slots, waiting: int = 1) -> None:
    """Free a slot as soon as `waiting` turns stand in line, however slow the machine is."""
    def run():
        deadline = time.monotonic() + 30
        while slots.waiting() < waiting and time.monotonic() < deadline:
            time.sleep(0.02)
        slots.release()
    Thread(target=run, daemon=True).start()


def until(condition, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "condition not met in time"
        time.sleep(0.05)


def ask(client, text):
    sid = client.post("/v1/chat/sessions", json={}).json()["id"]
    r = client.post(f"/v1/chat/sessions/{sid}/messages", json={"text": text})
    assert r.status_code == 200, r.text
    return sid, sse_events(r.text)


def take_every_slot(client):
    slots = client.app.state.model_slots
    for _ in range(settings()["gateway"]["max_concurrent"]):
        assert list(slots.acquire(1)) == []
    return slots


def test_a_turn_that_has_to_wait_is_told_its_place(learner_api, conn, fake_gw):
    slots = take_every_slot(learner_api)
    fake_gw.responses = [birth_dose_json(conn)]
    release_once_someone_waits(slots)
    _sid, events = ask(learner_api, Q)
    queued = [d for e, d in events if e == "status" and d["status"] == "queued"]
    assert queued == [{"status": "queued", "position": 1}]
    StatusEvent.model_validate(queued[0])
    names = [(e, d.get("kind") or d.get("status")) for e, d in events]
    assert names.index(("status", "queued")) == 6 and names[7] == ("status", "answering")     # after the stages, before the model
    assert events[-1][1]["state"] == "answered"
    assert (slots.in_use(), slots.waiting()) == (3, 0)                                        # its own slot was given back


def test_a_turn_that_does_not_wait_says_nothing_of_a_queue(learner_api, conn, fake_gw):
    fake_gw.responses = [birth_dose_json(conn)]
    _sid, events = ask(learner_api, Q)
    assert not [d for e, d in events if e == "status" and d["status"] == "queued"]
    assert learner_api.app.state.model_slots.in_use() == 0


def test_an_answer_that_needs_no_model_does_not_queue(learner_api, fake_gw):
    take_every_slot(learner_api)
    _sid, declined = ask(learner_api, "Con tôi sốt 39 độ nên uống thuốc gì?")
    _sid, nothing = ask(learner_api, "Phác đồ hoá trị ung thư phổi giai đoạn III?")
    assert declined[-1][1]["state"] == "declined" and nothing[-1][1]["state"] == "insufficient_evidence"
    assert not [d for e, d in declined + nothing if e == "status"]


def test_when_the_wait_is_too_long_the_learner_is_told(learner_api, conn, fake_gw, monkeypatch):
    slots = take_every_slot(learner_api)
    monkeypatch.setitem(settings()["gateway"], "queue_timeout_s", 0.3)
    _sid, events = ask(learner_api, Q)
    answer, final = events[-2][1], events[-1][1]
    assert final["state"] == "insufficient_evidence" and answer["notice"] == BUSY and fake_gw.calls == []
    assert answer["text"] == UNANSWERED                                        # not "the documents do not cover it"
    assert (slots.in_use(), slots.waiting()) == (4, 0)                                        # it took no slot and left the line
    assert conn.execute("select notice from chat_message where role = 'assistant'").fetchone()["notice"] == BUSY


def test_the_slot_is_given_back_when_the_model_step_breaks(learner_api, fake_gw):
    def boom(task, messages):
        raise RuntimeError("unforeseen")

    fake_gw.responses = boom
    _sid, events = ask(learner_api, Q)
    assert events[-1][1]["state"] == "insufficient_evidence" and learner_api.app.state.model_slots.in_use() == 0


def test_a_stream_that_is_abandoned_while_queued_still_ends(learner_api, conn, fake_gw, learner, clock):
    app = learner_api.app
    slots = take_every_slot(learner_api)
    fake_gw.responses = [birth_dose_json(conn)]
    sid = learner_api.post("/v1/chat/sessions", json={}).json()["id"]
    stream = stream_events(app.state.pool.connection, lambda connect: chat_service.answer_events(
        connect, slots, fake_gw, learner, {"id": sid, "module_id": None}, Q, False, False, clock()))
    for chunk in stream:
        if "queued" in chunk:
            break
    release_once_someone_waits(slots)
    stream.close()                      # the client went away: the turn is finished anyway, unsent
    stored = "select state from chat_message where session_id = %s and role = 'assistant'"
    until(lambda: conn.execute(stored, (sid,)).fetchone() is not None)
    assert conn.execute(stored, (sid,)).fetchone()["state"] == "answered"
    until(lambda: (slots.waiting(), slots.in_use()) == (0, 3))


def test_dropping_a_queued_stream_does_not_hold_up_the_server(learner_api, conn, fake_gw, learner, clock, monkeypatch):
    """The server closes a dropped stream on its event loop: the rest of the turn must not run there."""
    app = learner_api.app
    slots = take_every_slot(learner_api)
    monkeypatch.setitem(settings()["gateway"], "queue_timeout_s", 4)
    fake_gw.responses = [birth_dose_json(conn)]
    sid = learner_api.post("/v1/chat/sessions", json={}).json()["id"]
    stream = stream_events(app.state.pool.connection, lambda connect: chat_service.answer_events(
        connect, slots, fake_gw, learner, {"id": sid, "module_id": None}, Q, False, False, clock()))
    for chunk in stream:
        if "queued" in chunk:
            break
    started = time.monotonic()
    stream.close()                                         # every slot is still taken
    assert time.monotonic() - started < 1.0                # closing returns at once; the turn goes on elsewhere
    slots.release()
    stored = "select state from chat_message where session_id = %s and role = 'assistant'"
    until(lambda: conn.execute(stored, (sid,)).fetchone() is not None)
    assert conn.execute(stored, (sid,)).fetchone()["state"] == "answered"


def test_a_full_line_is_told_at_once_that_the_system_is_busy(learner_api, conn, fake_gw, monkeypatch):
    take_every_slot(learner_api)
    monkeypatch.setitem(settings()["gateway"], "max_waiting", 0)
    monkeypatch.setitem(settings()["gateway"], "queue_timeout_s", 30)
    started = time.monotonic()
    _sid, events = ask(learner_api, Q)
    assert time.monotonic() - started < 10 and fake_gw.calls == []
    assert not [d for e, d in events if e == "status" and d["status"] == "queued"]
    assert (events[-2][1]["text"], events[-2][1]["notice"]) == (UNANSWERED, BUSY)
