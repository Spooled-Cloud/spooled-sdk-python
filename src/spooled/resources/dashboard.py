"""
Dashboard resource for Spooled SDK.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from spooled.resources.base import AsyncBaseResource, BaseResource
from spooled.types.dashboard import DashboardData

if TYPE_CHECKING:
    from spooled.utils.async_http import AsyncHttpClient
    from spooled.utils.http import HttpClient


class DashboardResource(BaseResource):
    """Dashboard resource (sync)."""

    def get(self) -> DashboardData:
        """Get aggregated dashboard data."""
        data = self._http.get("/dashboard")
        return DashboardData.model_validate(data)


class AsyncDashboardResource(AsyncBaseResource):
    """Dashboard resource (async)."""

    async def get(self) -> DashboardData:
        """Get aggregated dashboard data."""
        data = await self._http.get("/dashboard")
        return DashboardData.model_validate(data)


