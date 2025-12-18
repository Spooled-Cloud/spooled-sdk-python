"""
Admin-related types.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from spooled.types.organizations import PlanTier


class AdminStats(BaseModel):
    """Platform-wide statistics."""

    total_organizations: int
    total_jobs: int
    total_queues: int
    total_workers: int
    jobs_today: int
    active_organizations: int


class PlanInfo(BaseModel):
    """Plan tier information."""

    tier: str
    display_name: str
    max_jobs_per_day: int | None = None
    max_active_jobs: int | None = None
    max_queues: int | None = None
    max_workers: int | None = None
    max_api_keys: int | None = None
    max_schedules: int | None = None
    max_workflows: int | None = None
    max_webhooks: int | None = None
    max_payload_size_bytes: int
    rate_limit_requests_per_second: int
    rate_limit_burst: int
    job_retention_days: int
    history_retention_days: int


class ListOrganizationsParams(BaseModel):
    """Parameters for listing organizations (admin)."""

    plan_tier: PlanTier | None = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    model_config = {"extra": "forbid"}


class AdminCreateOrganizationParams(BaseModel):
    """Parameters for admin creating an organization."""

    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100, pattern="^[a-z0-9-]+$")
    plan_tier: PlanTier = Field(default="free")
    billing_email: str | None = None
    settings: dict[str, Any] | None = None
    custom_limits: dict[str, Any] | None = None

    model_config = {"extra": "forbid"}


class AdminUpdateOrganizationParams(BaseModel):
    """Parameters for admin updating an organization."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    plan_tier: PlanTier | None = None
    billing_email: str | None = None
    settings: dict[str, Any] | None = None
    custom_limits: dict[str, Any] | None = None

    model_config = {"extra": "forbid"}


class AdminCreateApiKeyParams(BaseModel):
    """Parameters for admin creating an API key."""

    name: str = Field(..., min_length=1, max_length=100)
    queues: list[str] | None = None
    rate_limit: int | None = Field(default=None, ge=1)
    expires_at: datetime | None = None

    model_config = {"extra": "forbid"}


class AdminCreateApiKeyResponse(BaseModel):
    """Response from admin creating an API key."""

    id: str
    key: str  # Raw key - only shown once!
    name: str
    created_at: datetime
    expires_at: datetime | None = None
