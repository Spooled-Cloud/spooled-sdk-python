"""
Spooled Cloud Python SDK

Official Python SDK for the Spooled Cloud job queue service.

Example:
    >>> from spooled import SpooledClient
    >>> client = SpooledClient(api_key="sk_live_...")
    >>> result = client.jobs.create(
    ...     queue_name="emails",
    ...     payload={"to": "user@example.com"}
    ... )
    >>> print(f"Created job: {result.id}")
"""

from spooled.config import (
    CircuitBreakerConfig,
    RetryConfig,
    SpooledClientConfig,
)
from spooled.errors import (
    AuthenticationError,
    AuthorizationError,
    CircuitBreakerOpenError,
    ConflictError,
    JobAbortedError,
    NetworkError,
    NotFoundError,
    PayloadTooLargeError,
    RateLimitError,
    ServerError,
    SpooledError,
    TimeoutError,
    ValidationError,
    is_spooled_error,
)

# Version
__version__ = "1.0.1"

# These will be imported when the client modules are created
__all__ = [
    # Version
    "__version__",
    # Configuration
    "SpooledClientConfig",
    "RetryConfig",
    "CircuitBreakerConfig",
    # Errors
    "SpooledError",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "ConflictError",
    "ValidationError",
    "PayloadTooLargeError",
    "RateLimitError",
    "ServerError",
    "NetworkError",
    "TimeoutError",
    "CircuitBreakerOpenError",
    "JobAbortedError",
    "is_spooled_error",
    # Clients
    "SpooledClient",
    "AsyncSpooledClient",
    # Worker
    "SpooledWorker",
    "AsyncSpooledWorker",
    # gRPC
    "SpooledGrpcClient",
    # Realtime
    "SpooledRealtime",
]


def __getattr__(name: str) -> type:
    """Lazy import for clients, workers, gRPC, and realtime."""
    if name == "SpooledClient":
        from spooled.client import SpooledClient

        return SpooledClient
    if name == "AsyncSpooledClient":
        from spooled.async_client import AsyncSpooledClient

        return AsyncSpooledClient
    if name == "SpooledWorker":
        from spooled.worker import SpooledWorker

        return SpooledWorker
    if name == "AsyncSpooledWorker":
        from spooled.worker import AsyncSpooledWorker

        return AsyncSpooledWorker
    if name == "SpooledGrpcClient":
        from spooled.grpc.client import SpooledGrpcClient

        return SpooledGrpcClient
    if name == "SpooledRealtime":
        from spooled.realtime.unified import SpooledRealtime

        return SpooledRealtime
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
