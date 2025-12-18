"""
API key-related types.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ApiKey(BaseModel):
    """Full API key model."""

    id: str
    organization_id: str | None = None
    name: str
    key_prefix: str | None = None
    queues: list[str] | None = None
    rate_limit: int | None = None
    is_active: bool = True
    created_at: datetime
    last_used: datetime | None = None
    expires_at: datetime | None = None


class ApiKeySummary(BaseModel):
    """Summary view of an API key."""

    id: str
    name: str
    key_prefix: str | None = None
    queues: list[str]
    rate_limit: int | None = None
    is_active: bool
    created_at: datetime
    last_used: datetime | None = None
    expires_at: datetime | None = None


class CreateApiKeyParams(BaseModel):
    """Parameters for creating an API key."""

    name: str = Field(..., min_length=1, max_length=100)
    queues: list[str] | None = None
    rate_limit: int | None = Field(default=None, ge=1)
    expires_at: datetime | None = None

    model_config = {"extra": "forbid"}


class CreateApiKeyResponse(BaseModel):
    """Response from creating an API key."""

    id: str
    key: str  # Raw key - only shown once!
    name: str
    created_at: datetime
    expires_at: datetime | None = None


class UpdateApiKeyParams(BaseModel):
    """Parameters for updating an API key."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    queues: list[str] | None = None
    rate_limit: int | None = Field(default=None, ge=1)
    is_active: bool | None = None

    model_config = {"extra": "forbid"}
