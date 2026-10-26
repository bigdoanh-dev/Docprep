"""Sign-in and tokens."""
from fastapi import APIRouter, Request

from app.api.access import ERROR, Caller, access, public
from app.api.deps import Conn, Now, client_ip
from app.api.stub import mock_example
from app.schemas.auth import ActivateRequest, RefreshRequest, StaffLoginRequest, TokenPair
from app.schemas.common import Ok
from app.services import auth as auth_service

router = APIRouter(tags=["auth"])
# 401 unauthenticated: wrong code or password. 429 rate_limited: too many failed attempts.
SIGN_IN = public({401: ERROR, 429: ERROR})


@router.post("/auth/activate", response_model=TokenPair, summary="Sign a learner in with an activation code",
             **SIGN_IN)
def activate(request: Request, body: ActivateRequest, conn=Conn, now=Now):
    return mock_example(request, TokenPair) or auth_service.activate(conn, body.code, client_ip(request), now)


@router.post("/auth/staff/login", response_model=TokenPair, summary="Sign a reviewer or admin in", **SIGN_IN)
def staff_login(request: Request, body: StaffLoginRequest, conn=Conn, now=Now):
    return mock_example(request, TokenPair) or auth_service.staff_login(
        conn, body.email, body.password, client_ip(request), now)


REFRESH_NOTES = (
    "Returns a new access and refresh token and retires the old pair. Send one refresh at a time: a refresh "
    "token presented twice is treated as stolen and signs that device out (401 `unauthenticated`), so a client "
    "must not fire two refreshes in parallel or retry one whose answer it lost; sign in again in that case. "
    "A request still in flight with the old access token answers 401 `token_expired`: retry it with the new token."
)


@router.post("/auth/refresh", response_model=TokenPair, summary="Exchange a refresh token for a new pair",
             description=REFRESH_NOTES, **public({401: ERROR}))
def refresh(request: Request, body: RefreshRequest, conn=Conn, now=Now):
    return mock_example(request, TokenPair) or auth_service.refresh(conn, body.refresh_token, now)


@router.post("/auth/logout", response_model=Ok, summary="Revoke the caller's tokens",
             **access("learner", "reviewer", "admin", "ministry_viewer", consent=False))
def logout(request: Request, conn=Conn, now=Now, principal=Caller):
    if (mock := mock_example(request, Ok)) is not None:
        return mock
    auth_service.logout(conn, principal, now)
    return Ok()
