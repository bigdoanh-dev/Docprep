"""App modes, the error body, and the helpers every contract stub is built from."""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.base import Schema, example
from app.schemas.common import Ok


def test_mock_app_starts_without_database_env_or_model_key(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://none:none@localhost:1/none?connect_timeout=1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with TestClient(create_app("mock")) as c:
        health = c.get("/health").json()
        assert health["ok"] is True and health["mode"] == "mock"
        assert health["model_provider"] in ("scripted", "anthropic")
        assert isinstance(health["demo_content"], bool)


def test_mock_app_does_not_mount_legacy_routes(mock_client):
    assert mock_client.get("/home").status_code == 404


def test_real_app_serves_only_the_v1_api(real_client):
    assert real_client.get("/home").status_code == 404
    learner = real_client.role_headers["learner"]
    assert real_client.get("/v1/home", headers=learner).status_code == 200
    report = real_client.post("/v1/reports", json={"target_type": "question", "target_id": "q-dt-01",
                                                   "reason": "broken_item"}, headers=learner)
    assert report.status_code == 501                                              # a later phase


def test_unknown_path_uses_the_error_body(mock_client):
    r = mock_client.get("/v1/does-not-exist")
    assert r.status_code == 404
    assert r.json() == {"error": {"code": "not_found", "message_vi": "Không tìm thấy đường dẫn.", "details": None}}


def test_wrong_method_uses_the_error_body(mock_client):
    r = mock_client.delete("/health")
    assert r.status_code == 405
    assert r.json()["error"]["code"] == "method_not_allowed"


def test_invalid_body_in_mock_mode_names_the_failing_field(mock_client):
    r = mock_client.post("/v1/auth/activate", json={})
    assert r.status_code == 422
    error = r.json()["error"]
    assert error["code"] == "invalid_request"
    assert any(f["path"] == "body.code" and f["message"] for f in error["details"]["fields"])


def test_unknown_app_mode_is_refused():
    with pytest.raises(RuntimeError, match="APP_MODE"):
        create_app("staging")


def test_example_returns_a_validated_instance():
    assert example(Ok) == Ok(ok=True)


def test_example_names_the_model_when_missing():
    class Bare(Schema):
        x: int

    with pytest.raises(LookupError, match="Bare"):
        example(Bare)
