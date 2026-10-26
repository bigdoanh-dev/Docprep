"""Rules every /v1 operation follows: declared roles, an example served in mock mode, 501 until real."""
import re

import pytest

from app.main import create_app
from app.schemas.base import example
from tests.contract.operations import BINARY, EXPECTED, FILES, IMPLEMENTED, SSE, v1_operations

APP = create_app("mock")
OPS = v1_operations(APP)
IDS = [f"{m} {p}" for m, p, _ in OPS]


def _url(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "1", path)


def _payload(method, path, route) -> dict:
    if (method, path) in FILES:
        return {"files": FILES[(method, path)]}
    if route.body_field is not None:
        return {"json": example(route.body_field.field_info.annotation).model_dump(mode="json")}
    return {}


def test_registered_operations_match_expected():
    assert {(m, p) for m, p, _ in OPS} == EXPECTED


@pytest.mark.parametrize("method,path,route", OPS, ids=IDS)
def test_route_declares_its_roles(method, path, route):
    roles = (route.openapi_extra or {}).get("x-roles")
    assert roles, f"{method} {path} has no x-roles"
    assert set(roles) <= {"public", "learner", "reviewer", "admin", "ministry_viewer"}


@pytest.mark.parametrize("method,path,route", OPS, ids=IDS)
def test_mock_mode_serves_the_example(method, path, route, mock_client):
    r = mock_client.request(method, _url(path), **_payload(method, path, route))
    assert r.status_code == 200, r.text
    if (method, path) in SSE:
        assert r.headers["content-type"].startswith("text/event-stream")
        assert "event: final" in r.text
    elif (method, path) in BINARY:
        assert r.headers["content-type"] == BINARY[(method, path)]
        assert r.content[:2] == b"PK"      # an .xlsx file is a zip archive
    else:
        assert r.json() == example(route.response_model).model_dump(mode="json")


@pytest.mark.parametrize("method,path,route", OPS, ids=IDS)
def test_real_mode_answers_501_until_implemented(method, path, route, real_client):
    if (method, path) in IMPLEMENTED:
        pytest.skip("implemented")
    # Signed in as the first role the route accepts: the guard lets the caller in, the stub answers.
    roles = route.openapi_extra["x-roles"]
    headers = {} if roles == ["public"] else real_client.role_headers[roles[0]]
    r = real_client.request(method, _url(path), headers=headers, **_payload(method, path, route))
    assert r.status_code == 501, r.text
    assert r.json()["error"]["code"] == "not_implemented"
