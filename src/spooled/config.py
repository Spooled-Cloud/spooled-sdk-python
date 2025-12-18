"""
Configuration types and defaults for Spooled SDK.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

# API defaults
DEFAULT_BASE_URL = "https://api.spooled.cloud"
DEFAULT_GRPC_ADDRESS = "grpc.spooled.cloud:443"
API_BASE_PATH = "/api/v1"
DEFAULT_TIMEOUT = 30.0
DEFAULT_USER_AGENT = "spooled-python/1.0.1"


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
        api_key=config.api_key,
        access_token=config.access_token,
        refresh_token=config.refresh_token,
        admin_key=config.admin_key,
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
    if not config.api_key and not config.access_token:
        raise ValueError("Either api_key or access_token must be provided")
