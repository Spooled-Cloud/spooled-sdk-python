"""
Health resource for Spooled SDK.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from spooled.resources.base import AsyncBaseResource, BaseResource
from spooled.types.health import HealthResponse

if TYPE_CHECKING:
    from spooled.utils.async_http import AsyncHttpClient
    from spooled.utils.http import HttpClient


class HealthResource(BaseResource):
    """Health resource (sync)."""

    def get(self) -> HealthResponse:
        """Get full health check."""
        data = self._http.get("/health", skip_api_prefix=True)
        return HealthResponse.model_validate(data)

    def liveness(self) -> bool:
        """Check if service is alive."""
        try:
            self._http.get("/health/live", skip_api_prefix=True)
            return True
        except Exception:
            return False

    def readiness(self) -> bool:
        """Check if service is ready."""
        try:
            self._http.get("/health/ready", skip_api_prefix=True)
            return True
        except Exception:
            return False


class AsyncHealthResource(AsyncBaseResource):
    """Health resource (async)."""

    async def get(self) -> HealthResponse:
        """Get full health check."""
        data = await self._http.get("/health", skip_api_prefix=True)
        return HealthResponse.model_validate(data)

    async def liveness(self) -> bool:
        """Check if service is alive."""
        try:
            await self._http.get("/health/live", skip_api_prefix=True)
            return True
        except Exception:
            return False

    async def readiness(self) -> bool:
        """Check if service is ready."""
        try:
            await self._http.get("/health/ready", skip_api_prefix=True)
            return True
        except Exception:
            return False


