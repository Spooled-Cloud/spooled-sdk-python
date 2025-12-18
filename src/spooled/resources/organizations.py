"""
Organizations resource for Spooled SDK.
"""

from __future__ import annotations

import builtins
from typing import Any

from spooled.resources.base import AsyncBaseResource, BaseResource
from spooled.types.organizations import (
    CheckSlugResponse,
    CreateOrganizationParams,
    CreateOrganizationResponse,
    GenerateSlugResponse,
    Organization,
    OrganizationMember,
    OrganizationSummary,
    UpdateOrganizationParams,
    UsageInfo,
    WebhookTokenResponse,
)


class OrganizationsResource(BaseResource):
    """Organizations resource (sync)."""

    def create(
        self, params: CreateOrganizationParams | dict[str, Any]
    ) -> CreateOrganizationResponse:
        """Create a new organization."""
        if isinstance(params, dict):
            params = CreateOrganizationParams.model_validate(params)
        data = self._http.post("/organizations", params.model_dump(exclude_none=True))
        return CreateOrganizationResponse.model_validate(data)

    def list(self) -> builtins.list[OrganizationSummary]:
        """List organizations."""
        data = self._http.get("/organizations")
        return [OrganizationSummary.model_validate(item) for item in data]

    def get(self, org_id: str) -> Organization:
        """Get an organization by ID."""
        data = self._http.get(f"/organizations/{org_id}")
        return Organization.model_validate(data)

    def update(
        self, org_id: str, params: UpdateOrganizationParams | dict[str, Any]
    ) -> Organization:
        """Update an organization."""
        if isinstance(params, dict):
            params = UpdateOrganizationParams.model_validate(params)
        data = self._http.put(f"/organizations/{org_id}", params.model_dump(exclude_none=True))
        return Organization.model_validate(data)

    def delete(self, org_id: str) -> None:
        """Delete an organization."""
        self._http.delete(f"/organizations/{org_id}")

    def get_usage(self) -> UsageInfo:
        """Get usage and limits for current organization."""
        data = self._http.get("/organizations/usage")
        return UsageInfo.model_validate(data)

    def get_members(self, org_id: str) -> builtins.list[OrganizationMember]:
        """Get organization members."""
        data = self._http.get(f"/organizations/{org_id}/members")
        return [OrganizationMember.model_validate(item) for item in data]

    def check_slug(self, slug: str) -> CheckSlugResponse:
        """Check if a slug is available."""
        data = self._http.get("/organizations/check-slug", params={"slug": slug})
        return CheckSlugResponse.model_validate(data)

    def generate_slug(self, name: str) -> GenerateSlugResponse:
        """Generate a slug from a name."""
        data = self._http.post("/organizations/generate-slug", body={"name": name})
        return GenerateSlugResponse.model_validate(data)

    def get_webhook_token(self) -> WebhookTokenResponse:
        """Get the webhook token for the organization."""
        data = self._http.get("/organizations/webhook-token")
        return WebhookTokenResponse.model_validate(data)

    def regenerate_webhook_token(self) -> WebhookTokenResponse:
        """Regenerate the webhook token."""
        data = self._http.post("/organizations/webhook-token/regenerate")
        return WebhookTokenResponse.model_validate(data)

    def clear_webhook_token(self) -> None:
        """Clear the webhook token."""
        self._http.post("/organizations/webhook-token/clear", body={"confirm": True})


class AsyncOrganizationsResource(AsyncBaseResource):
    """Organizations resource (async)."""

    async def create(
        self, params: CreateOrganizationParams | dict[str, Any]
    ) -> CreateOrganizationResponse:
        """Create a new organization."""
        if isinstance(params, dict):
            params = CreateOrganizationParams.model_validate(params)
        data = await self._http.post("/organizations", params.model_dump(exclude_none=True))
        return CreateOrganizationResponse.model_validate(data)

    async def list(self) -> builtins.list[OrganizationSummary]:
        """List organizations."""
        data = await self._http.get("/organizations")
        return [OrganizationSummary.model_validate(item) for item in data]

    async def get(self, org_id: str) -> Organization:
        """Get an organization by ID."""
        data = await self._http.get(f"/organizations/{org_id}")
        return Organization.model_validate(data)

    async def update(
        self, org_id: str, params: UpdateOrganizationParams | dict[str, Any]
    ) -> Organization:
        """Update an organization."""
        if isinstance(params, dict):
            params = UpdateOrganizationParams.model_validate(params)
        data = await self._http.put(
            f"/organizations/{org_id}", params.model_dump(exclude_none=True)
        )
        return Organization.model_validate(data)

    async def delete(self, org_id: str) -> None:
        """Delete an organization."""
        await self._http.delete(f"/organizations/{org_id}")

    async def get_usage(self) -> UsageInfo:
        """Get usage and limits for current organization."""
        data = await self._http.get("/organizations/usage")
        return UsageInfo.model_validate(data)

    async def get_members(self, org_id: str) -> builtins.list[OrganizationMember]:
        """Get organization members."""
        data = await self._http.get(f"/organizations/{org_id}/members")
        return [OrganizationMember.model_validate(item) for item in data]

    async def check_slug(self, slug: str) -> CheckSlugResponse:
        """Check if a slug is available."""
        data = await self._http.get("/organizations/check-slug", params={"slug": slug})
        return CheckSlugResponse.model_validate(data)

    async def generate_slug(self, name: str) -> GenerateSlugResponse:
        """Generate a slug from a name."""
        data = await self._http.post("/organizations/generate-slug", body={"name": name})
        return GenerateSlugResponse.model_validate(data)

    async def get_webhook_token(self) -> WebhookTokenResponse:
        """Get the webhook token for the organization."""
        data = await self._http.get("/organizations/webhook-token")
        return WebhookTokenResponse.model_validate(data)

    async def regenerate_webhook_token(self) -> WebhookTokenResponse:
        """Regenerate the webhook token."""
        data = await self._http.post("/organizations/webhook-token/regenerate")
        return WebhookTokenResponse.model_validate(data)

    async def clear_webhook_token(self) -> None:
        """Clear the webhook token."""
        await self._http.post("/organizations/webhook-token/clear", body={"confirm": True})
