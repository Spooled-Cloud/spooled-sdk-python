"""
Configuration types and defaults for Spooled SDK.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from spooled._version import __version__

# API defaults
DEFAULT_BASE_URL = "https://api.spooled.cloud"
DEFAULT_GRPC_ADDRESS = "grpc.spooled.cloud:443"
API_BASE_PATH = "/api/v1"
DEFAULT_TIMEOUT = 30.0
DEFAULT_USER_AGENT = f"spooled-python/{__version__}"


class RetryConfig(BaseModel):
    """Configuration for retry behavior."""

    max_retries: int = Field(default=3, ge=0, le=10)
    base_delay: float = Field(default=1.0, gt=0)  # seconds
    max_delay: float = Field(default=30.0, gt=0)  # seconds
    factor: float = Field(default=2.0, gt=1)  # exponential factor
    jitter: bool = Field(default=True)

    model_config = {"frozen": True}


class CircuitBreakerConfig(BaseModel):
    """Configuration for circuit breaker."""

    enabled: bool = Field(default=True)
    failure_threshold: int = Field(default=5, ge=1)
    success_threshold: int = Field(default=3, ge=1)
    timeout: float = Field(default=30.0, gt=0)  # seconds

    model_config = {"frozen": True}


class SpooledClientConfig(BaseModel):
    """Configuration for SpooledClient."""

    # Authentication (at least one required)
    api_key: str | None = Field(default=None, min_length=10)
    access_token: str | None = Field(default=None)
    refresh_token: str | None = Field(default=None)
    admin_key: str | None = Field(default=None)

    # URLs
    base_url: str = Field(default=DEFAULT_BASE_URL)
    ws_url: str | None = Field(default=None)
    grpc_address: str = Field(default=DEFAULT_GRPC_ADDRESS)

    # Timeouts
    timeout: float = Field(default=DEFAULT_TIMEOUT, gt=0)
    connect_timeout: float = Field(default=10.0, gt=0)

    # Retry and resilience
    retry: RetryConfig = Field(default_factory=RetryConfig)
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)

    # Headers
    headers: dict[str, str] = Field(default_factory=dict)
    user_agent: str = Field(default=DEFAULT_USER_AGENT)

    # Token management
    auto_refresh_token: bool = Field(default=True)

    # Debug
    debug: bool = Field(default=False)

    model_config = {"extra": "forbid"}

    def get_ws_url(self) -> str:
        """Get WebSocket URL, deriving from base_url if not set."""
        if self.ws_url:
            return self.ws_url
        # Convert http(s) to ws(s)
        if self.base_url.startswith("https://"):
            return self.base_url.replace("https://", "wss://")
        return self.base_url.replace("http://", "ws://")


class ResolvedConfig(BaseModel):
    """Resolved configuration with all defaults applied."""

    api_key: str | None
    access_token: str | None
    refresh_token: str | None
    admin_key: str | None
    base_url: str
    ws_url: str
    grpc_address: str
    timeout: float
    connect_timeout: float
    retry: RetryConfig
    circuit_breaker: CircuitBreakerConfig
    headers: dict[str, str]
    user_agent: str
    auto_refresh_token: bool
    debug_fn: Callable[[str, Any], None] | None = None

    model_config = {"arbitrary_types_allowed": True}


def _normalize_credential(value: str | None) -> str | None:
    """Trim surrounding whitespace and treat an all-whitespace input as unset.

    httpx (and urllib3) reject ``Authorization: Bearer <key>\\n`` at the
    transport layer with an opaque error. Users routinely load credentials
    from ``.env`` files or ``os.getenv`` values that carry a trailing newline,
    so normalize once at config-resolve time — matching the Go, PHP, and
    Node SDKs.
    """
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def resolve_config(config: SpooledClientConfig) -> ResolvedConfig:
    """Resolve configuration with defaults."""
    debug_fn: Callable[[str, Any], None] | None = None
    if config.debug:

        def _debug(msg: str, meta: Any = None) -> None:
            if meta is not None:
                print(f"[spooled] {msg} {meta}")
            else:
                print(f"[spooled] {msg}")

        debug_fn = _debug

    return ResolvedConfig(
        api_key=_normalize_credential(config.api_key),
        access_token=_normalize_credential(config.access_token),
        refresh_token=_normalize_credential(config.refresh_token),
        admin_key=_normalize_credential(config.admin_key),
        base_url=config.base_url.rstrip("/"),
        ws_url=config.get_ws_url().rstrip("/"),
        grpc_address=config.grpc_address,
        timeout=config.timeout,
        connect_timeout=config.connect_timeout,
        retry=config.retry,
        circuit_breaker=config.circuit_breaker,
        headers=config.headers,
        user_agent=config.user_agent,
        auto_refresh_token=config.auto_refresh_token,
        debug_fn=debug_fn,
    )


def validate_config(config: ResolvedConfig) -> None:
    """Validate that configuration has required authentication."""
    # An admin key alone is enough for the /admin endpoints (X-Admin-Key header).
    if not config.api_key and not config.access_token and not config.admin_key:
        raise ValueError(
            "Either api_key or access_token must be provided "
            "(or admin_key for a client that only calls the admin endpoints)"
        )


def merge_client_config(current: ResolvedConfig, overrides: dict[str, Any]) -> SpooledClientConfig:
    """Build the config for ``with_options()``: everything in ``current`` plus ``overrides``.

    Every field is carried over -- headers, retry and circuit-breaker settings,
    user agent, timeouts, gRPC address and WebSocket URL -- not just the
    credentials and base URL. ``overrides`` entries that are ``None`` mean "keep".
    """
    merged: dict[str, Any] = {
        "api_key": current.api_key,
        "access_token": current.access_token,
        "refresh_token": current.refresh_token,
        "admin_key": current.admin_key,
        "base_url": current.base_url,
        "grpc_address": current.grpc_address,
        "timeout": current.timeout,
        "connect_timeout": current.connect_timeout,
        "retry": current.retry,
        "circuit_breaker": current.circuit_breaker,
        "headers": dict(current.headers),
        "user_agent": current.user_agent,
        "auto_refresh_token": current.auto_refresh_token,
        "debug": current.debug_fn is not None,
    }
    # ``ws_url`` is always resolved, but when it was only derived from the base
    # URL it must be derived again if ``base_url`` is overridden.
    if current.ws_url != SpooledClientConfig(base_url=current.base_url).get_ws_url().rstrip("/"):
        merged["ws_url"] = current.ws_url
    merged.update({key: value for key, value in overrides.items() if value is not None})
    return SpooledClientConfig(**merged)
