"""Sign-in: learners by activation code, staff by email and password. Tokens are opaque."""
from typing import Literal

from pydantic import Field

from app.schemas.base import RequestSchema, Schema, with_example
from app.schemas.common import Role


class DeviceInfo(RequestSchema):
    platform: Literal["ios", "android", "web"]
    model: str | None = None
    app_version: str | None = None


class ActivateRequest(RequestSchema):
    code: str = Field(min_length=6)
    device: DeviceInfo | None = None

    model_config = with_example({
        "code": "DEMO-0001",
        "device": {"platform": "android", "model": "Pixel 8", "app_version": "1.0.0"},
    })


class StaffLoginRequest(RequestSchema):
    email: str
    password: str

    model_config = with_example({"email": "tham.dinh.1@example.org", "password": "mat-khau-mau"})


class RefreshRequest(RequestSchema):
    refresh_token: str

    model_config = with_example({"refresh_token": "rt_3f9c1a7e5b2d4c60"})


class TokenPair(Schema):
    access_token: str
    refresh_token: str
    expires_in: int = Field(description="Lifetime of the access token, in seconds.")
    role: Role
    consent_required: bool = Field(description="True until the learner has given the current service consent.")

    model_config = with_example({
        "access_token": "at_8b1d0c4e7a2f4d19",
        "refresh_token": "rt_3f9c1a7e5b2d4c60",
        "expires_in": 1800,
        "role": "learner",
        "consent_required": True,
    })
