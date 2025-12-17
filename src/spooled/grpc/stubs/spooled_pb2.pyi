import datetime
from collections.abc import Iterable as _Iterable
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar

from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper

DESCRIPTOR: _descriptor.FileDescriptor

class JobStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    JOB_STATUS_UNSPECIFIED: _ClassVar[JobStatus]
    JOB_STATUS_PENDING: _ClassVar[JobStatus]
    JOB_STATUS_SCHEDULED: _ClassVar[JobStatus]
    JOB_STATUS_PROCESSING: _ClassVar[JobStatus]
    JOB_STATUS_COMPLETED: _ClassVar[JobStatus]
    JOB_STATUS_FAILED: _ClassVar[JobStatus]
    JOB_STATUS_DEADLETTER: _ClassVar[JobStatus]
    JOB_STATUS_CANCELLED: _ClassVar[JobStatus]
JOB_STATUS_UNSPECIFIED: JobStatus
JOB_STATUS_PENDING: JobStatus
JOB_STATUS_SCHEDULED: JobStatus
JOB_STATUS_PROCESSING: JobStatus
JOB_STATUS_COMPLETED: JobStatus
JOB_STATUS_FAILED: JobStatus
JOB_STATUS_DEADLETTER: JobStatus
JOB_STATUS_CANCELLED: JobStatus

class Job(_message.Message):
    __slots__ = ("id", "organization_id", "queue_name", "status", "payload", "result", "retry_count", "max_retries", "last_error", "priority", "timeout_seconds", "created_at", "scheduled_at", "started_at", "completed_at", "lease_expires_at", "assigned_worker_id", "idempotency_key")
    ID_FIELD_NUMBER: _ClassVar[int]
    ORGANIZATION_ID_FIELD_NUMBER: _ClassVar[int]
    QUEUE_NAME_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    RETRY_COUNT_FIELD_NUMBER: _ClassVar[int]
    MAX_RETRIES_FIELD_NUMBER: _ClassVar[int]
    LAST_ERROR_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_SECONDS_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    SCHEDULED_AT_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    COMPLETED_AT_FIELD_NUMBER: _ClassVar[int]
    LEASE_EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    ASSIGNED_WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    id: str
    organization_id: str
    queue_name: str
    status: JobStatus
    payload: _struct_pb2.Struct
    result: _struct_pb2.Struct
    retry_count: int
    max_retries: int
    last_error: str
    priority: int
    timeout_seconds: int
    created_at: _timestamp_pb2.Timestamp
    scheduled_at: _timestamp_pb2.Timestamp
    started_at: _timestamp_pb2.Timestamp
    completed_at: _timestamp_pb2.Timestamp
    lease_expires_at: _timestamp_pb2.Timestamp
    assigned_worker_id: str
    idempotency_key: str
    def __init__(self, id: str | None = ..., organization_id: str | None = ..., queue_name: str | None = ..., status: JobStatus | str | None = ..., payload: _struct_pb2.Struct | _Mapping | None = ..., result: _struct_pb2.Struct | _Mapping | None = ..., retry_count: int | None = ..., max_retries: int | None = ..., last_error: str | None = ..., priority: int | None = ..., timeout_seconds: int | None = ..., created_at: datetime.datetime | _timestamp_pb2.Timestamp | _Mapping | None = ..., scheduled_at: datetime.datetime | _timestamp_pb2.Timestamp | _Mapping | None = ..., started_at: datetime.datetime | _timestamp_pb2.Timestamp | _Mapping | None = ..., completed_at: datetime.datetime | _timestamp_pb2.Timestamp | _Mapping | None = ..., lease_expires_at: datetime.datetime | _timestamp_pb2.Timestamp | _Mapping | None = ..., assigned_worker_id: str | None = ..., idempotency_key: str | None = ...) -> None: ...

class EnqueueRequest(_message.Message):
    __slots__ = ("queue_name", "payload", "priority", "max_retries", "timeout_seconds", "scheduled_at", "idempotency_key", "tags")
    class TagsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: str | None = ..., value: str | None = ...) -> None: ...
    QUEUE_NAME_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    MAX_RETRIES_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_SECONDS_FIELD_NUMBER: _ClassVar[int]
    SCHEDULED_AT_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    queue_name: str
    payload: _struct_pb2.Struct
    priority: int
    max_retries: int
    timeout_seconds: int
    scheduled_at: _timestamp_pb2.Timestamp
    idempotency_key: str
    tags: _containers.ScalarMap[str, str]
    def __init__(self, queue_name: str | None = ..., payload: _struct_pb2.Struct | _Mapping | None = ..., priority: int | None = ..., max_retries: int | None = ..., timeout_seconds: int | None = ..., scheduled_at: datetime.datetime | _timestamp_pb2.Timestamp | _Mapping | None = ..., idempotency_key: str | None = ..., tags: _Mapping[str, str] | None = ...) -> None: ...

class EnqueueResponse(_message.Message):
    __slots__ = ("job_id", "created")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    created: bool
    def __init__(self, job_id: str | None = ..., created: bool = ...) -> None: ...

class DequeueRequest(_message.Message):
    __slots__ = ("queue_name", "worker_id", "lease_duration_secs", "batch_size")
    QUEUE_NAME_FIELD_NUMBER: _ClassVar[int]
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    LEASE_DURATION_SECS_FIELD_NUMBER: _ClassVar[int]
    BATCH_SIZE_FIELD_NUMBER: _ClassVar[int]
    queue_name: str
    worker_id: str
    lease_duration_secs: int
    batch_size: int
    def __init__(self, queue_name: str | None = ..., worker_id: str | None = ..., lease_duration_secs: int | None = ..., batch_size: int | None = ...) -> None: ...

class DequeueResponse(_message.Message):
    __slots__ = ("jobs",)
    JOBS_FIELD_NUMBER: _ClassVar[int]
    jobs: _containers.RepeatedCompositeFieldContainer[Job]
    def __init__(self, jobs: _Iterable[Job | _Mapping] | None = ...) -> None: ...

class CompleteRequest(_message.Message):
    __slots__ = ("job_id", "worker_id", "result")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    worker_id: str
    result: _struct_pb2.Struct
    def __init__(self, job_id: str | None = ..., worker_id: str | None = ..., result: _struct_pb2.Struct | _Mapping | None = ...) -> None: ...

class CompleteResponse(_message.Message):
    __slots__ = ("success",)
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    def __init__(self, success: bool = ...) -> None: ...

class FailRequest(_message.Message):
    __slots__ = ("job_id", "worker_id", "error", "retry")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    RETRY_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    worker_id: str
    error: str
    retry: bool
    def __init__(self, job_id: str | None = ..., worker_id: str | None = ..., error: str | None = ..., retry: bool = ...) -> None: ...

class FailResponse(_message.Message):
    __slots__ = ("success", "will_retry", "next_retry_delay_secs")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    WILL_RETRY_FIELD_NUMBER: _ClassVar[int]
    NEXT_RETRY_DELAY_SECS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    will_retry: bool
    next_retry_delay_secs: int
    def __init__(self, success: bool = ..., will_retry: bool = ..., next_retry_delay_secs: int | None = ...) -> None: ...

class RenewLeaseRequest(_message.Message):
    __slots__ = ("job_id", "worker_id", "extension_secs")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    EXTENSION_SECS_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    worker_id: str
    extension_secs: int
    def __init__(self, job_id: str | None = ..., worker_id: str | None = ..., extension_secs: int | None = ...) -> None: ...

class RenewLeaseResponse(_message.Message):
    __slots__ = ("success", "new_expires_at")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    NEW_EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    success: bool
    new_expires_at: _timestamp_pb2.Timestamp
    def __init__(self, success: bool = ..., new_expires_at: datetime.datetime | _timestamp_pb2.Timestamp | _Mapping | None = ...) -> None: ...

class GetJobRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    def __init__(self, job_id: str | None = ...) -> None: ...

class GetJobResponse(_message.Message):
    __slots__ = ("job",)
    JOB_FIELD_NUMBER: _ClassVar[int]
    job: Job
    def __init__(self, job: Job | _Mapping | None = ...) -> None: ...

class GetQueueStatsRequest(_message.Message):
    __slots__ = ("queue_name",)
    QUEUE_NAME_FIELD_NUMBER: _ClassVar[int]
    queue_name: str
    def __init__(self, queue_name: str | None = ...) -> None: ...

class GetQueueStatsResponse(_message.Message):
    __slots__ = ("queue_name", "pending", "scheduled", "processing", "completed", "failed", "deadletter", "total", "max_age_ms")
    QUEUE_NAME_FIELD_NUMBER: _ClassVar[int]
    PENDING_FIELD_NUMBER: _ClassVar[int]
    SCHEDULED_FIELD_NUMBER: _ClassVar[int]
    PROCESSING_FIELD_NUMBER: _ClassVar[int]
    COMPLETED_FIELD_NUMBER: _ClassVar[int]
    FAILED_FIELD_NUMBER: _ClassVar[int]
    DEADLETTER_FIELD_NUMBER: _ClassVar[int]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    MAX_AGE_MS_FIELD_NUMBER: _ClassVar[int]
    queue_name: str
    pending: int
    scheduled: int
    processing: int
    completed: int
    failed: int
    deadletter: int
    total: int
    max_age_ms: int
    def __init__(self, queue_name: str | None = ..., pending: int | None = ..., scheduled: int | None = ..., processing: int | None = ..., completed: int | None = ..., failed: int | None = ..., deadletter: int | None = ..., total: int | None = ..., max_age_ms: int | None = ...) -> None: ...

class StreamJobsRequest(_message.Message):
    __slots__ = ("queue_name", "worker_id", "lease_duration_secs")
    QUEUE_NAME_FIELD_NUMBER: _ClassVar[int]
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    LEASE_DURATION_SECS_FIELD_NUMBER: _ClassVar[int]
    queue_name: str
    worker_id: str
    lease_duration_secs: int
    def __init__(self, queue_name: str | None = ..., worker_id: str | None = ..., lease_duration_secs: int | None = ...) -> None: ...

class ProcessRequest(_message.Message):
    __slots__ = ("dequeue", "complete", "fail", "renew_lease")
    DEQUEUE_FIELD_NUMBER: _ClassVar[int]
    COMPLETE_FIELD_NUMBER: _ClassVar[int]
    FAIL_FIELD_NUMBER: _ClassVar[int]
    RENEW_LEASE_FIELD_NUMBER: _ClassVar[int]
    dequeue: DequeueRequest
    complete: CompleteRequest
    fail: FailRequest
    renew_lease: RenewLeaseRequest
    def __init__(self, dequeue: DequeueRequest | _Mapping | None = ..., complete: CompleteRequest | _Mapping | None = ..., fail: FailRequest | _Mapping | None = ..., renew_lease: RenewLeaseRequest | _Mapping | None = ...) -> None: ...

class ProcessResponse(_message.Message):
    __slots__ = ("job", "complete", "fail", "renew_lease", "error")
    JOB_FIELD_NUMBER: _ClassVar[int]
    COMPLETE_FIELD_NUMBER: _ClassVar[int]
    FAIL_FIELD_NUMBER: _ClassVar[int]
    RENEW_LEASE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    job: Job
    complete: CompleteResponse
    fail: FailResponse
    renew_lease: RenewLeaseResponse
    error: ErrorResponse
    def __init__(self, job: Job | _Mapping | None = ..., complete: CompleteResponse | _Mapping | None = ..., fail: FailResponse | _Mapping | None = ..., renew_lease: RenewLeaseResponse | _Mapping | None = ..., error: ErrorResponse | _Mapping | None = ...) -> None: ...

class ErrorResponse(_message.Message):
    __slots__ = ("code", "message")
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    code: str
    message: str
    def __init__(self, code: str | None = ..., message: str | None = ...) -> None: ...

class RegisterWorkerRequest(_message.Message):
    __slots__ = ("queue_name", "hostname", "worker_type", "max_concurrency", "version", "metadata")
    class MetadataEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: str | None = ..., value: str | None = ...) -> None: ...
    QUEUE_NAME_FIELD_NUMBER: _ClassVar[int]
    HOSTNAME_FIELD_NUMBER: _ClassVar[int]
    WORKER_TYPE_FIELD_NUMBER: _ClassVar[int]
    MAX_CONCURRENCY_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    queue_name: str
    hostname: str
    worker_type: str
    max_concurrency: int
    version: str
    metadata: _containers.ScalarMap[str, str]
    def __init__(self, queue_name: str | None = ..., hostname: str | None = ..., worker_type: str | None = ..., max_concurrency: int | None = ..., version: str | None = ..., metadata: _Mapping[str, str] | None = ...) -> None: ...

class RegisterWorkerResponse(_message.Message):
    __slots__ = ("worker_id", "lease_duration_secs", "heartbeat_interval_secs")
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    LEASE_DURATION_SECS_FIELD_NUMBER: _ClassVar[int]
    HEARTBEAT_INTERVAL_SECS_FIELD_NUMBER: _ClassVar[int]
    worker_id: str
    lease_duration_secs: int
    heartbeat_interval_secs: int
    def __init__(self, worker_id: str | None = ..., lease_duration_secs: int | None = ..., heartbeat_interval_secs: int | None = ...) -> None: ...

class HeartbeatRequest(_message.Message):
    __slots__ = ("worker_id", "current_jobs", "status", "metadata")
    class MetadataEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: str | None = ..., value: str | None = ...) -> None: ...
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    CURRENT_JOBS_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    worker_id: str
    current_jobs: int
    status: str
    metadata: _containers.ScalarMap[str, str]
    def __init__(self, worker_id: str | None = ..., current_jobs: int | None = ..., status: str | None = ..., metadata: _Mapping[str, str] | None = ...) -> None: ...

class HeartbeatResponse(_message.Message):
    __slots__ = ("acknowledged", "should_drain")
    ACKNOWLEDGED_FIELD_NUMBER: _ClassVar[int]
    SHOULD_DRAIN_FIELD_NUMBER: _ClassVar[int]
    acknowledged: bool
    should_drain: bool
    def __init__(self, acknowledged: bool = ..., should_drain: bool = ...) -> None: ...

class DeregisterRequest(_message.Message):
    __slots__ = ("worker_id",)
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    worker_id: str
    def __init__(self, worker_id: str | None = ...) -> None: ...

class DeregisterResponse(_message.Message):
    __slots__ = ("success",)
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    def __init__(self, success: bool = ...) -> None: ...
