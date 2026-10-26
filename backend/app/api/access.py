"""Who may call a route. Declared on every /v1 route; the contract carries it as `x-roles`.

In real mode the declaration is also enforced: a valid access token, a role the route accepts and,
for a learner, the current service consent. Mock mode checks nothing.
"""
from fastapi import Depends, Header, Request

from app.api.deps import Conn, Now
from app.auth.principal import Principal
from app.config import settings
from app.errors import ApiError
from app.repo import consent as consent_repo
from app.repo import learners as learners_repo
from app.schemas.common import ErrorBody, Role
from app.services import auth as auth_service

# Default for an `idempotency_key: str | None` parameter on writes the app may retry.
IDEMPOTENCY = Header(None, description="Repeat with the same key to retry safely; the stored response is returned.")
# Default for an `x_mock_state: str | None` parameter on streaming routes.
MOCK_STATE = Header(None, description="Mock server only: which scripted stream to replay.")

ERROR = {"model": ErrorBody}


def conflict(description: str) -> dict:
    """A documented 409. The description names each code the route returns with it, in backticks."""
    return {409: {**ERROR, "description": description}}


def _bearer_token(request: Request) -> str | None:
    """The token of an `Authorization: Bearer <token>` header; anything else counts as no token."""
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    return token.strip() or None if scheme.lower() == "bearer" else None


def _guard(roles: tuple[str, ...], consent: bool):
    def guard(request: Request, conn=Conn, now=Now) -> None:
        if request.app.state.mode == "mock":
            return
        principal = auth_service.authenticate(conn, _bearer_token(request), now)
        if principal.role not in roles:
            raise ApiError(403, "forbidden", "Bạn không có quyền thực hiện thao tác này.")
        if consent and principal.subject_type == "learner" and not consent_repo.has_current_service_consent(
                conn, principal.subject_id, settings()["consent"]["version"]):
            raise ApiError(403, "consent_required", "Bạn cần đồng ý với điều khoản sử dụng trước khi tiếp tục.")
        request.state.principal = principal

    return guard


def access(*roles: Role, consent: bool = True, responses: dict | None = None) -> dict:
    """Keyword arguments for a route decorator: the accepted roles, their enforcement, the error responses.

    consent=False is for the routes a learner must reach before consenting: sign-out, consent, account.
    A route can pass only one `responses` keyword, so extra entries (an SSE 200, a 409) go through here.
    """
    return {
        "openapi_extra": {"x-roles": list(roles), "security": [{"bearer": []}]},
        "responses": {401: ERROR, 403: ERROR, 404: ERROR, 422: ERROR, **(responses or {})},
        "dependencies": [Depends(_guard(roles, consent), scope="function")],
    }


def public(responses: dict | None = None) -> dict:
    """Keyword arguments for a route that needs no token."""
    return {"openapi_extra": {"x-roles": ["public"]}, "responses": {422: ERROR, **(responses or {})}}


PUBLIC: dict = public()


def current_principal(request: Request) -> Principal | None:
    """The caller the guard let in. None in mock mode."""
    return getattr(request.state, "principal", None)


Caller = Depends(current_principal)


def current_learner(conn=Conn, principal=Caller) -> dict | None:
    """The learner row of the caller, for routes only learners reach. None in mock mode."""
    return None if principal is None else learners_repo.get(conn, principal.subject_id)


Learner = Depends(current_learner)
