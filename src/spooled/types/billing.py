"""
Billing-related types.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class BillingStatus(BaseModel):
    """Billing status for an organization."""

    plan_tier: str
    stripe_subscription_id: str | None = None
    stripe_subscription_status: str | None = None
    stripe_current_period_end: datetime | None = None
    stripe_cancel_at_period_end: bool | None = None
    has_stripe_customer: bool


class CreatePortalParams(BaseModel):
    """Parameters for creating a billing portal session."""

    return_url: str

    model_config = {"extra": "forbid"}


class CreatePortalResponse(BaseModel):
    """Response from creating a billing portal session."""

    url: str
