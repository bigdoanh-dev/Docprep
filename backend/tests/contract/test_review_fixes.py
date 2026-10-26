"""Findings of the phase 1 whole-branch review, each pinned by a test."""
import importlib.metadata
import re
import subprocess
import sys

import pytest
import yaml
from fastapi.testclient import TestClient

from app.config import BACKEND_DIR
from app.main import create_app
from app.openapi import OPENAPI_PATH, build_openapi
from app.schemas.base import Schema, example
from tests.contract.operations import FILES, v1_operations
from tests.contract.test_contract import _payload, _url

APP = create_app("mock")
SPEC = build_openapi(APP)
OPS = v1_operations(APP)
IDS = [f"{m} {p}" for m, p, _ in OPS]


def _resolve(schema: dict) -> tuple[str | None, dict]:
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        return name, SPEC["components"]["schemas"][name]
    return None, schema


def _sample(schema: dict) -> str:
    """A valid value for a query parameter, from its schema."""
    if schema.get("examples"):      # a string with a pattern says what a valid value looks like
        return str(schema["examples"][0])
    if "anyOf" in schema:
        schema = next(s for s in schema["anyOf"] if s.get("type") != "null")
    if "enum" in schema:
        return str(schema["enum"][0])
    if "const" in schema:
        return str(schema["const"])
    return {"integer": str(max(1, schema.get("minimum", 1))), "boolean": "true"}.get(schema.get("type"), "x")


# 1. Query parameters declared as integer enums rejected every value.
@pytest.mark.parametrize("method,path,route", OPS, ids=IDS)
def test_every_documented_query_parameter_is_accepted(method, path, route, mock_client):
    params = {p["name"]: _sample(p["schema"])
              for p in SPEC["paths"][path][method.lower()].get("parameters", []) if p["in"] == "query"}
    if not params:
        pytest.skip("no query parameters")
    r = mock_client.request(method, _url(path), params=params, **_payload(method, path, route))
    assert r.status_code == 200, r.text


# 2. The schema the server serves was not the contract.
def test_served_openapi_is_the_committed_contract(mock_client):
    assert mock_client.get("/openapi.json").json() == yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))


# 3. Stream operations also advertised a JSON 200.
@pytest.mark.parametrize("path", ["/v1/chat/sessions/{session_id}/messages", "/v1/items/{question_id}/explain"])
def test_stream_operations_advertise_only_an_event_stream(path):
    assert list(SPEC["paths"][path]["post"]["responses"]["200"]["content"]) == ["text/event-stream"]


# 4. app.schemas.auth could not be imported on its own (it imported the API layer).
@pytest.mark.parametrize("module", sorted(p.stem for p in (BACKEND_DIR / "app" / "schemas").glob("[a-z]*.py")))
def test_each_schema_module_imports_on_its_own(module):
    done = subprocess.run([sys.executable, "-c", f"import app.schemas.{module}"], cwd=BACKEND_DIR,
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr[-400:]


# 5. The error half of the contract was missing.
def test_the_errors_the_app_branches_on_are_documented():
    paths = SPEC["paths"]
    assert {"401", "429"} <= set(paths["/v1/auth/activate"]["post"]["responses"])
    assert {"401", "429"} <= set(paths["/v1/auth/staff/login"]["post"]["responses"])
    assert "401" in paths["/v1/auth/refresh"]["post"]["responses"]
    assert "409" in paths["/v1/attempts/{attempt_id}/answers/{question_id}"]["put"]["responses"]
    codes = SPEC["components"]["schemas"]["ErrorDetail"]["properties"]["code"]["description"]
    for code in ("invalid_request", "unauthenticated", "token_expired", "forbidden", "consent_required",
                 "not_found", "attempt_closed", "rate_limited", "not_implemented", "internal_error"):
        assert code in codes, code
    assert "consent_required" in SPEC["info"]["description"]
    assert "unknown fields" in SPEC["info"]["description"]


# 6a. Response objects were closed, making every later field a breaking change.
@pytest.mark.parametrize("method,path,route", OPS, ids=IDS)
def test_request_bodies_are_closed_and_responses_open(method, path, route):
    op = SPEC["paths"][path][method.lower()]
    body = op.get("requestBody", {}).get("content", {}).get("application/json")
    if body:
        assert _resolve(body["schema"])[1].get("additionalProperties") is False
    ok = op["responses"]["200"]["content"].get("application/json")
    if ok:
        assert _resolve(ok["schema"])[1].get("additionalProperties") is not False


def test_an_unknown_request_field_is_rejected(mock_client):
    r = mock_client.post("/v1/auth/activate", json={"code": "DEMO-0001", "surprise": 1})
    assert r.status_code == 422 and r.json()["error"]["details"]["fields"][0]["path"] == "body.surprise"


# 6b. Operation ids were FastAPI's path-derived defaults.
def test_operation_ids_are_short_and_unique():
    ids = [op["operationId"] for ops in SPEC["paths"].values() for op in ops.values()]
    assert len(ids) == len(set(ids)) == 55
    assert not [i for i in ids if "_v1_" in i or not re.fullmatch(r"[a-z][a-z0-9_]*", i)]


# 6c. Response fields the server always sends were not marked required.
@pytest.mark.parametrize("method,path,route", OPS, ids=IDS)
def test_every_response_field_is_required(method, path, route):
    ok = SPEC["paths"][path][method.lower()]["responses"]["200"]["content"].get("application/json")
    if not ok:
        pytest.skip("stream")
    name, schema = _resolve(ok["schema"])
    assert set(schema.get("required", [])) == set(schema["properties"]), name


def test_event_fields_are_required():
    for name in ("StatusEvent", "StepEvent", "AnswerEvent", "FinalEvent"):
        schema = SPEC["components"]["schemas"][name]
        assert set(schema["required"]) == set(schema["properties"]), name


def test_no_model_is_split_into_input_and_output_variants():
    """A model used both as a request body and inside a response gets two generated names; keep them separate."""
    assert not [name for name in SPEC["components"]["schemas"] if name.endswith(("-Input", "-Output"))]


# 7. Nothing pinned the libraries the generated file depends on.
@pytest.mark.parametrize("package", ["fastapi", "pydantic", "starlette"])
def test_contract_libraries_are_pinned_to_what_is_installed(package):
    pins = dict(line.strip().split("==") for line in (BACKEND_DIR / "requirements.txt").read_text().splitlines()
                if "==" in line)
    assert pins.get(package) == importlib.metadata.version(package)


# Spec §5: a test fails when any example does not validate against its own model.
def _schemas(cls=Schema):
    for sub in cls.__subclasses__():
        yield sub
        yield from _schemas(sub)


def test_every_example_validates_against_its_model():
    with_examples = [m for m in set(_schemas()) if (m.model_config.get("json_schema_extra") or {}).get("examples")]
    assert len(with_examples) >= 55
    for model in with_examples:
        example(model)


# "Error body, everywhere": an unexpected failure must not answer text/plain.
def test_an_unexpected_error_uses_the_error_body():
    app = create_app("mock")

    @app.get("/boom")
    def boom():
        raise RuntimeError("unexpected")

    r = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert r.status_code == 500
    assert r.json() == {"error": {"code": "internal_error", "message_vi": "Có lỗi xảy ra. Vui lòng thử lại.",
                                  "details": None}}


@pytest.mark.parametrize("value,expected", [("abc", 400), ("-5", 0), ("999999", 5000), ("0", 0), (None, 400)])
def test_mock_delay_is_parsed_and_clamped(monkeypatch, value, expected):
    from app.api.mock_chat import mock_delay_ms
    if value is None:
        monkeypatch.delenv("MOCK_STEP_DELAY_MS", raising=False)
    else:
        monkeypatch.setenv("MOCK_STEP_DELAY_MS", value)
    assert mock_delay_ms() == expected
