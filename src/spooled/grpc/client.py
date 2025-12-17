"""
gRPC client for Spooled SDK.

Note: Requires the 'grpc' extra: pip install spooled[grpc]
"""

from __future__ import annotations

from typing import Any, Generator

from pydantic import BaseModel, Field

# Optional gRPC imports
try:
    import grpc

    HAS_GRPC = True
except ImportError:
    HAS_GRPC = False
    grpc = None  # type: ignore


class EnqueueRequest(BaseModel):
    """Request for enqueueing a job via gRPC."""

    queue_name: str = Field(..., min_length=1, max_length=100)
    payload: dict[str, Any]
    priority: int = Field(default=0, ge=-100, le=100)
    max_retries: int = Field(default=3, ge=0, le=100)
    timeout_seconds: int = Field(default=300, ge=1, le=86400)
    idempotency_key: str | None = None

    model_config = {"extra": "forbid"}


class EnqueueResponse(BaseModel):
    """Response from enqueueing a job via gRPC."""

    job_id: str
    created: bool


class DequeueRequest(BaseModel):
    """Request for dequeueing jobs via gRPC."""

    queue_name: str = Field(..., min_length=1, max_length=100)
    worker_id: str
    batch_size: int = Field(default=1, ge=1, le=100)
    lease_duration_secs: int = Field(default=30, ge=5, le=3600)

    model_config = {"extra": "forbid"}


class GrpcJob(BaseModel):
    """Job received via gRPC."""

    id: str
    queue_name: str
    payload: dict[str, Any]
    retry_count: int
    max_retries: int
    timeout_seconds: int


class DequeueResponse(BaseModel):
    """Response from dequeueing jobs via gRPC."""

    jobs: list[GrpcJob]


class CompleteRequest(BaseModel):
    """Request for completing a job via gRPC."""

    job_id: str
    worker_id: str
    result: dict[str, Any] | None = None

    model_config = {"extra": "forbid"}


class FailRequest(BaseModel):
    """Request for failing a job via gRPC."""

    job_id: str
    worker_id: str
    error: str = Field(..., min_length=1, max_length=2048)

    model_config = {"extra": "forbid"}


class RegisterWorkerRequest(BaseModel):
    """Request for registering a worker via gRPC."""

    queue_name: str = Field(..., min_length=1, max_length=100)
    hostname: str
    max_concurrency: int = Field(default=5, ge=1, le=100)

    model_config = {"extra": "forbid"}


class RegisterWorkerResponse(BaseModel):
    """Response from registering a worker via gRPC."""

    worker_id: str


class WorkerHeartbeatRequest(BaseModel):
    """Request for worker heartbeat via gRPC."""

    worker_id: str
    current_jobs: int = Field(ge=0)
    status: str = "healthy"

    model_config = {"extra": "forbid"}


class GrpcQueueService:
    """gRPC Queue service methods."""

    def __init__(self, channel: Any, api_key: str) -> None:
        self._channel = channel
        self._api_key = api_key
        self._metadata = [("authorization", f"Bearer {api_key}")]

    def enqueue(
        self,
        queue_name: str,
        payload: dict[str, Any],
        *,
        priority: int = 0,
        max_retries: int = 3,
        timeout_seconds: int = 300,
        idempotency_key: str | None = None,
    ) -> EnqueueResponse:
        """Enqueue a job via gRPC."""
        # This is a stub - actual implementation would use generated protobuf stubs
        raise NotImplementedError(
            "gRPC stub generation required. Run scripts/generate_grpc.sh first."
        )

    def dequeue(
        self,
        queue_name: str,
        worker_id: str,
        *,
        batch_size: int = 1,
        lease_duration_secs: int = 30,
    ) -> DequeueResponse:
        """Dequeue jobs via gRPC."""
        raise NotImplementedError(
            "gRPC stub generation required. Run scripts/generate_grpc.sh first."
        )

    def complete(
        self,
        job_id: str,
        worker_id: str,
        result: dict[str, Any] | None = None,
    ) -> None:
        """Complete a job via gRPC."""
        raise NotImplementedError(
            "gRPC stub generation required. Run scripts/generate_grpc.sh first."
        )

    def fail(self, job_id: str, worker_id: str, error: str) -> None:
        """Fail a job via gRPC."""
        raise NotImplementedError(
            "gRPC stub generation required. Run scripts/generate_grpc.sh first."
        )

    def stream_jobs(
        self,
        queue_name: str,
        worker_id: str,
        *,
        lease_duration_secs: int = 30,
    ) -> Generator[GrpcJob, None, None]:
        """Stream jobs via gRPC (server-side streaming)."""
        raise NotImplementedError(
            "gRPC stub generation required. Run scripts/generate_grpc.sh first."
        )


class GrpcWorkersService:
    """gRPC Workers service methods."""

    def __init__(self, channel: Any, api_key: str) -> None:
        self._channel = channel
        self._api_key = api_key
        self._metadata = [("authorization", f"Bearer {api_key}")]

    def register(
        self,
        queue_name: str,
        hostname: str,
        *,
        max_concurrency: int = 5,
    ) -> RegisterWorkerResponse:
        """Register a worker via gRPC."""
        raise NotImplementedError(
            "gRPC stub generation required. Run scripts/generate_grpc.sh first."
        )

    def heartbeat(
        self,
        worker_id: str,
        *,
        current_jobs: int = 0,
        status: str = "healthy",
    ) -> None:
        """Send worker heartbeat via gRPC."""
        raise NotImplementedError(
            "gRPC stub generation required. Run scripts/generate_grpc.sh first."
        )

    def deregister(self, worker_id: str) -> None:
        """Deregister a worker via gRPC."""
        raise NotImplementedError(
            "gRPC stub generation required. Run scripts/generate_grpc.sh first."
        )


class SpooledGrpcClient:
    """
    gRPC client for Spooled API.

    Note: Requires the 'grpc' extra: pip install spooled[grpc]

    Example:
        >>> from spooled.grpc import SpooledGrpcClient
        >>>
        >>> grpc_client = SpooledGrpcClient(
        ...     address="grpc.spooled.cloud:443",
        ...     api_key="sk_live_...",
        ... )
        >>>
        >>> # Enqueue a job
        >>> result = grpc_client.queue.enqueue(
        ...     queue_name="emails",
        ...     payload={"to": "user@example.com"},
        ... )
        >>> print(f"Job ID: {result.job_id}")
        >>>
        >>> grpc_client.close()
    """

    def __init__(
        self,
        address: str,
        api_key: str,
        *,
        use_tls: bool = True,
    ) -> None:
        """
        Initialize gRPC client.

        Args:
            address: gRPC server address (host:port)
            api_key: API key for authentication
            use_tls: Whether to use TLS (default: True)
        """
        if not HAS_GRPC:
            raise ImportError(
                "grpcio package required. Install with: pip install spooled[grpc]"
            )

        self._address = address
        self._api_key = api_key
        self._use_tls = use_tls

        # Create channel
        if use_tls:
            credentials = grpc.ssl_channel_credentials()
            self._channel = grpc.secure_channel(address, credentials)
        else:
            self._channel = grpc.insecure_channel(address)

        # Create service instances
        self._queue = GrpcQueueService(self._channel, api_key)
        self._workers = GrpcWorkersService(self._channel, api_key)

    @property
    def queue(self) -> GrpcQueueService:
        """Queue service methods."""
        return self._queue

    @property
    def workers(self) -> GrpcWorkersService:
        """Workers service methods."""
        return self._workers

    def wait_for_ready(self, timeout: float = 5.0) -> bool:
        """
        Wait for the channel to be ready.

        Args:
            timeout: Timeout in seconds

        Returns:
            True if ready, False if timeout
        """
        try:
            grpc.channel_ready_future(self._channel).result(timeout=timeout)
            return True
        except grpc.FutureTimeoutError:
            return False

    def close(self) -> None:
        """Close the gRPC channel."""
        self._channel.close()

    def __enter__(self) -> "SpooledGrpcClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


