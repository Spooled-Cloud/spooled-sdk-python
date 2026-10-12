"""
Metrics resource for Spooled SDK.
"""

from __future__ import annotations

from spooled.resources.base import AsyncBaseResource, BaseResource


class MetricsResource(BaseResource):
    """Metrics resource (sync)."""

    def get(self, token: str | None = None) -> str:
        """Get Prometheus metrics (``GET /metrics``).

        The endpoint is not public on Spooled Cloud: it takes the server's
        metrics token (``Authorization: Bearer <METRICS_TOKEN>``), not an API
        key, and answers 401 otherwise. Pass that token as ``token``; without
        it the client's API key is sent, which only works on a server that has
        no metrics token configured.
        """
        headers = {"Authorization": f"Bearer {token}"} if token else None
        data = self._http.get(
            "/metrics", headers=headers, skip_api_prefix=True, skip_response_conversion=True
        )
        return str(data)


class AsyncMetricsResource(AsyncBaseResource):
    """Metrics resource (async)."""

    async def get(self, token: str | None = None) -> str:
        """Get Prometheus metrics (see ``MetricsResource.get``; needs the metrics token)."""
        headers = {"Authorization": f"Bearer {token}"} if token else None
        data = await self._http.get(
            "/metrics", headers=headers, skip_api_prefix=True, skip_response_conversion=True
        )
        return str(data)
