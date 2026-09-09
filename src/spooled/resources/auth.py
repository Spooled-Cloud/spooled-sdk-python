"""
Auth resource for Spooled SDK.
"""

from __future__ import annotations

from typing import Any

from spooled.resources.base import AsyncBaseResource, BaseResource
from spooled.types.auth import (
    CheckEmailResponse,
    LoginParams,
    LoginResponse,
    MeResponse,
    RefreshParams,
    RefreshResponse,
    StartEmailLoginResponse,
    ValidateParams,
    ValidateResponse,
)


def _logout_body(http: Any, refresh_token: str | None) -> dict[str, str] | None:
    """POST /auth/logout needs refresh_token in the body or /auth/refresh survives."""
    token = refresh_token or getattr(getattr(http, "config", None), "refresh_token", None)
    if token:
        return {"refresh_token": token}
    return None


class AuthResource(BaseResource):
    """Auth resource (sync)."""

    def login(self, params: LoginParams | dict[str, Any]) -> LoginResponse:
        """Exchange API key for JWT tokens."""
        if isinstance(params, dict):
            params = LoginParams.model_validate(params)
        data = self._http.post("/auth/login", params.model_dump(exclude_none=True))
        return LoginResponse.model_validate(data)

    def refresh(self, params: RefreshParams | dict[str, Any]) -> RefreshResponse:
        """Refresh access token."""
        if isinstance(params, dict):
            params = RefreshParams.model_validate(params)
        data = self._http.post("/auth/refresh", params.model_dump(exclude_none=True))
        return RefreshResponse.model_validate(data)

    def logout(self, refresh_token: str | None = None) -> None:
        """Invalidate the access token and, when supplied, the refresh token.

        POST /auth/logout blacklists the access token from Authorization.
        Without ``refresh_token`` in the body, ``/auth/refresh`` still mints a
        new pair. The client's stored refresh token is sent when omitted.
        """
        self._http.post("/auth/logout", _logout_body(self._http, refresh_token))

    def me(self) -> MeResponse:
        """Get current user info."""
        data = self._http.get("/auth/me")
        return MeResponse.model_validate(data)

    def validate(self, params: ValidateParams | dict[str, Any]) -> ValidateResponse:
        """Validate a token."""
        if isinstance(params, dict):
            params = ValidateParams.model_validate(params)
        data = self._http.post("/auth/validate", params.model_dump(exclude_none=True))
        return ValidateResponse.model_validate(data)

    def start_email_login(self, email: str) -> StartEmailLoginResponse:
        """Start email login flow."""
        data = self._http.post("/auth/email/start", {"email": email})
        return StartEmailLoginResponse.model_validate(data)

    def check_email(self, email: str) -> CheckEmailResponse:
        """Check if an email is registered (GET /auth/check-email)."""
        data = self._http.get("/auth/check-email", params={"email": email})
        return CheckEmailResponse.model_validate(data)


class AsyncAuthResource(AsyncBaseResource):
    """Auth resource (async)."""

    async def login(self, params: LoginParams | dict[str, Any]) -> LoginResponse:
        """Exchange API key for JWT tokens."""
        if isinstance(params, dict):
            params = LoginParams.model_validate(params)
        data = await self._http.post("/auth/login", params.model_dump(exclude_none=True))
        return LoginResponse.model_validate(data)

    async def refresh(self, params: RefreshParams | dict[str, Any]) -> RefreshResponse:
        """Refresh access token."""
        if isinstance(params, dict):
            params = RefreshParams.model_validate(params)
        data = await self._http.post("/auth/refresh", params.model_dump(exclude_none=True))
        return RefreshResponse.model_validate(data)

    async def logout(self, refresh_token: str | None = None) -> None:
        """Invalidate the access token and, when supplied, the refresh token.

        POST /auth/logout blacklists the access token from Authorization.
        Without ``refresh_token`` in the body, ``/auth/refresh`` still mints a
        new pair. The client's stored refresh token is sent when omitted.
        """
        await self._http.post("/auth/logout", _logout_body(self._http, refresh_token))

    async def me(self) -> MeResponse:
        """Get current user info."""
        data = await self._http.get("/auth/me")
        return MeResponse.model_validate(data)

    async def validate(self, params: ValidateParams | dict[str, Any]) -> ValidateResponse:
        """Validate a token."""
        if isinstance(params, dict):
            params = ValidateParams.model_validate(params)
        data = await self._http.post("/auth/validate", params.model_dump(exclude_none=True))
        return ValidateResponse.model_validate(data)

    async def start_email_login(self, email: str) -> StartEmailLoginResponse:
        """Start email login flow."""
        data = await self._http.post("/auth/email/start", {"email": email})
        return StartEmailLoginResponse.model_validate(data)

    async def check_email(self, email: str) -> CheckEmailResponse:
        """Check if an email is registered (GET /auth/check-email)."""
        data = await self._http.get("/auth/check-email", params={"email": email})
        return CheckEmailResponse.model_validate(data)
