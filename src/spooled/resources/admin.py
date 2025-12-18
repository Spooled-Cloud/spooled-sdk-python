"""
Admin resource for Spooled SDK.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from spooled.resources.base import AsyncBaseResource, BaseResource
from spooled.types.admin import (
    AdminCreateApiKeyParams,
    AdminCreateApiKeyResponse,
    AdminCreateOrganizationParams,
    AdminStats,
    AdminUpdateOrganizationParams,
    ListOrganizationsParams,
    PlanInfo,
)
from spooled.types.organizations import Organization

if TYPE_CHECKING:
    from spooled.utils.async_http import AsyncHttpClient
    from spooled.utils.http import HttpClient


class AdminResource(BaseResource):
    """Admin resource (sync). Requires admin_key."""

    def __init__(self, http: HttpClient, admin_key: str | None = None) -> None:
        super().__init__(http)
        self._admin_key = admin_key

    def _get_headers(self) -> dict[str, str]:
        """Get admin headers."""
        if not self._admin_key:
            raise ValueError("Admin key is required for admin operations")
        return {"X-Admin-Key": self._admin_key}

    def list_organizations(
        self, params: ListOrganizationsParams | dict[str, Any] | None = None
    ) -> list[Organization]:
        """List all organizations."""
        if isinstance(params, dict):
            params = ListOrganizationsParams.model_validate(params)
        query_params = params.model_dump(exclude_none=True) if params else None
        data = self._http.get(
            "/admin/organizations", params=query_params, headers=self._get_headers()
        )
        return [Organization.model_validate(item) for item in data]

    def get_organization(self, org_id: str) -> Organization:
        """Get an organization by ID."""
        data = self._http.get(f"/admin/organizations/{org_id}", headers=self._get_headers())
        return Organization.model_validate(data)

    def create_organization(
        self, params: AdminCreateOrganizationParams | dict[str, Any]
    ) -> Organization:
        """Create a new organization."""
        if isinstance(params, dict):
            params = AdminCreateOrganizationParams.model_validate(params)
        data = self._http.post(
            "/admin/organizations",
            params.model_dump(exclude_none=True),
            headers=self._get_headers(),
        )
        return Organization.model_validate(data)

    def update_organization(
        self, org_id: str, params: AdminUpdateOrganizationParams | dict[str, Any]
    ) -> Organization:
        """Update an organization."""
        if isinstance(params, dict):
            params = AdminUpdateOrganizationParams.model_validate(params)
        data = self._http.patch(
            f"/admin/organizations/{org_id}",
            params.model_dump(exclude_none=True),
            headers=self._get_headers(),
        )
        return Organization.model_validate(data)

    def delete_organization(self, org_id: str, hard: bool = False) -> None:
        """Delete an organization."""
        self._http.delete(
            f"/admin/organizations/{org_id}",
            params={"hard": hard} if hard else None,
            headers=self._get_headers(),
        )

    def create_api_key(
        self, org_id: str, params: AdminCreateApiKeyParams | dict[str, Any]
    ) -> AdminCreateApiKeyResponse:
        """Create an API key for an organization."""
        if isinstance(params, dict):
            params = AdminCreateApiKeyParams.model_validate(params)
        data = self._http.post(
            f"/admin/organizations/{org_id}/api-keys",
            params.model_dump(exclude_none=True, mode="json"),
            headers=self._get_headers(),
        )
        return AdminCreateApiKeyResponse.model_validate(data)

    def reset_usage(self, org_id: str) -> None:
        """Reset usage counters for an organization."""
        self._http.post(
            f"/admin/organizations/{org_id}/reset-usage", headers=self._get_headers()
        )

    def get_stats(self) -> AdminStats:
        """Get platform-wide statistics."""
        data = self._http.get("/admin/stats", headers=self._get_headers())
        return AdminStats.model_validate(data)

    def list_plans(self) -> list[PlanInfo]:
        """List all plan tiers and limits."""
        data = self._http.get("/admin/plans", headers=self._get_headers())
        return [PlanInfo.model_validate(item) for item in data]


class AsyncAdminResource(AsyncBaseResource):
    """Admin resource (async). Requires admin_key."""

    def __init__(self, http: AsyncHttpClient, admin_key: str | None = None) -> None:
        super().__init__(http)
        self._admin_key = admin_key

    def _get_headers(self) -> dict[str, str]:
        """Get admin headers."""
        if not self._admin_key:
            raise ValueError("Admin key is required for admin operations")
        return {"X-Admin-Key": self._admin_key}

    async def list_organizations(
        self, params: ListOrganizationsParams | dict[str, Any] | None = None
    ) -> list[Organization]:
        """List all organizations."""
        if isinstance(params, dict):
            params = ListOrganizationsParams.model_validate(params)
        query_params = params.model_dump(exclude_none=True) if params else None
        data = await self._http.get(
            "/admin/organizations", params=query_params, headers=self._get_headers()
        )
        return [Organization.model_validate(item) for item in data]

    async def get_organization(self, org_id: str) -> Organization:
        """Get an organization by ID."""
        data = await self._http.get(
            f"/admin/organizations/{org_id}", headers=self._get_headers()
        )
        return Organization.model_validate(data)

    async def create_organization(
        self, params: AdminCreateOrganizationParams | dict[str, Any]
    ) -> Organization:
        """Create a new organization."""
        if isinstance(params, dict):
            params = AdminCreateOrganizationParams.model_validate(params)
        data = await self._http.post(
            "/admin/organizations",
            params.model_dump(exclude_none=True),
            headers=self._get_headers(),
        )
        return Organization.model_validate(data)

    async def update_organization(
        self, org_id: str, params: AdminUpdateOrganizationParams | dict[str, Any]
    ) -> Organization:
        """Update an organization."""
        if isinstance(params, dict):
            params = AdminUpdateOrganizationParams.model_validate(params)
        data = await self._http.patch(
            f"/admin/organizations/{org_id}",
            params.model_dump(exclude_none=True),
            headers=self._get_headers(),
        )
        return Organization.model_validate(data)

    async def delete_organization(self, org_id: str, hard: bool = False) -> None:
        """Delete an organization."""
        await self._http.delete(
            f"/admin/organizations/{org_id}",
            params={"hard": hard} if hard else None,
            headers=self._get_headers(),
        )

    async def create_api_key(
        self, org_id: str, params: AdminCreateApiKeyParams | dict[str, Any]
    ) -> AdminCreateApiKeyResponse:
        """Create an API key for an organization."""
        if isinstance(params, dict):
            params = AdminCreateApiKeyParams.model_validate(params)
        data = await self._http.post(
            f"/admin/organizations/{org_id}/api-keys",
            params.model_dump(exclude_none=True, mode="json"),
            headers=self._get_headers(),
        )
        return AdminCreateApiKeyResponse.model_validate(data)

    async def reset_usage(self, org_id: str) -> None:
        """Reset usage counters for an organization."""
        await self._http.post(
            f"/admin/organizations/{org_id}/reset-usage", headers=self._get_headers()
        )

    async def get_stats(self) -> AdminStats:
        """Get platform-wide statistics."""
        data = await self._http.get("/admin/stats", headers=self._get_headers())
        return AdminStats.model_validate(data)

    async def list_plans(self) -> list[PlanInfo]:
        """List all plan tiers and limits."""
        data = await self._http.get("/admin/plans", headers=self._get_headers())
        return [PlanInfo.model_validate(item) for item in data]
