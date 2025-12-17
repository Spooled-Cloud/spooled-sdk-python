"""
gRPC module for Spooled SDK.

Provides high-performance gRPC communication with the Spooled API,
including unary calls, server-side streaming, and bidirectional streaming.

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
    >>> # Stream jobs
    >>> for job in grpc_client.queue.stream_jobs("my-queue", "worker-1"):
    ...     print(f"Received: {job.id}")
    >>>
    >>> grpc_client.close()
"""

from spooled.grpc.client import (
    GrpcCompleteRequest,
    GrpcCompleteResponse,
    GrpcDequeueRequest,
    GrpcDequeueResponse,
    GrpcDeregisterResponse,
    # Request/Response models
    GrpcEnqueueRequest,
    GrpcEnqueueResponse,
    GrpcFailRequest,
    GrpcFailResponse,
    GrpcGetJobResponse,
    GrpcHeartbeatRequest,
    GrpcHeartbeatResponse,
    GrpcJob,
    # Service classes
    GrpcQueueService,
    GrpcQueueStats,
    GrpcRegisterWorkerRequest,
    GrpcRegisterWorkerResponse,
    GrpcRenewLeaseRequest,
    GrpcRenewLeaseResponse,
    GrpcWorkersService,
    JobStream,
    ProcessJobsStream,
    ProcessRequest,
    ProcessResponse,
    # Main client
    SpooledGrpcClient,
    # Streaming types
    StreamOptions,
)

__all__ = [
    # Main client
    "SpooledGrpcClient",
    # Service classes
    "GrpcQueueService",
    "GrpcWorkersService",
    # Request/Response models
    "GrpcEnqueueRequest",
    "GrpcEnqueueResponse",
    "GrpcDequeueRequest",
    "GrpcDequeueResponse",
    "GrpcCompleteRequest",
    "GrpcCompleteResponse",
    "GrpcFailRequest",
    "GrpcFailResponse",
    "GrpcRenewLeaseRequest",
    "GrpcRenewLeaseResponse",
    "GrpcGetJobResponse",
    "GrpcQueueStats",
    "GrpcRegisterWorkerRequest",
    "GrpcRegisterWorkerResponse",
    "GrpcHeartbeatRequest",
    "GrpcHeartbeatResponse",
    "GrpcDeregisterResponse",
    "GrpcJob",
    # Streaming types
    "StreamOptions",
    "JobStream",
    "ProcessRequest",
    "ProcessResponse",
    "ProcessJobsStream",
]
