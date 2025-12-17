"""
Async Spooled Client

Main entry point for the async Spooled SDK.
"""

from __future__ import annotations

from typing import Any

from spooled.config import (
    ResolvedConfig,
    SpooledClientConfig,
    resolve_config,
    validate_config,
)
from spooled.errors import AuthenticationError
from spooled.resources.admin import AsyncAdminResource
from spooled.resources.api_keys import AsyncApiKeysResource
from spooled.resources.auth import AsyncAuthResource
from spooled.resources.billing import AsyncBillingResource
from spooled.resources.dashboard import AsyncDashboardResource
from spooled.resources.health import AsyncHealthResource
from spooled.resources.ingest import AsyncIngestResource
from spooled.resources.jobs import AsyncJobsResource
from spooled.resources.metrics import AsyncMetricsResource
from spooled.resources.organizations import AsyncOrganizationsResource
from spooled.resources.queues import AsyncQueuesResource
from spooled.resources.schedules import AsyncSchedulesResource
from spooled.resources.webhooks import AsyncWebhooksResource
from spooled.resources.workers import AsyncWorkersResource
from spooled.resources.workflows import AsyncWorkflowsResource
from spooled.utils.async_http import create_async_http_client
from spooled.utils.circuit_breaker import create_circuit_breaker


class AsyncSpooledClient:
    """
    Spooled Cloud SDK Client (asynchronous).

    Example:
        >>> from spooled import AsyncSpooledClient
        >>> async with AsyncSpooledClient(api_key="sk_live_...") as client:
        ...     result = await client.jobs.create({
        ...         "queue_name": "my-queue",
        ...         "payload": {"message": "Hello, World!"}
        ...     })
        ...     queues = await client.queues.list()
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        access_token: str | None = None,
        refresh_token: str | None = None,
        admin_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        debug: bool = False,
        config: SpooledClientConfig | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the async Spooled client.

        Args:
            api_key: API key for authentication (sk_live_... or sk_test_...)
            access_token: JWT access token (alternative to api_key)
            refresh_token: JWT refresh token for auto-refresh
            admin_key: Admin key for admin operations
            base_url: API base URL (default: https://api.spooled.cloud)
            timeout: Request timeout in seconds
            debug: Enable debug logging
            config: Full configuration object (overrides other params)
        """
        # Build config from params or use provided config
        if config is not None:
            self._config = resolve_config(config)
        else:
            config_params: dict[str, Any] = {
                "api_key": api_key,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "admin_key": admin_key,
                "debug": debug,
                **kwargs,
            }
            if base_url is not None:
                config_params["base_url"] = base_url
            if timeout is not None:
                config_params["timeout"] = timeout

            # Remove None values
            config_params = {k: v for k, v in config_params.items() if v is not None}
            self._config = resolve_config(SpooledClientConfig(**config_params))

        validate_config(self._config)

        # Create circuit breaker
        self._circuit_breaker = create_circuit_breaker(self._config.circuit_breaker)

        # Create HTTP client
        self._http = create_async_http_client(self._config, self._circuit_breaker)

        # Token refresh state
        self._token_expires_at: float | None = None

        # Set up token refresh if using JWT
        if (
            self._config.access_token
            and self._config.refresh_token
            and self._config.auto_refresh_token
        ):
            self._http.set_refresh_token_fn(self._refresh_access_token)

        # Create resource instances
        self._auth = AsyncAuthResource(self._http)
        self._jobs = AsyncJobsResource(self._http)
        self._queues = AsyncQueuesResource(self._http)
        self._workers = AsyncWorkersResource(self._http)
        self._schedules = AsyncSchedulesResource(self._http)
        self._workflows = AsyncWorkflowsResource(self._http)
        self._webhooks = AsyncWebhooksResource(self._http)
        self._api_keys = AsyncApiKeysResource(self._http)
        self._organizations = AsyncOrganizationsResource(self._http)
        self._billing = AsyncBillingResource(self._http)
        self._dashboard = AsyncDashboardResource(self._http)
        self._health = AsyncHealthResource(self._http)
        self._metrics = AsyncMetricsResource(self._http)
        self._admin = AsyncAdminResource(self._http, self._config.admin_key)
        self._ingest = AsyncIngestResource(self._http)

        if self._config.debug_fn:
            self._config.debug_fn(
                "AsyncSpooledClient initialized",
                {
                    "base_url": self._config.base_url,
                    "has_api_key": bool(self._config.api_key),
                    "has_access_token": bool(self._config.access_token),
                },
            )

    # Resource properties

    @property
    def auth(self) -> AsyncAuthResource:
        """Authentication operations."""
        return self._auth

    @property
    def jobs(self) -> AsyncJobsResource:
        """Job operations."""
        return self._jobs

    @property
    def queues(self) -> AsyncQueuesResource:
        """Queue operations."""
        return self._queues

    @property
    def workers(self) -> AsyncWorkersResource:
        """Worker operations."""
        return self._workers

    @property
    def schedules(self) -> AsyncSchedulesResource:
        """Schedule operations."""
        return self._schedules

    @property
    def workflows(self) -> AsyncWorkflowsResource:
        """Workflow operations."""
        return self._workflows

    @property
    def webhooks(self) -> AsyncWebhooksResource:
        """Outgoing webhook operations."""
        return self._webhooks

    @property
    def api_keys(self) -> AsyncApiKeysResource:
        """API key operations."""
        return self._api_keys

    @property
    def organizations(self) -> AsyncOrganizationsResource:
        """Organization operations."""
        return self._organizations

    @property
    def billing(self) -> AsyncBillingResource:
        """Billing operations."""
        return self._billing

    @property
    def dashboard(self) -> AsyncDashboardResource:
        """Dashboard operations."""
        return self._dashboard

    @property
    def health(self) -> AsyncHealthResource:
        """Health endpoints (public)."""
        return self._health

    @property
    def metrics(self) -> AsyncMetricsResource:
        """Metrics endpoint (public)."""
        return self._metrics

    @property
    def admin(self) -> AsyncAdminResource:
        """Admin endpoints (requires admin_key)."""
        return self._admin

    @property
    def ingest(self) -> AsyncIngestResource:
        """Webhook ingestion endpoints."""
        return self._ingest

    # Token management

    async def get_jwt_token(self) -> str:
        """Get or acquire a JWT token for realtime connections."""
        # If we have an access token, use it
        if self._config.access_token:
            return self._config.access_token

        # If we only have an API key, exchange it for a JWT
        if self._config.api_key:
            response = await self.auth.login({"api_key": self._config.api_key})
            self._http.set_auth_token(response.access_token)
            # Update config with new tokens
            self._config.access_token = response.access_token
            self._config.refresh_token = response.refresh_token
            return response.access_token

        raise AuthenticationError("No authentication method available")

    async def _refresh_access_token(self) -> str:
        """Refresh the access token."""
        if not self._config.refresh_token:
            raise AuthenticationError("No refresh token available")

        response = await self.auth.refresh({"refresh_token": self._config.refresh_token})
        self._http.set_auth_token(response.access_token)
        self._config.access_token = response.access_token

        if self._config.debug_fn:
            self._config.debug_fn("Token refreshed successfully", None)

        return response.access_token

    # Configuration access

    def get_config(self) -> ResolvedConfig:
        """Get current configuration (read-only)."""
        return self._config

    def get_circuit_breaker_stats(self) -> dict:
        """Get circuit breaker statistics."""
        return self._circuit_breaker.get_stats()

    def reset_circuit_breaker(self) -> None:
        """Reset the circuit breaker."""
        self._circuit_breaker.reset()

    # Context manager

    async def close(self) -> None:
        """Close the client and release resources."""
        await self._http.close()

    async def __aenter__(self) -> AsyncSpooledClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()


async def create_async_client(
    api_key: str | None = None,
    **kwargs: Any,
) -> AsyncSpooledClient:
    """
    Create a new AsyncSpooledClient instance.

    Example:
        >>> from spooled import create_async_client
        >>> client = await create_async_client(api_key="sk_live_...")
    """
    return AsyncSpooledClient(api_key=api_key, **kwargs)


