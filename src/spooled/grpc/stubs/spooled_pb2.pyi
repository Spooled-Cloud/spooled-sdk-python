import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

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
    def __init__(self, id: _Optional[str] = ..., organization_id: _Optional[str] = ..., queue_name: _Optional[str] = ..., status: _Optional[_Union[JobStatus, str]] = ..., payload: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., result: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., retry_count: _Optional[int] = ..., max_retries: _Optional[int] = ..., last_error: _Optional[str] = ..., priority: _Optional[int] = ..., timeout_seconds: _Optional[int] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., scheduled_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., started_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., completed_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., lease_expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., assigned_worker_id: _Optional[str] = ..., idempotency_key: _Optional[str] = ...) -> None: ...

class EnqueueRequest(_message.Message):
    __slots__ = ("queue_name", "payload", "priority", "max_retries", "timeout_seconds", "scheduled_at", "idempotency_key", "tags")
    class TagsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
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
    def __init__(self, queue_name: _Optional[str] = ..., payload: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., priority: _Optional[int] = ..., max_retries: _Optional[int] = ..., timeout_seconds: _Optional[int] = ..., scheduled_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., idempotency_key: _Optional[str] = ..., tags: _Optional[_Mapping[str, str]] = ...) -> None: ...

class EnqueueResponse(_message.Message):
    __slots__ = ("job_id", "created")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    created: bool
    def __init__(self, job_id: _Optional[str] = ..., created: bool = ...) -> None: ...

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
    def __init__(self, queue_name: _Optional[str] = ..., worker_id: _Optional[str] = ..., lease_duration_secs: _Optional[int] = ..., batch_size: _Optional[int] = ...) -> None: ...

class DequeueResponse(_message.Message):
    __slots__ = ("jobs",)
    JOBS_FIELD_NUMBER: _ClassVar[int]
    jobs: _containers.RepeatedCompositeFieldContainer[Job]
    def __init__(self, jobs: _Optional[_Iterable[_Union[Job, _Mapping]]] = ...) -> None: ...

class CompleteRequest(_message.Message):
    __slots__ = ("job_id", "worker_id", "result")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    worker_id: str
    result: _struct_pb2.Struct
    def __init__(self, job_id: _Optional[str] = ..., worker_id: _Optional[str] = ..., result: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

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
    def __init__(self, job_id: _Optional[str] = ..., worker_id: _Optional[str] = ..., error: _Optional[str] = ..., retry: bool = ...) -> None: ...

class FailResponse(_message.Message):
    __slots__ = ("success", "will_retry", "next_retry_delay_secs")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    WILL_RETRY_FIELD_NUMBER: _ClassVar[int]
    NEXT_RETRY_DELAY_SECS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    will_retry: bool
    next_retry_delay_secs: int
    def __init__(self, success: bool = ..., will_retry: bool = ..., next_retry_delay_secs: _Optional[int] = ...) -> None: ...

class RenewLeaseRequest(_message.Message):
    __slots__ = ("job_id", "worker_id", "extension_secs")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    EXTENSION_SECS_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    worker_id: str
    extension_secs: int
    def __init__(self, job_id: _Optional[str] = ..., worker_id: _Optional[str] = ..., extension_secs: _Optional[int] = ...) -> None: ...

class RenewLeaseResponse(_message.Message):
    __slots__ = ("success", "new_expires_at")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    NEW_EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    success: bool
    new_expires_at: _timestamp_pb2.Timestamp
    def __init__(self, success: bool = ..., new_expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GetJobRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    def __init__(self, job_id: _Optional[str] = ...) -> None: ...

class GetJobResponse(_message.Message):
    __slots__ = ("job",)
    JOB_FIELD_NUMBER: _ClassVar[int]
    job: Job
    def __init__(self, job: _Optional[_Union[Job, _Mapping]] = ...) -> None: ...

class GetQueueStatsRequest(_message.Message):
    __slots__ = ("queue_name",)
    QUEUE_NAME_FIELD_NUMBER: _ClassVar[int]
    queue_name: str
    def __init__(self, queue_name: _Optional[str] = ...) -> None: ...

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
    def __init__(self, queue_name: _Optional[str] = ..., pending: _Optional[int] = ..., scheduled: _Optional[int] = ..., processing: _Optional[int] = ..., completed: _Optional[int] = ..., failed: _Optional[int] = ..., deadletter: _Optional[int] = ..., total: _Optional[int] = ..., max_age_ms: _Optional[int] = ...) -> None: ...

class StreamJobsRequest(_message.Message):
    __slots__ = ("queue_name", "worker_id", "lease_duration_secs")
    QUEUE_NAME_FIELD_NUMBER: _ClassVar[int]
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    LEASE_DURATION_SECS_FIELD_NUMBER: _ClassVar[int]
    queue_name: str
    worker_id: str
    lease_duration_secs: int
    def __init__(self, queue_name: _Optional[str] = ..., worker_id: _Optional[str] = ..., lease_duration_secs: _Optional[int] = ...) -> None: ...

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
    def __init__(self, dequeue: _Optional[_Union[DequeueRequest, _Mapping]] = ..., complete: _Optional[_Union[CompleteRequest, _Mapping]] = ..., fail: _Optional[_Union[FailRequest, _Mapping]] = ..., renew_lease: _Optional[_Union[RenewLeaseRequest, _Mapping]] = ...) -> None: ...

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
    def __init__(self, job: _Optional[_Union[Job, _Mapping]] = ..., complete: _Optional[_Union[CompleteResponse, _Mapping]] = ..., fail: _Optional[_Union[FailResponse, _Mapping]] = ..., renew_lease: _Optional[_Union[RenewLeaseResponse, _Mapping]] = ..., error: _Optional[_Union[ErrorResponse, _Mapping]] = ...) -> None: ...

class ErrorResponse(_message.Message):
    __slots__ = ("code", "message")
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    code: str
    message: str
    def __init__(self, code: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class RegisterWorkerRequest(_message.Message):
    __slots__ = ("queue_name", "hostname", "worker_type", "max_concurrency", "version", "metadata")
    class MetadataEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
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
    def __init__(self, queue_name: _Optional[str] = ..., hostname: _Optional[str] = ..., worker_type: _Optional[str] = ..., max_concurrency: _Optional[int] = ..., version: _Optional[str] = ..., metadata: _Optional[_Mapping[str, str]] = ...) -> None: ...

class RegisterWorkerResponse(_message.Message):
    __slots__ = ("worker_id", "lease_duration_secs", "heartbeat_interval_secs")
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    LEASE_DURATION_SECS_FIELD_NUMBER: _ClassVar[int]
    HEARTBEAT_INTERVAL_SECS_FIELD_NUMBER: _ClassVar[int]
    worker_id: str
    lease_duration_secs: int
    heartbeat_interval_secs: int
    def __init__(self, worker_id: _Optional[str] = ..., lease_duration_secs: _Optional[int] = ..., heartbeat_interval_secs: _Optional[int] = ...) -> None: ...

class HeartbeatRequest(_message.Message):
    __slots__ = ("worker_id", "current_jobs", "status", "metadata")
    class MetadataEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    WORKER_ID_FIELD_NUMBER: _ClassVar[int]
    CURRENT_JOBS_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    worker_id: str
    current_jobs: int
    status: str
    metadata: _containers.ScalarMap[str, str]
    def __init__(self, worker_id: _Optional[str] = ..., current_jobs: _Optional[int] = ..., status: _Optional[str] = ..., metadata: _Optional[_Mapping[str, str]] = ...) -> None: ...

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
    def __init__(self, worker_id: _Optional[str] = ...) -> None: ...

class DeregisterResponse(_message.Message):
    __slots__ = ("success",)
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    def __init__(self, success: bool = ...) -> None: ...
