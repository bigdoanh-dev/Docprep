"""Rules that hold across the whole contract."""
import re

import pytest
from pydantic import ValidationError

from app.main import create_app
from app.openapi import OPENAPI_PATH, build_openapi
from app.schemas.review import ReviewDecisionRequest
from tests.contract.operations import EXPECTED, IMPLEMENTED

# No screen or payload may predict an exam outcome (FR-LRN-26).
PREDICTION = re.compile(
    r"dự đoán điểm|xác suất đỗ|khả năng đỗ|khả năng đậu|điểm dự kiến|chắc chắn đỗ|tỷ lệ đỗ|"
    r"pass probability|predicted score|pass line", re.IGNORECASE)

IDEMPOTENT = {
    ("post", "/v1/units/{unit_id}/responses"),
    ("post", "/v1/session/today/practice/responses"),
    ("post", "/v1/practice-sets/{set_id}/responses"),
    ("put", "/v1/attempts/{attempt_id}/answers/{question_id}"),
    ("post", "/v1/cards/{card_id}/reviews"),
}


def test_the_contract_has_all_55_operations_and_only_those_can_be_implemented():
    assert len(EXPECTED) == 55
    assert IMPLEMENTED <= EXPECTED


def test_no_prediction_wording_anywhere_in_the_contract():
    assert not PREDICTION.search(OPENAPI_PATH.read_text(encoding="utf-8"))


def test_idempotency_key_is_declared_exactly_where_the_spec_says():
    spec = build_openapi(create_app("mock"))
    declared = {
        (method, path)
        for path, ops in spec["paths"].items() for method, op in ops.items()
        if any(p["name"].lower() == "idempotency-key" for p in op.get("parameters", []))
    }
    assert declared == IDEMPOTENT


def test_every_protected_operation_documents_401_and_403():
    spec = build_openapi(create_app("mock"))
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            if op["x-roles"] != ["public"]:
                assert {"401", "403"} <= set(op["responses"]), f"{method} {path}"


@pytest.mark.parametrize("decision", ["revise", "reject"])
def test_a_decision_other_than_pass_needs_a_comment(decision):
    with pytest.raises(ValidationError, match="Cần ghi nhận xét"):
        ReviewDecisionRequest(version=1, round=1, decision=decision, comment="  ")


def test_a_pass_needs_no_comment():
    assert ReviewDecisionRequest(version=1, round=2, decision="pass").comment is None


PHASE_3 = {
    ("POST", "/v1/auth/activate"), ("POST", "/v1/auth/staff/login"), ("POST", "/v1/auth/refresh"),
    ("POST", "/v1/auth/logout"), ("GET", "/v1/consent/current"), ("POST", "/v1/consent"),
    ("DELETE", "/v1/consent"), ("GET", "/v1/me"), ("PATCH", "/v1/me"), ("GET", "/v1/me/data"), ("DELETE", "/v1/me"),
}
PHASE_4 = {
    ("GET", "/v1/home"), ("GET", "/v1/modules"), ("GET", "/v1/modules/{module_id}"),
    ("GET", "/v1/units/{unit_id}/next"), ("POST", "/v1/units/{unit_id}/responses"),
    ("POST", "/v1/units/{unit_id}/advance"), ("POST", "/v1/items/{question_id}/explain"),
    ("GET", "/v1/exams"), ("POST", "/v1/exams/{form_id}/attempts"), ("GET", "/v1/attempts/{attempt_id}"),
    ("PUT", "/v1/attempts/{attempt_id}/answers/{question_id}"), ("POST", "/v1/attempts/{attempt_id}/submit"),
    ("GET", "/v1/attempts/{attempt_id}/results"), ("GET", "/v1/attempts/{attempt_id}/items/{question_id}"),
    ("GET", "/v1/cards/due"), ("POST", "/v1/cards/{card_id}/reviews"),
    ("POST", "/v1/chat/sessions"), ("GET", "/v1/chat/sessions"), ("GET", "/v1/chat/sessions/{session_id}/messages"),
    ("POST", "/v1/chat/sessions/{session_id}/messages"), ("GET", "/v1/passages/{passage_id}"),
}


PHASE_5A = {
    ("GET", "/v1/session/today"), ("GET", "/v1/session/today/practice"),
    ("POST", "/v1/session/today/practice/responses"), ("POST", "/v1/session/today/practice/complete"),
    ("GET", "/v1/practice-sets/{set_id}"), ("POST", "/v1/practice-sets/{set_id}/responses"),
    ("POST", "/v1/practice-sets/{set_id}/complete"),
}


PHASE_5B = {
    ("GET", "/v1/progress/skills"), ("GET", "/v1/progress/rhythm"), ("GET", "/v1/decks"),
    ("PATCH", "/v1/cards/{card_id}"), ("POST", "/v1/items/{question_id}/hint"),
}


def test_the_operations_of_phases_3_to_7_are_implemented():
    assert (len(PHASE_4), len(PHASE_5A), len(PHASE_5B)) == (21, 7, 5)
    assert IMPLEMENTED == PHASE_3 | PHASE_4 | PHASE_5A | PHASE_5B | PHASE_6 | PHASE_7 and len(IMPLEMENTED) == 48


PHASE_6 = {("GET", "/v1/admin/dashboard/overview"), ("GET", "/v1/admin/dashboard/export")}
PHASE_7 = {("POST", "/v1/chat/suggestions/{suggestion_id}/accept"), ("POST", "/v1/messages/{message_id}/rating")}

CONFLICTS = {
    ("post", "/v1/chat/suggestions/{suggestion_id}/accept"): ["nothing_to_practise", "tomorrow_taken"],
    ("post", "/v1/chat/sessions"): ["not_answered", "tutor_unavailable"],
    ("post", "/v1/consent"): ["consent_version_outdated"],
    ("post", "/v1/items/{question_id}/hint"): ["hint_unavailable"],
    ("post", "/v1/practice-sets/{set_id}/responses"): ["set_completed"],
    ("post", "/v1/session/today/practice/responses"): ["set_completed"],
    ("post", "/v1/exams/{form_id}/attempts"): ["no_attempts_left", "form_unavailable"],
    ("get", "/v1/attempts/{attempt_id}/results"): ["attempt_open"],
    ("get", "/v1/attempts/{attempt_id}/items/{question_id}"): ["attempt_open"],
    ("put", "/v1/attempts/{attempt_id}/answers/{question_id}"): ["attempt_closed"],
    ("post", "/v1/units/{unit_id}/responses"): ["not_current_item"],
    ("post", "/v1/items/{question_id}/explain"): ["not_answered"],
}


def test_every_409_a_route_returns_is_documented_with_its_codes():
    paths = build_openapi(create_app("mock"))["paths"]
    for (method, path), codes in CONFLICTS.items():
        description = paths[path][method]["responses"]["409"]["description"]
        assert all(f"`{code}`" in description for code in codes), f"{method} {path}: {description}"
    documented = {(m, p) for p, ops in paths.items() for m, op in ops.items() if "409" in op["responses"]}
    assert ("post", "/v1/attempts/{attempt_id}/submit") not in documented
