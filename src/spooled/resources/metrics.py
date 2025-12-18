"""
Metrics resource for Spooled SDK.
"""

from __future__ import annotations

from spooled.resources.base import AsyncBaseResource, BaseResource


class MetricsResource(BaseResource):
    """Metrics resource (sync)."""

    def get(self) -> str:
        """Get Prometheus metrics."""
        data = self._http.get("/metrics", skip_api_prefix=True, skip_response_conversion=True)
        return str(data)


class AsyncMetricsResource(AsyncBaseResource):
    """Metrics resource (async)."""

    async def get(self) -> str:
        """Get Prometheus metrics."""
        data = await self._http.get(
            "/metrics", skip_api_prefix=True, skip_response_conversion=True
        )
        return str(data)
