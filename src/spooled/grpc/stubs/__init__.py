"""Generated gRPC stubs for Spooled API."""

from spooled.grpc.stubs.spooled_pb2 import (
    Job,
    JobStatus,
    EnqueueRequest,
    EnqueueResponse,
    DequeueRequest,
    DequeueResponse,
    CompleteRequest,
    CompleteResponse,
    FailRequest,
    FailResponse,
    RenewLeaseRequest,
    RenewLeaseResponse,
    GetJobRequest,
    GetJobResponse,
    GetQueueStatsRequest,
    GetQueueStatsResponse,
    StreamJobsRequest,
    ProcessRequest,
    ProcessResponse,
    ErrorResponse,
    RegisterWorkerRequest,
    RegisterWorkerResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    DeregisterRequest,
    DeregisterResponse,
)

from spooled.grpc.stubs.spooled_pb2_grpc import (
    QueueServiceStub,
    WorkerServiceStub,
)

__all__ = [
    # Messages
    "Job",
    "JobStatus",
    "EnqueueRequest",
    "EnqueueResponse",
    "DequeueRequest",
    "DequeueResponse",
    "CompleteRequest",
    "CompleteResponse",
    "FailRequest",
    "FailResponse",
    "RenewLeaseRequest",
    "RenewLeaseResponse",
    "GetJobRequest",
    "GetJobResponse",
    "GetQueueStatsRequest",
    "GetQueueStatsResponse",
    "StreamJobsRequest",
    "ProcessRequest",
    "ProcessResponse",
    "ErrorResponse",
    "RegisterWorkerRequest",
    "RegisterWorkerResponse",
    "HeartbeatRequest",
    "HeartbeatResponse",
    "DeregisterRequest",
    "DeregisterResponse",
    # Service stubs
    "QueueServiceStub",
    "WorkerServiceStub",
]

