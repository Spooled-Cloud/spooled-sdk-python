"""
Webhook-related types.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

WebhookEvent = Literal[
    "job.created",
    "job.started",
    "job.completed",
    "job.failed",
    "job.cancelled",
    "queue.paused",
    "queue.resumed",
    "worker.registered",
    "worker.deregistered",
    "schedule.triggered",
]


class OutgoingWebhook(BaseModel):
    """Outgoing webhook configuration."""

    id: str
    organization_id: str
    name: str
    url: str
    events: list[WebhookEvent]
    enabled: bool
    failure_count: int
    last_triggered_at: datetime | None = None
    last_status: Literal["success", "failed"] | None = None
    created_at: datetime
    updated_at: datetime


class OutgoingWebhookDelivery(BaseModel):
    """Webhook delivery record."""

    id: str
    webhook_id: str
    event: str
    payload: dict[str, Any]
    status: Literal["pending", "success", "failed"]
    status_code: int | None = None
    response_body: str | None = None
    error: str | None = None
    attempts: int
    created_at: datetime
    delivered_at: datetime | None = None


class CreateOutgoingWebhookParams(BaseModel):
    """Parameters for creating an outgoing webhook."""

    name: str = Field(..., min_length=1, max_length=100)
    url: str = Field(..., min_length=1)
    events: list[WebhookEvent]
    secret: str | None = None
    enabled: bool = Field(default=True)

    model_config = {"extra": "forbid"}


class UpdateOutgoingWebhookParams(BaseModel):
    """Parameters for updating an outgoing webhook."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    url: str | None = Field(default=None, min_length=1)
    events: list[WebhookEvent] | None = None
    secret: str | None = None
    enabled: bool | None = None

    model_config = {"extra": "forbid"}


class TestWebhookResponse(BaseModel):
    """Response from testing a webhook."""

    success: bool
    status_code: int | None = None
    response_time_ms: int
    error: str | None = None


class ListDeliveriesParams(BaseModel):
    """Parameters for listing webhook deliveries."""

    status: Literal["pending", "success", "failed"] | None = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    model_config = {"extra": "forbid"}


class RetryDeliveryResponse(BaseModel):
    """Response from retrying a delivery."""

    delivery_id: str
    status: str
