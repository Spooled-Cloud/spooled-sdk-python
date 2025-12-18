"""
Spooled Client (synchronous)

Main entry point for the Spooled SDK.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from spooled.config import (
    ResolvedConfig,
    SpooledClientConfig,
    resolve_config,
    validate_config,
)
from spooled.errors import AuthenticationError
from spooled.resources.admin import AdminResource
from spooled.resources.api_keys import ApiKeysResource
from spooled.resources.auth import AuthResource
from spooled.resources.billing import BillingResource
from spooled.resources.dashboard import DashboardResource
from spooled.resources.health import HealthResource
from spooled.resources.ingest import IngestResource
from spooled.resources.jobs import JobsResource
from spooled.resources.metrics import MetricsResource
from spooled.resources.organizations import OrganizationsResource
from spooled.resources.queues import QueuesResource
from spooled.resources.schedules import SchedulesResource
from spooled.resources.webhooks import WebhooksResource
from spooled.resources.workers import WorkersResource
from spooled.resources.workflows import WorkflowsResource
from spooled.utils.circuit_breaker import create_circuit_breaker
from spooled.utils.http import create_http_client

if TYPE_CHECKING:
    from spooled.grpc.client import SpooledGrpcClient
    from spooled.realtime.unified import SpooledRealtime


class SpooledClient:
    """
    Spooled Cloud SDK Client (synchronous).

    Example:
        >>> from spooled import SpooledClient
        >>> client = SpooledClient(api_key="sk_live_...")
        >>>
        >>> # Create a job
        >>> result = client.jobs.create({
        ...     "queue_name": "my-queue",
        ...     "payload": {"message": "Hello, World!"}
        ... })
        >>>
        >>> # List queues
        >>> queues = client.queues.list()

    Using as context manager:
        >>> with SpooledClient(api_key="sk_live_...") as client:
        ...     job = client.jobs.create({"queue_name": "test", "payload": {}})
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
        Initialize the Spooled client.

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
        self._http = create_http_client(self._config, self._circuit_breaker)

        # Token refresh state
        self._refresh_promise: str | None = None
        self._token_expires_at: float | None = None

        # Set up token refresh if using JWT
        if (
            self._config.access_token
            and self._config.refresh_token
            and self._config.auto_refresh_token
        ):
            self._http.set_refresh_token_fn(self._refresh_access_token)

        # Create resource instances
        self._auth = AuthResource(self._http)
        self._jobs = JobsResource(self._http)
        self._queues = QueuesResource(self._http)
        self._workers = WorkersResource(self._http)
        self._schedules = SchedulesResource(self._http)
        self._workflows = WorkflowsResource(self._http)
        self._webhooks = WebhooksResource(self._http)
        self._api_keys = ApiKeysResource(self._http)
        self._organizations = OrganizationsResource(self._http)
        self._billing = BillingResource(self._http)
        self._dashboard = DashboardResource(self._http)
        self._health = HealthResource(self._http)
        self._metrics = MetricsResource(self._http)
        self._admin = AdminResource(self._http, self._config.admin_key)
        self._ingest = IngestResource(self._http)

        # Lazy-loaded gRPC client
        self._grpc: SpooledGrpcClient | None = None

        if self._config.debug_fn:
            self._config.debug_fn(
                "SpooledClient initialized",
                {
                    "base_url": self._config.base_url,
                    "has_api_key": bool(self._config.api_key),
                    "has_access_token": bool(self._config.access_token),
                },
            )

    # Resource properties

    @property
    def auth(self) -> AuthResource:
        """Authentication operations."""
        return self._auth

    @property
    def jobs(self) -> JobsResource:
        """Job operations."""
        return self._jobs

    @property
    def queues(self) -> QueuesResource:
        """Queue operations."""
        return self._queues

    @property
    def workers(self) -> WorkersResource:
        """Worker operations."""
        return self._workers

    @property
    def schedules(self) -> SchedulesResource:
        """Schedule operations."""
        return self._schedules

    @property
    def workflows(self) -> WorkflowsResource:
        """Workflow operations."""
        return self._workflows

    @property
    def webhooks(self) -> WebhooksResource:
        """Outgoing webhook operations."""
        return self._webhooks

    @property
    def api_keys(self) -> ApiKeysResource:
        """API key operations."""
        return self._api_keys

    @property
    def organizations(self) -> OrganizationsResource:
        """Organization operations."""
        return self._organizations

    @property
    def billing(self) -> BillingResource:
        """Billing operations."""
        return self._billing

    @property
    def dashboard(self) -> DashboardResource:
        """Dashboard operations."""
        return self._dashboard

    @property
    def health(self) -> HealthResource:
        """Health endpoints (public)."""
        return self._health

    @property
    def metrics(self) -> MetricsResource:
        """Metrics endpoint (public)."""
        return self._metrics

    @property
    def admin(self) -> AdminResource:
        """Admin endpoints (requires admin_key)."""
        return self._admin

    @property
    def ingest(self) -> IngestResource:
        """Webhook ingestion endpoints."""
        return self._ingest

    @property
    def grpc(self) -> SpooledGrpcClient:
        """
        Get gRPC client (lazy-loaded).

        The gRPC client is created on first access.

        Example:
            >>> job = client.grpc.enqueue(
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

            # Build gRPC URL from base URL
            base_url = self._config.base_url
            if base_url.startswith("https://"):
                grpc_url = base_url.replace("https://", "")
                use_tls = True
            elif base_url.startswith("http://"):
                grpc_url = base_url.replace("http://", "")
                use_tls = False
            else:
                grpc_url = base_url
                use_tls = True

            # Extract host and use default gRPC port
            host = grpc_url.split(":")[0] if ":" in grpc_url else grpc_url
            grpc_port = 50051
            grpc_url = f"{host}:{grpc_port}"

            # Get API key or token for auth
            api_key = self._config.api_key
            if not api_key and self._config.access_token:
                api_key = self._config.access_token

            self._grpc = SpooledGrpcClient(
                address=grpc_url,
                api_key=api_key or "",
                use_tls=use_tls,
            )

        return self._grpc

    def realtime(
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
            >>> realtime = client.realtime(type="websocket")
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

        # Get JWT token for realtime authentication
        token = self.get_jwt_token()

        options = SpooledRealtimeOptions(
            base_url=self._config.base_url,
            token=token,
            type=type,
            auto_reconnect=auto_reconnect,
            max_reconnect_attempts=max_reconnect_attempts,
            reconnect_delay=reconnect_delay,
            max_reconnect_delay=max_reconnect_delay,
            debug=self._config.debug_fn,
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
    ) -> SpooledClient:
        """
        Create a new client with modified options.

        Returns a new SpooledClient instance with the specified options
        merged with the current configuration.

        Args:
            api_key: Override API key
            access_token: Override access token
            refresh_token: Override refresh token
            admin_key: Override admin key
            base_url: Override base URL
            timeout: Override timeout
            debug: Override debug flag
            **kwargs: Additional configuration options

        Returns:
            New SpooledClient instance

        Example:
            >>> # Create client with debug enabled
            >>> debug_client = client.with_options(debug=True)
            >>>
            >>> # Create client with different API key
            >>> other_client = client.with_options(api_key="sk_live_other")
        """
        # Start with current config values
        new_config: dict[str, Any] = {
            "api_key": api_key if api_key is not None else self._config.api_key,
            "access_token": access_token if access_token is not None else self._config.access_token,
            "refresh_token": refresh_token if refresh_token is not None else self._config.refresh_token,
            "admin_key": admin_key if admin_key is not None else self._config.admin_key,
            "base_url": base_url if base_url is not None else self._config.base_url,
            "timeout": timeout if timeout is not None else self._config.timeout,
            "debug": debug if debug is not None else (self._config.debug_fn is not None),
        }

        # Add any extra kwargs
        new_config.update(kwargs)

        # Remove None values
        new_config = {k: v for k, v in new_config.items() if v is not None}

        return SpooledClient(**new_config)

    # Token management

    def get_jwt_token(self) -> str:
        """Get or acquire a JWT token for realtime connections."""
        # If we have an access token, use it
        if self._config.access_token:
            return self._config.access_token

        # If we only have an API key, exchange it for a JWT
        if self._config.api_key:
            response = self.auth.login({"api_key": self._config.api_key})
            self._http.set_auth_token(response.access_token)
            # Update config with new tokens
            self._config.access_token = response.access_token
            self._config.refresh_token = response.refresh_token
            return response.access_token

        raise AuthenticationError("No authentication method available")

    def _refresh_access_token(self) -> str:
        """Refresh the access token."""
        if not self._config.refresh_token:
            raise AuthenticationError("No refresh token available")

        response = self.auth.refresh({"refresh_token": self._config.refresh_token})
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

    def close(self) -> None:
        """Close the client and release resources."""
        self._http.close()

        # Close gRPC client if it was created
        if self._grpc is not None:
            self._grpc.close()
            self._grpc = None

    def __enter__(self) -> SpooledClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


def create_client(
    api_key: str | None = None,
    **kwargs: Any,
) -> SpooledClient:
    """
    Create a new SpooledClient instance.

    Example:
        >>> from spooled import create_client
        >>> client = create_client(api_key="sk_live_...")
    """
    return SpooledClient(api_key=api_key, **kwargs)
