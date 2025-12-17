"""
gRPC client for Spooled SDK.

Provides high-performance gRPC communication with the Spooled API,
including support for unary calls, server-side streaming, and bidirectional streaming.

Note: Requires the 'grpc' extra: pip install spooled[grpc]
"""

from __future__ import annotations

import queue
from collections.abc import Callable, Generator, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from google.protobuf import struct_pb2, timestamp_pb2
from pydantic import BaseModel, Field

# Optional gRPC imports
try:
    import grpc

    HAS_GRPC = True
except ImportError:
    HAS_GRPC = False
    grpc = None  # type: ignore[assignment]


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Models for type-safe responses
# ─────────────────────────────────────────────────────────────────────────────


class GrpcEnqueueRequest(BaseModel):
    """Request for enqueueing a job via gRPC."""

    queue_name: str = Field(..., min_length=1, max_length=100)
    payload: dict[str, Any]
    priority: int = Field(default=0, ge=-100, le=100)
    max_retries: int = Field(default=3, ge=0, le=100)
    timeout_seconds: int = Field(default=300, ge=1, le=86400)
    idempotency_key: str | None = None
    tags: dict[str, str] | None = None

    model_config = {"extra": "forbid"}


class GrpcEnqueueResponse(BaseModel):
    """Response from enqueueing a job via gRPC."""

    job_id: str
    created: bool


class GrpcDequeueRequest(BaseModel):
    """Request for dequeueing jobs via gRPC."""

    queue_name: str = Field(..., min_length=1, max_length=100)
    worker_id: str
    batch_size: int = Field(default=1, ge=1, le=100)
    lease_duration_secs: int = Field(default=30, ge=5, le=3600)

    model_config = {"extra": "forbid"}


class GrpcJob(BaseModel):
    """Job received via gRPC."""

    id: str
    organization_id: str | None = None
    queue_name: str
    status: str
    payload: dict[str, Any]
    result: dict[str, Any] | None = None
    retry_count: int = 0
    max_retries: int = 3
    last_error: str | None = None
    priority: int = 0
    timeout_seconds: int = 300
    created_at: datetime | None = None
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    lease_expires_at: datetime | None = None
    assigned_worker_id: str | None = None
    idempotency_key: str | None = None


class GrpcDequeueResponse(BaseModel):
    """Response from dequeueing jobs via gRPC."""

    jobs: list[GrpcJob]


class GrpcCompleteRequest(BaseModel):
    """Request for completing a job via gRPC."""

    job_id: str
    worker_id: str
    result: dict[str, Any] | None = None

    model_config = {"extra": "forbid"}


class GrpcCompleteResponse(BaseModel):
    """Response from completing a job."""

    success: bool


class GrpcFailRequest(BaseModel):
    """Request for failing a job via gRPC."""

    job_id: str
    worker_id: str
    error: str = Field(..., min_length=1, max_length=2048)
    retry: bool = True

    model_config = {"extra": "forbid"}


class GrpcFailResponse(BaseModel):
    """Response from failing a job."""

    success: bool
    will_retry: bool
    next_retry_delay_secs: int = 0


class GrpcRenewLeaseRequest(BaseModel):
    """Request for renewing job lease via gRPC."""

    job_id: str
    worker_id: str
    extension_secs: int = Field(default=30, ge=5, le=3600)

    model_config = {"extra": "forbid"}


class GrpcRenewLeaseResponse(BaseModel):
    """Response from renewing job lease."""

    success: bool
    new_expires_at: datetime | None = None


class GrpcGetJobResponse(BaseModel):
    """Response from getting a job."""

    job: GrpcJob | None


class GrpcQueueStats(BaseModel):
    """Queue statistics from gRPC."""

    queue_name: str
    pending: int = 0
    scheduled: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0
    deadletter: int = 0
    total: int = 0
    max_age_ms: int = 0


class GrpcRegisterWorkerRequest(BaseModel):
    """Request for registering a worker via gRPC."""

    queue_name: str = Field(..., min_length=1, max_length=100)
    hostname: str
    worker_type: str = "python"
    max_concurrency: int = Field(default=5, ge=1, le=100)
    version: str = "1.0.0"
    metadata: dict[str, str] | None = None

    model_config = {"extra": "forbid"}


class GrpcRegisterWorkerResponse(BaseModel):
    """Response from registering a worker via gRPC."""

    worker_id: str
    lease_duration_secs: int = 30
    heartbeat_interval_secs: int = 10


class GrpcHeartbeatRequest(BaseModel):
    """Request for worker heartbeat via gRPC."""

    worker_id: str
    current_jobs: int = Field(ge=0)
    status: str = "healthy"
    metadata: dict[str, str] | None = None

    model_config = {"extra": "forbid"}


class GrpcHeartbeatResponse(BaseModel):
    """Response from worker heartbeat."""

    acknowledged: bool
    should_drain: bool = False


class GrpcDeregisterResponse(BaseModel):
    """Response from deregistering a worker."""

    success: bool


# ─────────────────────────────────────────────────────────────────────────────
# Conversion utilities
# ─────────────────────────────────────────────────────────────────────────────


def _dict_to_struct(d: dict[str, Any] | None) -> struct_pb2.Struct | None:
    """Convert a Python dict to a protobuf Struct."""
    if d is None:
        return None
    struct = struct_pb2.Struct()
    struct.update(d)
    return struct


def _struct_to_dict(struct: struct_pb2.Struct | None) -> dict[str, Any] | None:
    """Convert a protobuf Struct to a Python dict."""
    if struct is None:
        return None
    # MessageToDict preserves all nested structures
    from google.protobuf.json_format import MessageToDict

    result: dict[str, Any] = MessageToDict(struct)
    return result


def _timestamp_to_datetime(ts: timestamp_pb2.Timestamp | None) -> datetime | None:
    """Convert a protobuf Timestamp to a Python datetime."""
    if ts is None or (ts.seconds == 0 and ts.nanos == 0):
        return None
    return datetime.fromtimestamp(ts.seconds + ts.nanos / 1e9, tz=timezone.utc)


def _datetime_to_timestamp(dt: datetime | None) -> timestamp_pb2.Timestamp | None:
    """Convert a Python datetime to a protobuf Timestamp."""
    if dt is None:
        return None
    ts = timestamp_pb2.Timestamp()
    ts.FromDatetime(dt)
    return ts


def _job_status_to_str(status: int) -> str:
    """Convert JobStatus enum to string."""
    status_map = {
        0: "unspecified",
        1: "pending",
        2: "scheduled",
        3: "processing",
        4: "completed",
        5: "failed",
        6: "deadletter",
        7: "cancelled",
    }
    return status_map.get(status, "unknown")


def _proto_job_to_grpc_job(job: Any) -> GrpcJob:
    """Convert a protobuf Job to a GrpcJob model."""
    return GrpcJob(
        id=job.id,
        organization_id=job.organization_id or None,
        queue_name=job.queue_name,
        status=_job_status_to_str(job.status),
        payload=_struct_to_dict(job.payload) or {},
        result=_struct_to_dict(job.result),
        retry_count=job.retry_count,
        max_retries=job.max_retries,
        last_error=job.last_error or None,
        priority=job.priority,
        timeout_seconds=job.timeout_seconds,
        created_at=_timestamp_to_datetime(job.created_at),
        scheduled_at=_timestamp_to_datetime(job.scheduled_at),
        started_at=_timestamp_to_datetime(job.started_at),
        completed_at=_timestamp_to_datetime(job.completed_at),
        lease_expires_at=_timestamp_to_datetime(job.lease_expires_at),
        assigned_worker_id=job.assigned_worker_id or None,
        idempotency_key=job.idempotency_key or None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Streaming types
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class StreamOptions:
    """Options for streaming operations."""

    on_connected: Callable[[], None] | None = None
    on_error: Callable[[Exception], None] | None = None
    on_end: Callable[[], None] | None = None


class JobStream:
    """
    Async-like iterator for streaming jobs from the server.

    Example:
        >>> stream = grpc_client.queue.stream_jobs("my-queue", "worker-1")
        >>> for job in stream:
        ...     print(f"Received job: {job.id}")
        >>> stream.cancel()
    """

    def __init__(
        self,
        call: Any,  # grpc.CallIterator
        options: StreamOptions | None = None,
    ) -> None:
        self._call = call
        self._options = options or StreamOptions()
        self._cancelled = False

    def __iter__(self) -> Iterator[GrpcJob]:
        return self

    def __next__(self) -> GrpcJob:
        if self._cancelled:
            raise StopIteration

        try:
            proto_job = next(self._call)
            return _proto_job_to_grpc_job(proto_job)
        except StopIteration:
            if self._options.on_end:
                self._options.on_end()
            raise
        except Exception as e:
            if self._options.on_error:
                self._options.on_error(e)
            raise

    def cancel(self) -> None:
        """Cancel the stream."""
        self._cancelled = True
        if hasattr(self._call, "cancel"):
            self._call.cancel()


@dataclass
class ProcessRequest:
    """Request for bidirectional streaming."""

    dequeue: GrpcDequeueRequest | None = None
    complete: GrpcCompleteRequest | None = None
    fail: GrpcFailRequest | None = None
    renew_lease: GrpcRenewLeaseRequest | None = None


@dataclass
class ProcessResponse:
    """Response from bidirectional streaming."""

    job: GrpcJob | None = None
    complete: GrpcCompleteResponse | None = None
    fail: GrpcFailResponse | None = None
    renew_lease: GrpcRenewLeaseResponse | None = None
    error: str | None = None


class ProcessJobsStream:
    """
    Bidirectional stream for processing jobs.

    Example:
        >>> stream = grpc_client.queue.process_jobs()
        >>> stream.send(ProcessRequest(dequeue=GrpcDequeueRequest(...)))
        >>> for response in stream.receive():
        ...     if response.job:
        ...         process(response.job)
        ...         stream.send(ProcessRequest(complete=GrpcCompleteRequest(...)))
        >>> stream.end()
    """

    def __init__(
        self,
        call: Any,  # grpc.StreamStreamMultiCallable
        metadata: list[tuple[str, str]],
        options: StreamOptions | None = None,
    ) -> None:
        self._call = call
        self._metadata = metadata
        self._options = options or StreamOptions()
        self._request_queue: queue.Queue[Any] = queue.Queue()
        self._response_iterator: Any = None
        self._stream: Any = None
        self._ended = False
        self._started = False

    def _ensure_started(self) -> None:
        """Ensure the stream is started."""
        if self._started:
            return

        # Import stubs

        def request_generator() -> Generator[Any, None, None]:
            while True:
                try:
                    req = self._request_queue.get(timeout=1.0)
                    if req is None:  # End signal
                        break
                    yield req
                except queue.Empty:
                    if self._ended:
                        break
                    continue

        self._stream = self._call(request_generator(), metadata=self._metadata)
        self._started = True

    def send(self, request: ProcessRequest) -> None:
        """Send a request to the server."""
        from spooled.grpc.stubs import (
            CompleteRequest,
            DequeueRequest,
            FailRequest,
            RenewLeaseRequest,
        )
        from spooled.grpc.stubs import (
            ProcessRequest as ProtoProcessRequest,
        )

        self._ensure_started()

        proto_req = ProtoProcessRequest()

        if request.dequeue:
            proto_req.dequeue.CopyFrom(
                DequeueRequest(
                    queue_name=request.dequeue.queue_name,
                    worker_id=request.dequeue.worker_id,
                    lease_duration_secs=request.dequeue.lease_duration_secs,
                    batch_size=request.dequeue.batch_size,
                )
            )
        elif request.complete:
            proto_req.complete.CopyFrom(
                CompleteRequest(
                    job_id=request.complete.job_id,
                    worker_id=request.complete.worker_id,
                    result=_dict_to_struct(request.complete.result),
                )
            )
        elif request.fail:
            proto_req.fail.CopyFrom(
                FailRequest(
                    job_id=request.fail.job_id,
                    worker_id=request.fail.worker_id,
                    error=request.fail.error,
                    retry=request.fail.retry,
                )
            )
        elif request.renew_lease:
            proto_req.renew_lease.CopyFrom(
                RenewLeaseRequest(
                    job_id=request.renew_lease.job_id,
                    worker_id=request.renew_lease.worker_id,
                    extension_secs=request.renew_lease.extension_secs,
                )
            )

        self._request_queue.put(proto_req)

    def receive(self) -> Generator[ProcessResponse, None, None]:
        """Receive responses from the server."""
        self._ensure_started()

        try:
            for proto_resp in self._stream:
                response = ProcessResponse()

                which = proto_resp.WhichOneof("response")
                if which == "job":
                    response.job = _proto_job_to_grpc_job(proto_resp.job)
                elif which == "complete":
                    response.complete = GrpcCompleteResponse(
                        success=proto_resp.complete.success
                    )
                elif which == "fail":
                    response.fail = GrpcFailResponse(
                        success=proto_resp.fail.success,
                        will_retry=proto_resp.fail.will_retry,
                        next_retry_delay_secs=proto_resp.fail.next_retry_delay_secs,
                    )
                elif which == "renew_lease":
                    response.renew_lease = GrpcRenewLeaseResponse(
                        success=proto_resp.renew_lease.success,
                        new_expires_at=_timestamp_to_datetime(
                            proto_resp.renew_lease.new_expires_at
                        ),
                    )
                elif which == "error":
                    response.error = f"{proto_resp.error.code}: {proto_resp.error.message}"

                yield response

        except Exception as e:
            if self._options.on_error:
                self._options.on_error(e)
            raise
        finally:
            if self._options.on_end:
                self._options.on_end()

    def end(self) -> None:
        """Signal that no more requests will be sent."""
        self._ended = True
        self._request_queue.put(None)

    def cancel(self) -> None:
        """Cancel the stream."""
        self._ended = True
        self._request_queue.put(None)
        if self._stream and hasattr(self._stream, "cancel"):
            self._stream.cancel()


# ─────────────────────────────────────────────────────────────────────────────
# Service classes
# ─────────────────────────────────────────────────────────────────────────────


class GrpcQueueService:
    """
    gRPC Queue service methods.

    Provides high-performance job queue operations via gRPC.
    """

    def __init__(self, stub: Any, metadata: list[tuple[str, str]]) -> None:
        self._stub = stub
        self._metadata = metadata

    def enqueue(
        self,
        queue_name: str,
        payload: dict[str, Any],
        *,
        priority: int = 0,
        max_retries: int = 3,
        timeout_seconds: int = 300,
        idempotency_key: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> GrpcEnqueueResponse:
        """
        Enqueue a job via gRPC.

        Args:
            queue_name: Name of the queue
            payload: Job payload data
            priority: Job priority (-100 to 100)
            max_retries: Maximum retry attempts
            timeout_seconds: Job timeout in seconds
            idempotency_key: Optional idempotency key
            tags: Optional job tags

        Returns:
            GrpcEnqueueResponse with job_id and created flag
        """
        from spooled.grpc.stubs import EnqueueRequest

        request = EnqueueRequest(
            queue_name=queue_name,
            payload=_dict_to_struct(payload),
            priority=priority,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            idempotency_key=idempotency_key or "",
        )

        if tags:
            request.tags.update(tags)

        response = self._stub.Enqueue(request, metadata=self._metadata)
        return GrpcEnqueueResponse(job_id=response.job_id, created=response.created)

    def dequeue(
        self,
        queue_name: str,
        worker_id: str,
        *,
        batch_size: int = 1,
        lease_duration_secs: int = 30,
    ) -> GrpcDequeueResponse:
        """
        Dequeue jobs via gRPC.

        Args:
            queue_name: Name of the queue
            worker_id: Worker ID
            batch_size: Number of jobs to dequeue
            lease_duration_secs: Lease duration in seconds

        Returns:
            GrpcDequeueResponse with list of jobs
        """
        from spooled.grpc.stubs import DequeueRequest

        request = DequeueRequest(
            queue_name=queue_name,
            worker_id=worker_id,
            batch_size=batch_size,
            lease_duration_secs=lease_duration_secs,
        )

        response = self._stub.Dequeue(request, metadata=self._metadata)
        jobs = [_proto_job_to_grpc_job(job) for job in response.jobs]
        return GrpcDequeueResponse(jobs=jobs)

    def complete(
        self,
        job_id: str,
        worker_id: str,
        result: dict[str, Any] | None = None,
    ) -> GrpcCompleteResponse:
        """
        Complete a job via gRPC.

        Args:
            job_id: Job ID
            worker_id: Worker ID
            result: Optional result data

        Returns:
            GrpcCompleteResponse with success flag
        """
        from spooled.grpc.stubs import CompleteRequest

        request = CompleteRequest(
            job_id=job_id,
            worker_id=worker_id,
            result=_dict_to_struct(result),
        )

        response = self._stub.Complete(request, metadata=self._metadata)
        return GrpcCompleteResponse(success=response.success)

    def fail(
        self,
        job_id: str,
        worker_id: str,
        error: str,
        *,
        retry: bool = True,
    ) -> GrpcFailResponse:
        """
        Fail a job via gRPC.

        Args:
            job_id: Job ID
            worker_id: Worker ID
            error: Error message
            retry: Whether to retry the job

        Returns:
            GrpcFailResponse with success flag and retry info
        """
        from spooled.grpc.stubs import FailRequest

        request = FailRequest(
            job_id=job_id,
            worker_id=worker_id,
            error=error,
            retry=retry,
        )

        response = self._stub.Fail(request, metadata=self._metadata)
        return GrpcFailResponse(
            success=response.success,
            will_retry=response.will_retry,
            next_retry_delay_secs=response.next_retry_delay_secs,
        )

    def renew_lease(
        self,
        job_id: str,
        worker_id: str,
        extension_secs: int = 30,
    ) -> GrpcRenewLeaseResponse:
        """
        Renew a job's lease via gRPC.

        Args:
            job_id: Job ID
            worker_id: Worker ID
            extension_secs: Extension duration in seconds

        Returns:
            GrpcRenewLeaseResponse with success flag and new expiration
        """
        from spooled.grpc.stubs import RenewLeaseRequest

        request = RenewLeaseRequest(
            job_id=job_id,
            worker_id=worker_id,
            extension_secs=extension_secs,
        )

        response = self._stub.RenewLease(request, metadata=self._metadata)
        return GrpcRenewLeaseResponse(
            success=response.success,
            new_expires_at=_timestamp_to_datetime(response.new_expires_at),
        )

    def get_job(self, job_id: str) -> GrpcGetJobResponse:
        """
        Get a job by ID via gRPC.

        Args:
            job_id: Job ID

        Returns:
            GrpcGetJobResponse with job data
        """
        from spooled.grpc.stubs import GetJobRequest

        request = GetJobRequest(job_id=job_id)
        response = self._stub.GetJob(request, metadata=self._metadata)

        job = None
        if response.HasField("job"):
            job = _proto_job_to_grpc_job(response.job)

        return GrpcGetJobResponse(job=job)

    def get_queue_stats(self, queue_name: str) -> GrpcQueueStats:
        """
        Get queue statistics via gRPC.

        Args:
            queue_name: Queue name

        Returns:
            GrpcQueueStats with queue statistics
        """
        from spooled.grpc.stubs import GetQueueStatsRequest

        request = GetQueueStatsRequest(queue_name=queue_name)
        response = self._stub.GetQueueStats(request, metadata=self._metadata)

        return GrpcQueueStats(
            queue_name=response.queue_name,
            pending=response.pending,
            scheduled=response.scheduled,
            processing=response.processing,
            completed=response.completed,
            failed=response.failed,
            deadletter=response.deadletter,
            total=response.total,
            max_age_ms=response.max_age_ms,
        )

    def stream_jobs(
        self,
        queue_name: str,
        worker_id: str,
        *,
        lease_duration_secs: int = 30,
        options: StreamOptions | None = None,
    ) -> JobStream:
        """
        Stream jobs from a queue (server-side streaming).

        This opens a persistent connection to the server and receives jobs
        as they become available.

        Args:
            queue_name: Name of the queue
            worker_id: Worker ID
            lease_duration_secs: Lease duration for claimed jobs
            options: Stream options for callbacks

        Returns:
            JobStream that yields jobs as they arrive

        Example:
            >>> stream = grpc_client.queue.stream_jobs("my-queue", "worker-1")
            >>> for job in stream:
            ...     print(f"Processing: {job.id}")
            ...     # Process job...
            ...     grpc_client.queue.complete(job.id, "worker-1")
            >>> stream.cancel()
        """
        from spooled.grpc.stubs import StreamJobsRequest

        request = StreamJobsRequest(
            queue_name=queue_name,
            worker_id=worker_id,
            lease_duration_secs=lease_duration_secs,
        )

        call = self._stub.StreamJobs(request, metadata=self._metadata)

        if options and options.on_connected:
            options.on_connected()

        return JobStream(call, options)

    def process_jobs(self, options: StreamOptions | None = None) -> ProcessJobsStream:
        """
        Open a bidirectional stream for processing jobs.

        This allows sending requests and receiving responses over a single
        persistent connection.

        Args:
            options: Stream options for callbacks

        Returns:
            ProcessJobsStream for bidirectional communication

        Example:
            >>> stream = grpc_client.queue.process_jobs()
            >>>
            >>> # Request jobs
            >>> stream.send(ProcessRequest(dequeue=GrpcDequeueRequest(
            ...     queue_name="my-queue",
            ...     worker_id="worker-1",
            ...     batch_size=5,
            ... )))
            >>>
            >>> # Process responses
            >>> for response in stream.receive():
            ...     if response.job:
            ...         # Process the job
            ...         stream.send(ProcessRequest(complete=GrpcCompleteRequest(
            ...             job_id=response.job.id,
            ...             worker_id="worker-1",
            ...         )))
            ...     elif response.error:
            ...         print(f"Error: {response.error}")
            >>>
            >>> stream.end()
        """
        return ProcessJobsStream(
            self._stub.ProcessJobs,
            self._metadata,
            options,
        )


class GrpcWorkersService:
    """
    gRPC Workers service methods.

    Provides worker registration, heartbeat, and deregistration via gRPC.
    """

    def __init__(self, stub: Any, metadata: list[tuple[str, str]]) -> None:
        self._stub = stub
        self._metadata = metadata

    def register(
        self,
        queue_name: str,
        hostname: str,
        *,
        worker_type: str = "python",
        max_concurrency: int = 5,
        version: str = "1.0.0",
        metadata: dict[str, str] | None = None,
    ) -> GrpcRegisterWorkerResponse:
        """
        Register a worker via gRPC.

        Args:
            queue_name: Queue to process jobs from
            hostname: Worker hostname
            worker_type: Worker type identifier
            max_concurrency: Maximum concurrent jobs
            version: Worker version
            metadata: Additional worker metadata

        Returns:
            GrpcRegisterWorkerResponse with worker_id and timing info
        """
        from spooled.grpc.stubs import RegisterWorkerRequest

        request = RegisterWorkerRequest(
            queue_name=queue_name,
            hostname=hostname,
            worker_type=worker_type,
            max_concurrency=max_concurrency,
            version=version,
        )

        if metadata:
            request.metadata.update(metadata)

        response = self._stub.Register(request, metadata=self._metadata)
        return GrpcRegisterWorkerResponse(
            worker_id=response.worker_id,
            lease_duration_secs=response.lease_duration_secs,
            heartbeat_interval_secs=response.heartbeat_interval_secs,
        )

    def heartbeat(
        self,
        worker_id: str,
        *,
        current_jobs: int = 0,
        status: str = "healthy",
        metadata: dict[str, str] | None = None,
    ) -> GrpcHeartbeatResponse:
        """
        Send worker heartbeat via gRPC.

        Args:
            worker_id: Worker ID
            current_jobs: Number of jobs currently processing
            status: Worker status
            metadata: Additional heartbeat metadata

        Returns:
            GrpcHeartbeatResponse with acknowledgment and drain signal
        """
        from spooled.grpc.stubs import HeartbeatRequest

        request = HeartbeatRequest(
            worker_id=worker_id,
            current_jobs=current_jobs,
            status=status,
        )

        if metadata:
            request.metadata.update(metadata)

        response = self._stub.Heartbeat(request, metadata=self._metadata)
        return GrpcHeartbeatResponse(
            acknowledged=response.acknowledged,
            should_drain=response.should_drain,
        )

    def deregister(self, worker_id: str) -> GrpcDeregisterResponse:
        """
        Deregister a worker via gRPC.

        Args:
            worker_id: Worker ID to deregister

        Returns:
            GrpcDeregisterResponse with success flag
        """
        from spooled.grpc.stubs import DeregisterRequest

        request = DeregisterRequest(worker_id=worker_id)
        response = self._stub.Deregister(request, metadata=self._metadata)
        return GrpcDeregisterResponse(success=response.success)


# ─────────────────────────────────────────────────────────────────────────────
# Main client class
# ─────────────────────────────────────────────────────────────────────────────


class SpooledGrpcClient:
    """
    gRPC client for Spooled API.

    Provides high-performance communication with the Spooled API using gRPC.
    Supports unary calls, server-side streaming, and bidirectional streaming.

    Note: Requires the 'grpc' extra: pip install spooled[grpc]

    Example:
        >>> from spooled.grpc import SpooledGrpcClient
        >>>
        >>> grpc_client = SpooledGrpcClient(
        ...     address="grpc.spooled.cloud:443",
        ...     api_key="sk_live_...",
        ... )
        >>>
        >>> # Wait for connection
        >>> grpc_client.wait_for_ready(timeout=5.0)
        >>>
        >>> # Enqueue a job
        >>> result = grpc_client.queue.enqueue(
        ...     queue_name="emails",
        ...     payload={"to": "user@example.com"},
        ... )
        >>> print(f"Job ID: {result.job_id}")
        >>>
        >>> # Stream jobs (server-side streaming)
        >>> for job in grpc_client.queue.stream_jobs("my-queue", "worker-1"):
        ...     print(f"Received: {job.id}")
        ...     grpc_client.queue.complete(job.id, "worker-1")
        >>>
        >>> grpc_client.close()
    """

    def __init__(
        self,
        address: str,
        api_key: str,
        *,
        use_tls: bool | None = None,
        root_certificates: bytes | None = None,
        options: list[tuple[str, Any]] | None = None,
    ) -> None:
        """
        Initialize gRPC client.

        Args:
            address: gRPC server address (host:port)
            api_key: API key for authentication
            use_tls: Whether to use TLS. If None, auto-detect from address.
            root_certificates: Custom root certificates for TLS
            options: Additional gRPC channel options
        """
        if not HAS_GRPC:
            raise ImportError(
                "grpcio package required. Install with: pip install spooled[grpc]"
            )

        self._address = address
        self._api_key = api_key

        # Auto-detect TLS based on address
        if use_tls is None:
            host = address.split(":")[0].lower()
            use_tls = host not in ("localhost", "127.0.0.1", "[::1]")

        self._use_tls = use_tls

        # Create metadata with API key
        self._metadata = [("x-api-key", api_key)]

        # Create channel
        channel_options = options or []
        if use_tls:
            credentials = grpc.ssl_channel_credentials(
                root_certificates=root_certificates
            )
            self._channel = grpc.secure_channel(
                address, credentials, options=channel_options
            )
        else:
            self._channel = grpc.insecure_channel(address, options=channel_options)

        # Create service stubs (generated code without type annotations)
        from spooled.grpc.stubs import QueueServiceStub, WorkerServiceStub

        self._queue_stub = QueueServiceStub(self._channel)  # type: ignore[no-untyped-call]
        self._worker_stub = WorkerServiceStub(self._channel)  # type: ignore[no-untyped-call]

        # Create service instances
        self._queue = GrpcQueueService(self._queue_stub, self._metadata)
        self._workers = GrpcWorkersService(self._worker_stub, self._metadata)

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

    def get_state(self, try_to_connect: bool = False) -> str:
        """
        Get the current connection state.

        Args:
            try_to_connect: Whether to initiate connection if idle

        Returns:
            Connection state string
        """
        state = self._channel._channel.check_connectivity_state(try_to_connect)
        state_names = {
            0: "idle",
            1: "connecting",
            2: "ready",
            3: "transient_failure",
            4: "shutdown",
        }
        return state_names.get(state, "unknown")

    def close(self) -> None:
        """Close the gRPC channel."""
        self._channel.close()

    def __enter__(self) -> SpooledGrpcClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
