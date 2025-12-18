"""
Authentication-related types.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


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


class MeResponse(BaseModel):
    """Response from /auth/me endpoint."""

    organization_id: str
    api_key_id: str
    queues: list[str]
    issued_at: datetime
    expires_at: datetime


class ValidateParams(BaseModel):
    """Parameters for token validation."""

    token: str

    model_config = {"extra": "forbid"}


class ValidateResponse(BaseModel):
    """Response from token validation."""

    valid: bool
    organization_id: str | None = None
    expires_at: datetime | None = None


class StartEmailLoginResponse(BaseModel):
    """Response from starting email login."""

    message: str
    expires_in: int | None = None  # seconds
    email_to: str | None = None  # masked email


class CheckEmailResponse(BaseModel):
    """Response from checking email."""

    exists: bool
    has_organizations: bool | None = None
