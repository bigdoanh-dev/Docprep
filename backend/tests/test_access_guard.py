"""Every /v1 route sits behind a token, a role and, for learners, the service consent."""
import re

import pytest

from app.main import create_app
from tests.contract.operations import v1_operations

PROTECTED = [(m, p, r) for m, p, r in v1_operations(create_app("mock")) if r.openapi_extra["x-roles"] != ["public"]]
IDS = [f"{m} {p}" for m, p, _ in PROTECTED]


def url(path):
    return re.sub(r"\{[^}]+\}", "1", path)


def let_in(response) -> bool:
    """The guard let the request through, whatever the route then answered."""
    return response.status_code not in (401, 403)


@pytest.mark.parametrize("method,path,route", PROTECTED, ids=IDS)
def test_every_protected_operation_needs_a_token(real_client, method, path, route):
    r = real_client.request(method, url(path))
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated", r.text


@pytest.mark.parametrize("header", ["", "Bearer", "Bearer ", "Basic abc", "at_notatoken", "Bearer at_notatoken"])
def test_a_malformed_or_unknown_authorization_header_is_a_401(api, header):
    r = api.get("/v1/me", headers={"Authorization": header})
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"


def test_a_valid_token_reaches_the_route(api, learner_headers):
    assert let_in(api.get("/v1/me", headers=learner_headers))


def test_an_expired_token_says_so(api, learner_headers, clock):
    clock.advance(minutes=31)
    r = api.get("/v1/me", headers=learner_headers)
    assert r.status_code == 401 and r.json()["error"]["code"] == "token_expired"


def test_a_refresh_token_is_not_an_access_token(api, conn, learner, clock):
    from app.services.auth import issue_tokens
    issued = issue_tokens(conn, "learner", learner["id"], clock())
    conn.commit()
    r = api.get("/v1/me", headers={"Authorization": f"Bearer {issued.refresh_token}"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"


@pytest.mark.parametrize("change", ["update learner set active = false", "delete from learner"])
def test_a_token_whose_learner_is_gone_is_a_401_not_a_500(api, conn, learner_headers, change):
    conn.execute(change)
    conn.commit()
    r = api.get("/v1/me", headers=learner_headers)
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"


def test_a_learner_cannot_call_the_review_workbench(api, consented_headers):
    r = api.get("/v1/review/queue", headers=consented_headers)
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"


def test_a_reviewer_cannot_call_learner_or_admin_routes(api, staff_headers):
    headers = staff_headers("reviewer")
    assert api.get("/v1/home", headers=headers).json()["error"]["code"] == "forbidden"
    assert api.post("/v1/admin/users/import/1/confirm", headers=headers).json()["error"]["code"] == "forbidden"
    assert let_in(api.get("/v1/review/queue", headers=headers))


def test_an_admin_can_call_review_and_admin_routes(api, staff_headers):
    headers = staff_headers("admin")
    assert let_in(api.get("/v1/review/queue", headers=headers))
    assert let_in(api.post("/v1/admin/users/import/1/confirm", headers=headers))


def test_the_consent_gate_closes_learner_routes_until_consent(api, conn, learner, learner_headers, clock):
    from tests.conftest import _give_service_consent
    r = api.get("/v1/home", headers=learner_headers)
    assert r.status_code == 403 and r.json()["error"]["code"] == "consent_required"
    _give_service_consent(conn, learner["id"], clock())
    conn.commit()
    assert let_in(api.get("/v1/home", headers=learner_headers))


@pytest.mark.parametrize("method,path", [
    ("GET", "/v1/me"), ("GET", "/v1/consent/current"), ("GET", "/v1/me/data"), ("POST", "/v1/auth/logout")])
def test_account_and_consent_routes_stay_open_before_consent(api, learner_headers, method, path):
    assert let_in(api.request(method, path, headers=learner_headers))


def test_staff_are_never_asked_for_consent(api, staff_headers):
    assert let_in(api.get("/v1/review/queue", headers=staff_headers("reviewer")))


def test_mock_mode_asks_for_no_token(mock_client):
    assert mock_client.get("/v1/home").status_code == 200
