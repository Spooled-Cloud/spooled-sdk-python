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

# Outcome of the most recent delivery attempt for a webhook.
# ``auto_disabled`` is set by the backend, not by a client.
WebhookLastStatus = Literal["success", "failed", "auto_disabled"]


class OutgoingWebhook(BaseModel):
    """Outgoing webhook configuration.

    ``enabled`` is not purely caller-controlled: after 20 consecutive failed
    deliveries the backend disables the webhook itself, setting
    ``enabled=False`` and ``last_status="auto_disabled"``. It receives no
    further events until it is re-enabled with
    ``client.webhooks.update(id, {"enabled": True})`` — which counts against
    the plan webhook cap, so re-enabling can raise
    :class:`~spooled.errors.RateLimitError` with code ``QUOTA_EXCEEDED``.

    ``failure_count`` counts failed *deliveries*, not individual retry
    attempts, so for the same real-world failures it is roughly 5x smaller
    than the attempt-based count. Any successful delivery — including a
    successful manual retry via ``retry_delivery`` — resets it to 0.
    """

    id: str
    organization_id: str
    name: str
    url: str
    events: list[WebhookEvent]
    enabled: bool
    failure_count: int
    last_triggered_at: datetime | None = None
    last_status: WebhookLastStatus | None = None
    created_at: datetime
    updated_at: datetime


class OutgoingWebhookDelivery(BaseModel):
    """Webhook delivery record.

    Delivery history is retained, not archived: the per-organization retention
    sweep deletes rows older than the plan's history retention window (free 1
    day, starter 7, pro 30, enterprise 90). Only the newest 100 deliveries per
    webhook are readable through the API in any case, so copy anything you
    need for long-term auditing into your own store.
    """

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
    """Parameters for updating an outgoing webhook.

    Only the fields you actually pass are sent; everything you leave out keeps
    its current server-side value.

    ``secret`` is three-state, and one of those states is destructive:

    * leave it out entirely — the current signing secret is kept
    * pass ``secret=None`` — the signing secret is **cleared**, and deliveries
      then go out unsigned with no ``X-Spooled-Signature`` header
    * pass a string — the signing secret is replaced

    Because "omitted" and "explicitly null" now mean different things, do not
    build update params by dumping a full model and passing every field back:
    an unchanged ``secret`` serialised as an explicit ``None`` wipes a live
    secret. Pass only the fields you mean to change.

    Setting ``enabled=True`` on an auto-disabled webhook counts against the
    plan webhook cap and can therefore raise
    :class:`~spooled.errors.RateLimitError` with code ``QUOTA_EXCEEDED``.
    """

    name: str | None = Field(default=None, min_length=1, max_length=100)
    url: str | None = Field(default=None, min_length=1)
    events: list[WebhookEvent] | None = None
    secret: str | None = None
    enabled: bool | None = None

    model_config = {"extra": "forbid"}

    def to_payload(self) -> dict[str, Any]:
        """Build the request body, preserving an explicitly-cleared secret.

        Fields the caller never mentioned are omitted so the server keeps
        them. ``secret`` is the exception: when it was explicitly set to
        ``None`` it is serialised as JSON ``null`` so the server clears it.
        """
        payload: dict[str, Any] = self.model_dump(exclude_none=True)
        if "secret" in self.model_fields_set and self.secret is None:
            payload["secret"] = None
        return payload


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
