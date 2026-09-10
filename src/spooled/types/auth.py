"""
Authentication-related types.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class LoginParams(BaseModel):
    """Parameters for login."""

    api_key: str = Field(..., min_length=10)

    model_config = {"extra": "forbid"}


class LoginResponse(BaseModel):
    """Response from login."""

    access_token: str
    refresh_token: str
    token_type: str  # 'Bearer'
    expires_in: int  # seconds
    refresh_expires_in: int  # seconds


class RefreshParams(BaseModel):
    """Parameters for token refresh."""

    refresh_token: str

    model_config = {"extra": "forbid"}


class RefreshResponse(BaseModel):
    """Response from token refresh."""

    access_token: str
    token_type: str  # 'Bearer'
    expires_in: int  # seconds


class MeOrganization(BaseModel):
    """Organization nested on GET /auth/me (`CurrentUserResponse.organization`)."""

    id: str
    name: str
    slug: str
    plan_tier: str
    billing_email: str | None = None


class MeResponse(BaseModel):
    """Response from /auth/me endpoint.

    The API also sends nested ``organization`` (id/name/slug/plan_tier/
    billing_email). That used to be dropped because it was not on this model.
    """

    organization_id: str
    api_key_id: str
    queues: list[str]
    issued_at: datetime
    expires_at: datetime
    organization: MeOrganization | None = None


class ValidateParams(BaseModel):
    """Parameters for token validation."""

    token: str

    model_config = {"extra": "forbid"}


class ValidateResponse(BaseModel):
    """POST /auth/validate — `{ valid, error?, claims? }`.

    Claims carry `org_id`, `api_key_id`, `queues`, `exp`. The API never sends
    top-level `organization_id` / `expires_at`.
    """

    valid: bool
    error: str | None = None
    organization_id: str | None = None
    api_key_id: str | None = None
    queues: list[str] | None = None
    expires_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def map_claims(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        claims = data.get("claims")
        if not isinstance(claims, dict):
            return data
        data = dict(data)
        if data.get("organization_id") is None:
            org = claims.get("org_id") or claims.get("organization_id")
            if org is not None:
                data["organization_id"] = org
        if data.get("api_key_id") is None and claims.get("api_key_id") is not None:
            data["api_key_id"] = claims["api_key_id"]
        if data.get("queues") is None and isinstance(claims.get("queues"), list):
            data["queues"] = claims["queues"]
        if data.get("expires_at") is None and claims.get("exp") is not None:
            exp = claims["exp"]
            if isinstance(exp, (int, float)):
                data["expires_at"] = datetime.fromtimestamp(int(exp), tz=timezone.utc)
            else:
                data["expires_at"] = exp
        return data


class StartEmailLoginResponse(BaseModel):
    """Response from POST /auth/email/start."""

    model_config = ConfigDict(populate_by_name=True)

    message: str
    email_sent_to: str | None = Field(
        default=None,
        validation_alias=AliasChoices("email_sent_to", "email_to"),
    )
    expires_in: int | None = None


class CheckEmailResponse(BaseModel):
    """Response from GET /auth/check-email."""

    exists: bool
    available: bool | None = None
    signup_enabled: bool | None = None
    has_organizations: bool | None = None
