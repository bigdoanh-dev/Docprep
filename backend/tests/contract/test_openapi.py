"""openapi.yaml is generated from the code and must never drift from it."""
import yaml

from app.main import create_app
from app.openapi import OPENAPI_PATH, build_openapi, dump_openapi


def test_committed_file_matches_the_code():
    committed = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    assert committed == build_openapi(create_app("mock")), "run: python -m app.cli export-openapi"


def test_spec_has_bearer_security_and_no_legacy_paths():
    spec = build_openapi(create_app("mock"))
    assert spec["components"]["securitySchemes"]["bearer"] == {"type": "http", "scheme": "bearer"}
    assert all(p.startswith("/v1/") for p in spec["paths"])


def test_dump_keeps_vietnamese_readable_and_uses_lf():
    text = dump_openapi({"info": {"title": "Ôn thi năng lực Y học dự phòng"}})
    assert "Ôn thi năng lực Y học dự phòng" in text
    assert "\\u" not in text and "\r" not in text


def test_export_writes_utf8_bytes(tmp_path, monkeypatch):
    import app.cli as cli
    target = tmp_path / "openapi.yaml"
    monkeypatch.setattr(cli, "OPENAPI_PATH", target)
    cli.main(["export-openapi"])
    raw = target.read_bytes()
    assert b"\r\n" not in raw
    raw.decode("utf-8")
