"""
API Keys resource for Spooled SDK.
"""

from __future__ import annotations

from typing import Any

from spooled.resources.base import AsyncBaseResource, BaseResource
from spooled.types.api_keys import (
    ApiKey,
    ApiKeySummary,
    CreateApiKeyParams,
    CreateApiKeyResponse,
    UpdateApiKeyParams,
)


class ApiKeysResource(BaseResource):
    """API Keys resource (sync)."""

    def list(self) -> list[ApiKeySummary]:
        """List all API keys."""
        data = self._http.get("/api-keys")
        return [ApiKeySummary.model_validate(item) for item in data]

    def create(self, params: CreateApiKeyParams | dict[str, Any]) -> CreateApiKeyResponse:
        """Create a new API key."""
        if isinstance(params, dict):
            params = CreateApiKeyParams.model_validate(params)
        data = self._http.post("/api-keys", params.model_dump(exclude_none=True, mode="json"))
        return CreateApiKeyResponse.model_validate(data)

    def get(self, key_id: str) -> ApiKey:
        """Get an API key by ID."""
        data = self._http.get(f"/api-keys/{key_id}")
        return ApiKey.model_validate(data)

    def update(self, key_id: str, params: UpdateApiKeyParams | dict[str, Any]) -> ApiKey:
        """Update an API key."""
        if isinstance(params, dict):
            params = UpdateApiKeyParams.model_validate(params)
        data = self._http.put(f"/api-keys/{key_id}", params.model_dump(exclude_none=True))
        return ApiKey.model_validate(data)

    def delete(self, key_id: str) -> None:
        """Revoke an API key."""
        self._http.delete(f"/api-keys/{key_id}")


class AsyncApiKeysResource(AsyncBaseResource):
    """API Keys resource (async)."""

    async def list(self) -> list[ApiKeySummary]:
        """List all API keys."""
        data = await self._http.get("/api-keys")
        return [ApiKeySummary.model_validate(item) for item in data]

    async def create(
        self, params: CreateApiKeyParams | dict[str, Any]
    ) -> CreateApiKeyResponse:
        """Create a new API key."""
        if isinstance(params, dict):
            params = CreateApiKeyParams.model_validate(params)
        data = await self._http.post(
            "/api-keys", params.model_dump(exclude_none=True, mode="json")
        )
        return CreateApiKeyResponse.model_validate(data)

    async def get(self, key_id: str) -> ApiKey:
        """Get an API key by ID."""
        data = await self._http.get(f"/api-keys/{key_id}")
        return ApiKey.model_validate(data)

    async def update(
        self, key_id: str, params: UpdateApiKeyParams | dict[str, Any]
    ) -> ApiKey:
        """Update an API key."""
        if isinstance(params, dict):
            params = UpdateApiKeyParams.model_validate(params)
        data = await self._http.put(f"/api-keys/{key_id}", params.model_dump(exclude_none=True))
        return ApiKey.model_validate(data)

    async def delete(self, key_id: str) -> None:
        """Revoke an API key."""
        await self._http.delete(f"/api-keys/{key_id}")
