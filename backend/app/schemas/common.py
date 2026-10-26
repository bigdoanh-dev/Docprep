"""Shapes shared by several domains."""
from typing import Literal

from pydantic import Field

from app.schemas.base import Schema, with_example

Role = Literal["learner", "reviewer", "admin", "ministry_viewer"]

ERROR_CODES = (
    "General codes: `invalid_request` (422; `details.fields` lists `{path, message}` per failing field), "
    "`unauthenticated` (401; no or unknown token, or wrong sign-in credentials), `token_expired` (401; refresh, "
    "then retry), `forbidden` (403; the role may not call this), `consent_required` (403; record the service "
    "consent first), `not_found` (404), `method_not_allowed` (405), `attempt_closed` (409; the exam attempt was "
    "already handed in), `rate_limited` (429), `not_implemented` (501), `internal_error` (500). "
    "A route may add codes of its own; treat an unknown code as a generic failure and show `message_vi`."
)


class ErrorDetail(Schema):
    code: str = Field(description=ERROR_CODES)
    message_vi: str = Field(description="Vietnamese message, fit to show to the user.")
    details: dict | None = Field(default=None, description="Extra data for some codes; null otherwise.")


class ErrorBody(Schema):
    """The body of every error response."""
    error: ErrorDetail

    model_config = with_example(
        {"error": {"code": "not_found", "message_vi": "Không tìm thấy đường dẫn.", "details": None}})


class Ok(Schema):
    ok: bool = True

    model_config = with_example({"ok": True})


class Citation(Schema):
    n: int
    passage_id: str
    document: str
    chapter: str | None = None
    section: str | None = None
    page: int | None = None
    article: str | None = None


class Option(Schema):
    key: str
    text: str
