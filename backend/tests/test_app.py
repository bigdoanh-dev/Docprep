"""App-level behaviour: the startup check. Commit timing is checked in test_chat_v1.py."""
import pytest
from fastapi.testclient import TestClient



def test_startup_fails_fast_when_the_database_is_unreachable():
    from app.main import create_app

    app = create_app("real", database_url="postgresql://demo:demo@localhost:1/none?connect_timeout=2")
    with pytest.raises(RuntimeError, match="docker compose"):
        with TestClient(app):
            pass
