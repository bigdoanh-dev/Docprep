"""Consent, profile, the learner's own data, account deletion."""
from typing import Literal

from fastapi import APIRouter, Request

from app.api.access import Caller, access, conflict
from app.api.deps import Conn, Now
from app.api.stub import mock_example
from app.schemas.account import ConsentRequest, ConsentStatus, ConsentText, DeletionAccepted, Me, MePatch, MyData
from app.services import account as account_service

router = APIRouter(tags=["account"])
# A learner must reach consent and their own account before consenting, so these routes skip the gate.
LEARNER = access("learner", consent=False)


@router.get("/consent/current", response_model=ConsentText, summary="Current consent text and version", **LEARNER)
def get_consent_text(request: Request):
    return mock_example(request, ConsentText) or account_service.consent_text()


@router.post("/consent", response_model=ConsentStatus, summary="Record consent",
             **access("learner", consent=False, responses=conflict(
                 "`consent_version_outdated`: the texts changed since the client fetched them; show the current ones.")))
def give_consent(request: Request, body: ConsentRequest, conn=Conn, now=Now, principal=Caller):
    return mock_example(request, ConsentStatus) or account_service.give_consent(
        conn, principal.subject_id, body.version, body.service, body.research, now)


@router.delete("/consent", response_model=ConsentStatus, summary="Withdraw one consent", **LEARNER)
def withdraw_consent(request: Request, kind: Literal["service", "research"] = "research", conn=Conn, now=Now,
                     principal=Caller):
    return mock_example(request, ConsentStatus) or account_service.withdraw_consent(
        conn, principal.subject_id, kind, now)


@router.get("/me", response_model=Me, summary="Profile and settings", **LEARNER)
def get_me(request: Request, conn=Conn, principal=Caller):
    return mock_example(request, Me) or account_service.get_me(conn, principal.subject_id)


@router.patch("/me", response_model=Me, summary="Change profile or settings", **LEARNER)
def patch_me(request: Request, body: MePatch, conn=Conn, now=Now, principal=Caller):
    return mock_example(request, Me) or account_service.patch_me(
        conn, principal.subject_id, body.model_dump(exclude_unset=True), account_service.local_date(now))


@router.get("/me/data", response_model=MyData, summary="Export the learner's own data", **LEARNER)
def export_my_data(request: Request, conn=Conn, now=Now, principal=Caller):
    return mock_example(request, MyData) or account_service.export_data(conn, principal.subject_id, now)


@router.delete("/me", response_model=DeletionAccepted, summary="Request account deletion", **LEARNER)
def delete_me(request: Request, conn=Conn, now=Now, principal=Caller):
    return mock_example(request, DeletionAccepted) or account_service.delete_account(conn, principal, now)
