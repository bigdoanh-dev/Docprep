"""The connection pool and the request-scoped connection."""
import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from app.api.deps import Conn
from app.db import open_pool
from app.main import create_app
from tests.conftest import _test_conn, test_database_url


def test_an_unreachable_database_is_reported_with_the_command_to_run():
    with pytest.raises(RuntimeError, match="docker compose"):
        open_pool("postgresql://demo:demo@localhost:1/none?connect_timeout=2", 1, 2)


def test_rows_come_back_as_dicts_and_connections_are_reused(migrated):
    pool = open_pool(test_database_url(), 1, 2)
    try:
        with pool.connection() as c:
            first = c.execute("select pg_backend_pid() as pid").fetchone()["pid"]
        with pool.connection() as c:
            assert c.execute("select pg_backend_pid() as pid").fetchone()["pid"] == first
    finally:
        pool.close()


def _app_with(router: APIRouter) -> FastAPI:
    app = create_app("real", database_url=test_database_url())
    app.include_router(router)
    return app


def test_a_request_commits_before_the_response_and_rolls_back_on_error(conn):
    router = APIRouter()

    @router.post("/t/ok")
    def ok(c=Conn):
        c.execute("insert into organisation(code, name) values ('A', 'CSĐT A')")
        return {"ok": True}

    @router.post("/t/boom")
    def boom(c=Conn):
        c.execute("insert into organisation(code, name) values ('B', 'CSĐT B')")
        raise RuntimeError("unexpected")

    with TestClient(_app_with(router), raise_server_exceptions=False) as client:
        assert client.post("/t/ok").status_code == 200
        assert client.post("/t/boom").status_code == 500
    with _test_conn() as c:
        assert [r["code"] for r in c.execute("select code from organisation order by code")] == ["A"]


def test_mock_mode_opens_no_pool():
    with TestClient(create_app("mock")) as client:
        assert not hasattr(client.app.state, "pool")
