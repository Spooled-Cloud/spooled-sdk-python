"""
Ingest resource for Spooled SDK.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from spooled.resources.base import AsyncBaseResource, BaseResource


class CustomWebhookParams(BaseModel):
    """Parameters for custom webhook ingestion."""

    queue_name: str = Field(..., min_length=1, max_length=100)
    event_type: str | None = None
    payload: dict[str, Any]
    idempotency_key: str | None = None
    priority: int | None = Field(default=None, ge=-100, le=100)

    model_config = {"extra": "forbid"}


class CustomWebhookResponse(BaseModel):
    """POST /webhooks/{org_id}/custom — OpenAPI WebhookResponse."""

    job_id: str | None = None
    queue_name: str | None = None
    status: str | None = None


def _custom_response(data: Any) -> CustomWebhookResponse:
    """Map JSON ``{job_id, queue_name, status}``; empty 200 stays all-None."""
    if isinstance(data, dict):
        return CustomWebhookResponse.model_validate(data)
    return CustomWebhookResponse()


class IngestResource(BaseResource):
    """Webhook ingestion resource (sync)."""

    def custom(
        self,
        org_id: str,
        params: CustomWebhookParams | dict[str, Any],
        webhook_token: str | None = None,
    ) -> CustomWebhookResponse:
        """Ingest a custom webhook.

        POST /webhooks/{org_id}/custom returns ``{job_id, queue_name, status}``.
        Older empty-200 bodies map to a response with those fields unset.
        """
        if isinstance(params, dict):
            params = CustomWebhookParams.model_validate(params)

        headers = {}
        if webhook_token:
            headers["X-Webhook-Token"] = webhook_token

        data = self._http.post(
            f"/webhooks/{org_id}/custom",
            params.model_dump(exclude_none=True),
            headers=headers if headers else None,
        )
        return _custom_response(data)


class AsyncIngestResource(AsyncBaseResource):
    """Webhook ingestion resource (async)."""

    async def custom(
        self,
        org_id: str,
        params: CustomWebhookParams | dict[str, Any],
        webhook_token: str | None = None,
    ) -> CustomWebhookResponse:
        """Ingest a custom webhook.

        POST /webhooks/{org_id}/custom returns ``{job_id, queue_name, status}``.
        Older empty-200 bodies map to a response with those fields unset.
        """
        if isinstance(params, dict):
            params = CustomWebhookParams.model_validate(params)

        headers = {}
        if webhook_token:
            headers["X-Webhook-Token"] = webhook_token

        data = await self._http.post(
            f"/webhooks/{org_id}/custom",
            params.model_dump(exclude_none=True),
            headers=headers if headers else None,
        )
        return _custom_response(data)
