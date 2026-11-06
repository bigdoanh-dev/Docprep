"""Dedicated disposable database and Redis namespace, never the demo or Alpha test DB."""
import os
import uuid
from pathlib import Path
from datetime import datetime, timezone
from contextlib import ExitStack
from urllib.parse import urlsplit
import pytest
from fastapi.testclient import TestClient
from app.application import create_app
from app.db import connect, migrate, truncate_all
from app.api import deps
from app.gateway import FakeGateway
from seed import run_seed


class PrivateDSN(str):
    def __repr__(self):
        return '<private phase1_test DSN>'


@pytest.fixture(scope="session")
def test_url():
    url = os.environ.get("PHASE_TEST_DATABASE_URL", "")
    if not url or urlsplit(url).path != "/phase1_test" or url == os.environ.get("DATABASE_URL"):
        raise RuntimeError("PHASE_TEST_DATABASE_URL must name the separate phase1_test database")
    with connect(url) as conn:
        conn.execute("drop schema if exists public cascade; create schema public")
    migrate(url)
    with connect(url) as conn:
        conn.execute((Path(__file__).resolve().parents[2] / "deploy" / "grants.sql").read_text())
    return PrivateDSN(url)


@pytest.fixture
def world(test_url, monkeypatch):
    monkeypatch.setenv("PHASE_REDIS_NAMESPACE", "test:" + uuid.uuid4().hex)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PHASE_MODEL_PROVIDER", "scripted")
    monkeypatch.setenv("PHASE_LEASE_SECONDS", "3")
    with connect(test_url) as conn:
        truncate_all(conn)
        run_seed(conn)
    business = create_app("real", test_url, service="business")
    chats = [create_app("real", test_url, service="chat") for _ in range(2)]
    fake = FakeGateway(lambda task, messages: '{"insufficient":true}')
    for app in chats:
        app.dependency_overrides[deps.get_gateway] = lambda: fake
    with ExitStack() as stack:
        b = stack.enter_context(TestClient(business))
        clients = [stack.enter_context(TestClient(app)) for app in chats]
        token = b.post("/v1/auth/activate", json={"code": "DEMO-0001"}).json()["access_token"]
        headers = {"Authorization": "Bearer " + token}
        b.headers.update(headers)
        text = b.get("/v1/consent/current").json()
        assert b.post("/v1/consent", json={"version": text["version"], "service": True, "research": False}).status_code == 200
        for c in clients:
            c.headers.update(headers)
        yield b, clients, fake, test_url
    # Only our own temporary namespace is removed, even when runtime Redis shares the server.
    from app.chat.admission import Admission
    from app.phase_config import PhaseConfig
    coord = Admission(PhaseConfig.load())
    keys = list(coord.r.scan_iter(match=coord.p + "*"))
    if keys:
        coord.r.delete(*keys)
    coord.close()
