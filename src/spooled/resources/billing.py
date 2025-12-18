"""
Billing resource for Spooled SDK.
"""

from __future__ import annotations

from typing import Any

from spooled.resources.base import AsyncBaseResource, BaseResource
from spooled.types.billing import (
    BillingStatus,
    CreatePortalParams,
    CreatePortalResponse,
)


class BillingResource(BaseResource):
    """Billing resource (sync)."""

    def get_status(self) -> BillingStatus:
        """Get billing status for current organization."""
        data = self._http.get("/billing/status")
        return BillingStatus.model_validate(data)

    def create_portal(
        self, params: CreatePortalParams | dict[str, Any]
    ) -> CreatePortalResponse:
        """Create a Stripe billing portal session."""
        if isinstance(params, dict):
            params = CreatePortalParams.model_validate(params)
        data = self._http.post("/billing/portal", params.model_dump(exclude_none=True))
        return CreatePortalResponse.model_validate(data)


class AsyncBillingResource(AsyncBaseResource):
    """Billing resource (async)."""

    async def get_status(self) -> BillingStatus:
        """Get billing status for current organization."""
        data = await self._http.get("/billing/status")
        return BillingStatus.model_validate(data)

    async def create_portal(
        self, params: CreatePortalParams | dict[str, Any]
    ) -> CreatePortalResponse:
        """Create a Stripe billing portal session."""
        if isinstance(params, dict):
            params = CreatePortalParams.model_validate(params)
        data = await self._http.post("/billing/portal", params.model_dump(exclude_none=True))
        return CreatePortalResponse.model_validate(data)
