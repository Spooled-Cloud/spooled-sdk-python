"""
Webhooks resource for Spooled SDK.
"""

from __future__ import annotations

import builtins
from typing import Any

from spooled.resources.base import AsyncBaseResource, BaseResource
from spooled.types.webhooks import (
    CreateOutgoingWebhookParams,
    ListDeliveriesParams,
    OutgoingWebhook,
    OutgoingWebhookDelivery,
    RetryDeliveryResponse,
    TestWebhookResponse,
    UpdateOutgoingWebhookParams,
)


class WebhooksResource(BaseResource):
    """Outgoing webhooks resource (sync)."""

    def list(self) -> builtins.list[OutgoingWebhook]:
        """List all outgoing webhooks."""
        data = self._http.get("/outgoing-webhooks")
        return [OutgoingWebhook.model_validate(item) for item in data]

    def create(
        self, params: CreateOutgoingWebhookParams | dict[str, Any]
    ) -> OutgoingWebhook:
        """Create an outgoing webhook."""
        if isinstance(params, dict):
            params = CreateOutgoingWebhookParams.model_validate(params)
        data = self._http.post("/outgoing-webhooks", params.model_dump(exclude_none=True))
        return OutgoingWebhook.model_validate(data)

    def get(self, webhook_id: str) -> OutgoingWebhook:
        """Get an outgoing webhook by ID."""
        data = self._http.get(f"/outgoing-webhooks/{webhook_id}")
        return OutgoingWebhook.model_validate(data)

    def update(
        self, webhook_id: str, params: UpdateOutgoingWebhookParams | dict[str, Any]
    ) -> OutgoingWebhook:
        """Update an outgoing webhook."""
        if isinstance(params, dict):
            params = UpdateOutgoingWebhookParams.model_validate(params)
        data = self._http.put(
            f"/outgoing-webhooks/{webhook_id}", params.model_dump(exclude_none=True)
        )
        return OutgoingWebhook.model_validate(data)

    def delete(self, webhook_id: str) -> None:
        """Delete an outgoing webhook."""
        self._http.delete(f"/outgoing-webhooks/{webhook_id}")

    def test(self, webhook_id: str) -> TestWebhookResponse:
        """Test an outgoing webhook."""
        data = self._http.post(f"/outgoing-webhooks/{webhook_id}/test")
        return TestWebhookResponse.model_validate(data)

    def get_deliveries(
        self, webhook_id: str, params: ListDeliveriesParams | dict[str, Any] | None = None
    ) -> builtins.list[OutgoingWebhookDelivery]:
        """Get webhook delivery history."""
        if isinstance(params, dict):
            params = ListDeliveriesParams.model_validate(params)
        query_params = params.model_dump(exclude_none=True) if params else None
        data = self._http.get(f"/outgoing-webhooks/{webhook_id}/deliveries", params=query_params)
        return [OutgoingWebhookDelivery.model_validate(item) for item in data]

    def retry_delivery(self, webhook_id: str, delivery_id: str) -> RetryDeliveryResponse:
        """Retry a failed webhook delivery."""
        data = self._http.post(
            f"/outgoing-webhooks/{webhook_id}/deliveries/{delivery_id}/retry"
        )
        return RetryDeliveryResponse.model_validate(data)


class AsyncWebhooksResource(AsyncBaseResource):
    """Outgoing webhooks resource (async)."""

    async def list(self) -> builtins.list[OutgoingWebhook]:
        """List all outgoing webhooks."""
        data = await self._http.get("/outgoing-webhooks")
        return [OutgoingWebhook.model_validate(item) for item in data]

    async def create(
        self, params: CreateOutgoingWebhookParams | dict[str, Any]
    ) -> OutgoingWebhook:
        """Create an outgoing webhook."""
        if isinstance(params, dict):
            params = CreateOutgoingWebhookParams.model_validate(params)
        data = await self._http.post("/outgoing-webhooks", params.model_dump(exclude_none=True))
        return OutgoingWebhook.model_validate(data)

    async def get(self, webhook_id: str) -> OutgoingWebhook:
        """Get an outgoing webhook by ID."""
        data = await self._http.get(f"/outgoing-webhooks/{webhook_id}")
        return OutgoingWebhook.model_validate(data)

    async def update(
        self, webhook_id: str, params: UpdateOutgoingWebhookParams | dict[str, Any]
    ) -> OutgoingWebhook:
        """Update an outgoing webhook."""
        if isinstance(params, dict):
            params = UpdateOutgoingWebhookParams.model_validate(params)
        data = await self._http.put(
            f"/outgoing-webhooks/{webhook_id}", params.model_dump(exclude_none=True)
        )
        return OutgoingWebhook.model_validate(data)

    async def delete(self, webhook_id: str) -> None:
        """Delete an outgoing webhook."""
        await self._http.delete(f"/outgoing-webhooks/{webhook_id}")

    async def test(self, webhook_id: str) -> TestWebhookResponse:
        """Test an outgoing webhook."""
        data = await self._http.post(f"/outgoing-webhooks/{webhook_id}/test")
        return TestWebhookResponse.model_validate(data)

    async def get_deliveries(
        self, webhook_id: str, params: ListDeliveriesParams | dict[str, Any] | None = None
    ) -> builtins.list[OutgoingWebhookDelivery]:
        """Get webhook delivery history."""
        if isinstance(params, dict):
            params = ListDeliveriesParams.model_validate(params)
        query_params = params.model_dump(exclude_none=True) if params else None
        data = await self._http.get(
            f"/outgoing-webhooks/{webhook_id}/deliveries", params=query_params
        )
        return [OutgoingWebhookDelivery.model_validate(item) for item in data]

    async def retry_delivery(
        self, webhook_id: str, delivery_id: str
    ) -> RetryDeliveryResponse:
        """Retry a failed webhook delivery."""
        data = await self._http.post(
            f"/outgoing-webhooks/{webhook_id}/deliveries/{delivery_id}/retry"
        )
        return RetryDeliveryResponse.model_validate(data)
