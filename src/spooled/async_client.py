"""
Async Spooled Client

Main entry point for the async Spooled SDK.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, Literal

from spooled.config import (
    ResolvedConfig,
    SpooledClientConfig,
    merge_client_config,
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
from spooled.utils.jwt import decode_jwt_exp, jwt_needs_refresh

if TYPE_CHECKING:
    from spooled.grpc.client import SpooledGrpcClient
    from spooled.realtime.unified import SpooledRealtime


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

        # Cached realtime JWT (exchanged from an API key). Reused across
        # (re)connects until near expiry so reconnect storms don't hammer the
        # login endpoint. The lock serialises concurrent coroutines racing to
        # refresh the same token.
        self._jwt_lock = asyncio.Lock()
        self._cached_jwt: str | None = None
        self._cached_jwt_exp: float | None = None

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

        # Lazy-loaded gRPC client
        self._grpc: SpooledGrpcClient | None = None

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

    @property
    def grpc(self) -> SpooledGrpcClient:
        """
        Get gRPC client (lazy-loaded).

        The gRPC client is created on first access.

        Example:
            >>> job = client.grpc.queue.enqueue(
            ...     queue_name="test",
            ...     payload={"task": "process"}
            ... )
        """
        if self._grpc is None:
            try:
                from spooled.grpc.client import SpooledGrpcClient
            except ImportError as e:
                raise ImportError(
                    "gRPC package required. Install with: pip install spooled[grpc]"
                ) from e

            # Use the configured gRPC address (default: grpc.spooled.cloud:443, as in
            # the docs and the other SDKs). It is a different host/port from the REST
            # API, so it must not be derived from base_url; self-hosted servers set
            # ``grpc_address`` explicitly. TLS is auto-detected: on unless the host
            # is localhost.
            grpc_address = self._config.grpc_address

            # Get API key or token for auth
            api_key = self._config.api_key
            if not api_key and self._config.access_token:
                api_key = self._config.access_token

            self._grpc = SpooledGrpcClient(
                address=grpc_address,
                api_key=api_key or "",
            )

        return self._grpc

    async def realtime(
        self,
        type: Literal["websocket", "sse"] = "websocket",
        auto_reconnect: bool = True,
        max_reconnect_attempts: int = 10,
        reconnect_delay: float = 1.0,
        max_reconnect_delay: float = 30.0,
    ) -> SpooledRealtime:
        """
        Create a unified realtime client.

        The realtime client provides a common interface for both WebSocket
        and SSE connections, matching the Node.js SDK API.

        Args:
            type: Connection type ('websocket' or 'sse')
            auto_reconnect: Whether to automatically reconnect on disconnect
            max_reconnect_attempts: Maximum reconnection attempts
            reconnect_delay: Base delay between reconnection attempts (seconds)
            max_reconnect_delay: Maximum delay between reconnection attempts

        Returns:
            SpooledRealtime client instance

        Example:
            >>> realtime = await client.realtime(type="websocket")
            >>>
            >>> @realtime.on("job.created")
            ... def on_job_created(data):
            ...     print(f"Job created: {data}")
            >>>
            >>> realtime.connect()
            >>> realtime.subscribe(SubscriptionFilter(queue="emails"))
        """
        try:
            from spooled.realtime.unified import (
                SpooledRealtime,
                SpooledRealtimeOptions,
            )
        except ImportError as e:
            raise ImportError(
                "Realtime packages required. Install with: pip install spooled[realtime]"
            ) from e

        # The realtime WebSocket endpoint requires a JWT in ?token=; exchange an
        # API key for one first rather than forwarding the raw key (which the
        # server rejects on the WS handshake). The cached JWT is reused here, so
        # repeated realtime() calls do not each hit the login endpoint. The
        # unified realtime client is synchronous: it reconnects on background
        # threads, which call back into this client for a fresh token below.
        token = await self.get_jwt_token()
        loop = asyncio.get_running_loop()

        def token_provider() -> str:
            try:
                on_loop = asyncio.get_running_loop() is loop
            except RuntimeError:
                on_loop = False
            if on_loop:
                # connect() called from async code: blocking on a coroutine of this
                # very loop would deadlock, so reuse the newest token minted so far.
                return self._cached_jwt or self._config.access_token or token
            return asyncio.run_coroutine_threadsafe(self.get_jwt_token(), loop).result(30)

        options = SpooledRealtimeOptions(
            base_url=self._config.base_url,
            ws_url=self._config.ws_url,
            token=token,
            type=type,
            auto_reconnect=auto_reconnect,
            max_reconnect_attempts=max_reconnect_attempts,
            reconnect_delay=reconnect_delay,
            max_reconnect_delay=max_reconnect_delay,
            debug=self._config.debug_fn,
            # Each (re)connect on a background thread mints a token via the cached
            # exchange, so long-lived streams survive JWT expiry.
            token_provider=token_provider,
        )

        return SpooledRealtime(options)

    def with_options(
        self,
        *,
        api_key: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
        admin_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        debug: bool | None = None,
        **kwargs: Any,
    ) -> AsyncSpooledClient:
        """
        Create a new client with modified options.

        Returns a new AsyncSpooledClient instance with the specified options
        merged with the current configuration.

        Args:
            api_key: Override API key
            access_token: Override access token
            refresh_token: Override refresh token
            admin_key: Override admin key
            base_url: Override base URL
            timeout: Override timeout
            debug: Override debug flag
            **kwargs: Any other ``SpooledClientConfig`` field to override
                (``headers``, ``retry``, ``circuit_breaker``, ``ws_url``,
                ``grpc_address``, ``connect_timeout``, ``user_agent``, ...)

        Returns:
            New AsyncSpooledClient instance

        Example:
            >>> # Create client with debug enabled
            >>> debug_client = client.with_options(debug=True)
            >>>
            >>> # Create client with different API key
            >>> other_client = client.with_options(api_key="sk_live_other")
        """
        overrides: dict[str, Any] = {
            "api_key": api_key,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "admin_key": admin_key,
            "base_url": base_url,
            "timeout": timeout,
            "debug": debug,
            **kwargs,
        }

        # Carry over the whole current configuration (headers, retry, circuit
        # breaker, user agent, timeouts, gRPC address, WebSocket URL), not just
        # the credentials: an allow-list here silently reset everything else.
        return AsyncSpooledClient(config=merge_client_config(self._config, overrides))

    # Token management

    async def get_jwt_token(self, *, force_refresh: bool = False) -> str:
        """Get or acquire a JWT token for realtime connections.

        The token is for the realtime transport only: it is never installed as
        the REST client's bearer, so an API-key client keeps authenticating its
        REST calls with the key (a JWT swapped in here expired after 24 h with
        nothing to renew it).

        A statically configured ``access_token`` is returned as-is; when a
        ``refresh_token`` is also configured it is renewed shortly before it
        expires. When only an API key is available, the JWT obtained from
        ``/auth/login`` is cached and reused across (re)connects until it is
        near expiry (decoded from the token's ``exp`` claim, refreshed ~60s
        early). This keeps reconnect storms from repeatedly hitting the login
        rate limiter. Pass ``force_refresh=True`` to bypass the cache, e.g.
        after the server rejects the current token on a WebSocket handshake.
        """
        # A user-supplied access token is used as-is, renewed only when we can.
        if self._config.access_token:
            await self._refresh_static_token_if_due()
            return self._config.access_token

        if not self._config.api_key:
            raise AuthenticationError("No authentication method available")

        async with self._jwt_lock:
            if (
                not force_refresh
                and self._cached_jwt is not None
                and not jwt_needs_refresh(self._cached_jwt_exp, time.time())
            ):
                return self._cached_jwt

            response = await self.auth.login({"api_key": self._config.api_key})
            self._cached_jwt = response.access_token
            self._cached_jwt_exp = decode_jwt_exp(response.access_token)
            return self._cached_jwt

    async def _refresh_static_token_if_due(self) -> None:
        """Renew a configured access token that is about to expire (needs a refresh token)."""
        config = self._config
        if not (config.access_token and config.refresh_token and config.auto_refresh_token):
            return
        exp = decode_jwt_exp(config.access_token)
        if exp is not None and jwt_needs_refresh(exp, time.time()):
            await self._http.refresh_now()

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

    def get_circuit_breaker_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics."""
        return self._circuit_breaker.get_stats()

    def reset_circuit_breaker(self) -> None:
        """Reset the circuit breaker."""
        self._circuit_breaker.reset()

    # Context manager

    async def close(self) -> None:
        """Close the client and release resources."""
        await self._http.close()

        # Close gRPC client if it was created
        if self._grpc is not None:
            self._grpc.close()
            self._grpc = None

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
