"""
Organization-related types.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

PlanTier = Literal["free", "starter", "pro", "enterprise"]


class Organization(BaseModel):
    """Full organization model."""

    id: str
    name: str
    slug: str
    plan_tier: PlanTier
    billing_email: str | None = None
    settings: dict[str, Any]
    custom_limits: dict[str, Any] | None = None
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    stripe_subscription_status: str | None = None
    stripe_current_period_end: datetime | None = None
    stripe_cancel_at_period_end: bool | None = None
    created_at: datetime
    updated_at: datetime


class OrganizationSummary(BaseModel):
    """Summary view of an organization."""

    id: str
    name: str
    slug: str
    plan_tier: PlanTier
    created_at: datetime


class OrganizationMember(BaseModel):
    """Organization member."""

    id: str
    user_id: str
    email: str
    name: str
    role: str
    joined_at: datetime
    invited_by: str | None = None


class CreateOrganizationParams(BaseModel):
    """Parameters for creating an organization."""

    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100, pattern="^[a-z0-9-]+$")
    billing_email: str | None = None

    model_config = {"extra": "forbid"}


class ApiKeyInfo(BaseModel):
    """API key info returned on organization creation."""

    id: str
    key: str
    name: str
    created_at: datetime


class CreateOrganizationResponse(BaseModel):
    """Response from creating an organization."""

    organization: Organization
    api_key: ApiKeyInfo


class UpdateOrganizationParams(BaseModel):
    """Parameters for updating an organization."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    billing_email: str | None = None
    settings: dict[str, Any] | None = None

    model_config = {"extra": "forbid"}


class PlanLimits(BaseModel):
    """Plan limits."""

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


class UsageItem(BaseModel):
    """Single usage item."""

    current: int
    limit: int | None = None
    percentage: float | None = None
    is_disabled: bool


class ResourceUsage(BaseModel):
    """Resource usage breakdown."""

    jobs_today: UsageItem
    active_jobs: UsageItem
    queues: UsageItem
    workers: UsageItem
    api_keys: UsageItem
    schedules: UsageItem
    workflows: UsageItem
    webhooks: UsageItem


class UsageWarning(BaseModel):
    """Usage warning."""

    resource: str
    message: str
    severity: Literal["warning", "critical"] | str


class UsageInfo(BaseModel):
    """Usage information."""

    plan: PlanTier
    plan_display_name: str
    limits: PlanLimits
    usage: ResourceUsage
    warnings: list[UsageWarning]


class CheckSlugResponse(BaseModel):
    """Response from checking slug availability."""

    available: bool
    valid: bool = True
    slug: str | None = None


class GenerateSlugResponse(BaseModel):
    """Response from generating a slug."""

    slug: str


class WebhookTokenResponse(BaseModel):
    """Response containing webhook token."""

    webhook_token: str | None = None
    webhook_url: str | None = None
