import json
import threading
import time
import uuid
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import pytest
import psycopg
from app.application import create_app
from app.db import connect
from app.privacy import clean, validate_prompt
from app.gateway import GatewayError
from app.repo import turns
from app.api.turns import _submit
from app.chat.worker import utcnow
from app.phase_routes import combined_openapi


def parse(response):
    event, out = "", []
    for line in response.text.splitlines():
        if line.startswith("event:"): event = line[6:].strip()
        if line.startswith("data:"): out.append((event, json.loads(line[5:])))
    return out


def ask(c, text="Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?", key=None, sid=None):
    sid = sid or c.post("/v1/chat/sessions", json={}).json()["id"]
    return c.post(f"/v1/chat/sessions/{sid}/messages", json={"text": text},
                  headers={"Idempotency-Key": key or str(uuid.uuid4())})


def wait(predicate, seconds=8):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        value = predicate()
        if value: return value
        time.sleep(.05)
    raise AssertionError("condition timed out")


def test_partition_and_no_business_gateway():
    b, c = [create_app("mock", service=s) for s in ("business", "chat")]
    business, chat = b.openapi()["paths"], c.openapi()["paths"]
    assert "/v1/chat/suggestions/{suggestion_id}/accept" in business
    assert "/v1/items/{question_id}/hint" in chat
    assert not hasattr(b.state, "model_slots") and not hasattr(b.state, "worker")
    merged = combined_openapi()
    assert sum(len(v) for v in merged["paths"].values()) == 59
    assert not any(path in business and set(business[path]) & set(chat[path]) for path in chat)


def test_provider_requires_explicit_approval(monkeypatch):
    from app.phase_config import PhaseConfig
    monkeypatch.setenv("PHASE_MODEL_PROVIDER", "vllm")
    with pytest.raises(RuntimeError, match="unapproved"): PhaseConfig.load()
    monkeypatch.setenv("PHASE_MODEL_PROVIDER", "scripted")
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError): PhaseConfig.load()


def test_privacy():
    value = "a@example.org 0912345678 at_secret HV-000001 192.168.1.1 123456789012"
    assert "secret" not in clean(value) and "@" not in clean(value)
    with pytest.raises(GatewayError): validate_prompt("", [{"role": "user", "content": value}])


def test_logs_never_render_arbitrary_messages_or_exception_values():
    import logging
    from app.observability import MetadataFormatter
    record = logging.LogRecord('app.phase', logging.ERROR, '', 1, 'at_private_example', (),
                               (RuntimeError, RuntimeError('sensitive body'), None))
    rendered = MetadataFormatter().format(record)
    assert 'private_example' not in rendered and 'sensitive body' not in rendered
    assert json.loads(rendered)['event'] == 'runtime_event'
    create_app('mock', service='chat')
    for name in ('uvicorn.error', 'uvicorn.access', 'psycopg.pool', 'app.chat.worker'):
        handler = logging.getLogger(name).handlers[0]
        assert isinstance(handler.formatter, MetadataFormatter)
        assert handler.filter(record)
        data = json.loads(handler.formatter.format(record))
        assert data['service'] == 'chat' and data['instance']


def test_chat_commit_resume_idempotency_and_ownership(world):
    b, (c1, c2), fake, url = world
    sid = c1.post("/v1/chat/sessions", json={}).json()["id"]
    r = ask(c1, key="same", sid=sid)
    assert r.status_code == 200
    data = parse(r)
    assert data[-1][0] == "final" and any(e == "answer" for e, _ in data)
    assert sum(e == "answer" for e, _ in data) == 1
    tid = r.headers["x-turn-id"]
    repeated = ask(c2, key="same", sid=sid)
    assert repeated.headers["x-turn-id"] == tid and len(fake.calls) == 1
    assert ask(c2, text="khác", key="same", sid=sid).status_code == 409
    snapshot = c2.get(f"/v1/chat/turns/{tid}").json()
    assert snapshot["turn_status"] == "completed"
    resumed = c2.get(f"/v1/chat/turns/{tid}/events")
    assert parse(resumed)[-1][0] == "final"
    with connect(url) as conn:
        assert conn.execute("select count(*) n from chat_message where ai_turn_id=%s", (tid,)).fetchone()["n"] == 1
        assert conn.execute("select count(*) n from ai_model_call where ended_at is null").fetchone()["n"] == 0
    from tests.conftest import _give_service_consent
    # Anonymous reads cannot leak the turn; another learner also gets 404.
    assert c2.get(f"/v1/chat/turns/{tid}", headers={"Authorization": "Bearer invalid"}).status_code == 401
    with connect(url) as conn:
        from app.repo.learners import create
        from app.services.auth import issue_tokens
        lid = create(conn, "HV-OTHER", None, "student", "2027-03-15", .9, "Other")
        _give_service_consent(conn, lid, utcnow())
        token = issue_tokens(conn, "learner", lid, utcnow()).access_token
    for suffix in ("", "/events"):
        assert c2.get(f"/v1/chat/turns/{tid}{suffix}", headers={"Authorization": "Bearer " + token}).status_code == 404
    assert c2.delete(f"/v1/chat/turns/{tid}", headers={"Authorization": "Bearer " + token}).status_code == 404


def test_technical_failure_has_final_without_fabricated_answer(world):
    _, (c, _), fake, _ = world
    def broken(task, messages): raise GatewayError("provider unavailable")
    fake.responses = broken
    result = parse(ask(c))
    assert result[-1][0] == "final" and result[-1][1]["turn_status"] == "failed"
    assert result[-1][1]["state"] is None
    assert not any(e == "answer" for e, _ in result)


def test_cancel_running_and_one_active(world):
    _, (c1, c2), fake, url = world
    entered, release = threading.Event(), threading.Event()
    def blocked(task, messages):
        entered.set(); assert release.wait(8); return '{"insufficient":true}'
    fake.responses = blocked
    with ThreadPoolExecutor(1) as executor:
        running = executor.submit(ask, c1)
        assert entered.wait(5)
        try:
            tid = c2.get("/v1/chat/turns/active").json()["item"]["turn_id"]
            assert ask(c2).status_code == 409
            assert c2.delete(f"/v1/chat/turns/{tid}").json()["turn_status"] == "cancelled"
            with connect(url) as conn:
                assert conn.execute("select count(*) n from ai_model_call where ended_at is null").fetchone()["n"] == 1
        finally: release.set()
        assert parse(running.result())[-1][1]["turn_status"] == "cancelled"


def test_exam_blocks_every_ai_path(world):
    b, (c, _), _, _ = world
    sid = c.post("/v1/chat/sessions", json={}).json()["id"]
    form = b.get("/v1/exams").json()["items"][0]["id"]
    assert b.post(f"/v1/exams/{form}/attempts", json={}).status_code == 200
    for path, body in ((f"/v1/chat/sessions/{sid}/messages", {"text": "Tỷ lệ hiện mắc là gì?"}),
                       ("/v1/items/q-dt-01/hint", {}), ("/v1/items/q-dt-01/explain", {})):
        r = c.post(path, json=body)
        assert r.status_code == 409 and r.json()["error"]["code"] == "ai_during_exam"


def test_database_privileges(world):
    _, _, _, url = world
    with connect(url) as conn:
        conn.execute("set role phase_chat")
        conn.execute("select * from ai_turn")
        for query in ("select * from learner_identity", "update exam_attempt set score=0", "update card set suspended=true", "create table forbidden(x int)"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction(): conn.execute(query)
        conn.execute("reset role; set role phase_business")
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction(): conn.execute("select * from ai_model_call")


def test_redis_restart_rebuild_and_event_expiry(world):
    _, (c1, c2), _, _ = world
    r = ask(c1)
    tid = r.headers["x-turn-id"]
    coord = c1.app.state.admission
    coord.r.delete(coord.key("epoch"), coord.key("ready"))
    wait(lambda: coord.ready())
    coord.purge(tid)
    expired = c2.get(f"/v1/chat/turns/{tid}/events", headers={"Last-Event-ID": "1-0"})
    assert expired.status_code == 410
    assert c2.get(f"/v1/chat/turns/{tid}").json()["result"]["final"]["message_id"]
