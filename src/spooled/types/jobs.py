"""
Job-related types.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field

# Backend `tags` is serde_json::Value: object (`{"urgent": true}`) or string array.
JsonTags = dict[str, Any] | list[Any] | None
# Backend `payload` / `result` is serde_json::Value (any JSON).
JsonValue = Any

# Job status enum
JobStatus = Literal[
    "pending",
    "scheduled",
    "processing",
    "completed",
    "failed",
    "deadletter",
    "cancelled",
]


class CreateJobParams(BaseModel):
    """Parameters for creating a job."""

    queue_name: str = Field(..., min_length=1, max_length=100)
    payload: JsonValue
    priority: int = Field(default=0, ge=-100, le=100)
    max_retries: int = Field(default=3, ge=0, le=100)
    timeout_seconds: int = Field(default=300, ge=1, le=86400)
    scheduled_at: datetime | None = None
    expires_at: datetime | None = None
    idempotency_key: str | None = Field(default=None, max_length=255)
    tags: JsonTags = None
    parent_job_id: str | None = None
    completion_webhook: str | None = None

    model_config = {"extra": "forbid"}


class CreateJobResponse(BaseModel):
    """Response from creating a job."""

    id: str
    created: bool  # False if idempotent hit


class Job(BaseModel):
    """Full job model."""

    id: str
    organization_id: str
    queue_name: str
    status: JobStatus
    payload: JsonValue
    result: JsonValue = None
    retry_count: int
    max_retries: int
    last_error: str | None = None
    created_at: datetime
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime | None = None
    priority: int
    tags: JsonTags = None
    timeout_seconds: int
    parent_job_id: str | None = None
    completion_webhook: str | None = None
    assigned_worker_id: str | None = None
    lease_id: str | None = None
    lease_expires_at: datetime | None = None
    idempotency_key: str | None = None
    updated_at: datetime | None = None
    workflow_id: str | None = None
    dependency_mode: str | None = None
    dependencies_met: bool | None = None


class JobSummary(BaseModel):
    """Summary view of a job."""

    id: str
    queue_name: str
    status: JobStatus
    priority: int
    retry_count: int = Field(
        default=0,
        validation_alias=AliasChoices("retry_count", "attempt"),
    )
    max_retries: int | None = None
    # GET /jobs summaries send payload.job_type as job_type (empty if absent).
    job_type: str = ""
    # List/DLQ summaries send last_error (null when none).
    last_error: str | None = None
    created_at: datetime
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class JobStats(BaseModel):
    """Job statistics."""

    pending: int
    scheduled: int
    processing: int
    completed: int
    failed: int
    deadletter: int
    cancelled: int
    total: int


class ListJobsParams(BaseModel):
    """Parameters for listing jobs."""

    queue_name: str | None = None
    status: JobStatus | None = None
    tag: str | None = Field(default=None, max_length=64)
    """Filter by a single tag (matches Postgres `tags ? tag` semantics)."""
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    order_by: str | None = None
    order_dir: str | None = Field(default=None, pattern="^(asc|desc)$")

    model_config = {"extra": "forbid"}


class BatchJobStatus(BaseModel):
    """Status of a single job in batch status lookup.

    ``GET /jobs/status`` sends ``retry_count``, not ``attempt``, and has no
    ``max_retries``.
    """

    id: str
    status: JobStatus
    queue_name: str
    retry_count: int
    created_at: datetime
    completed_at: datetime | None = None


class BoostPriorityResponse(BaseModel):
    """Response from boosting job priority."""

    job_id: str
    old_priority: int
    new_priority: int


class BulkJobItem(BaseModel):
    """Single job in bulk enqueue request."""

    payload: JsonValue
    priority: int | None = None
    idempotency_key: str | None = None
    scheduled_at: datetime | None = None

    model_config = {"extra": "forbid"}


class BulkJobResult(BaseModel):
    """Result of a single job in bulk enqueue."""

    index: int
    job_id: str | None = None
    created: bool | None = None
    error: str | None = None


class BulkEnqueueParams(BaseModel):
    """Parameters for bulk enqueueing jobs."""

    queue_name: str = Field(..., min_length=1, max_length=100)
    jobs: list[BulkJobItem] = Field(..., max_length=100)
    default_priority: int | None = Field(default=None, ge=-100, le=100)
    default_max_retries: int | None = Field(default=None, ge=0, le=100)
    default_timeout_seconds: int | None = Field(default=None, ge=1, le=86400)

    model_config = {"extra": "forbid"}


class BulkEnqueueResponse(BaseModel):
    """Response from bulk enqueueing jobs."""

    succeeded: list[BulkJobResult]
    failed: list[BulkJobResult]
    total: int
    success_count: int
    failure_count: int


class ClaimJobsParams(BaseModel):
    """Parameters for claiming jobs."""

    queue_name: str = Field(..., min_length=1, max_length=100)
    worker_id: str
    limit: int = Field(default=1, ge=1, le=100)
    lease_duration_secs: int = Field(default=30, ge=5, le=3600)

    model_config = {"extra": "forbid"}


class ClaimedJob(BaseModel):
    """A claimed job ready for processing.

    ``lease_id`` is the lease fencing token returned by the backend on claim;
    echo it back on complete/fail/heartbeat so the operation applies only to
    the lease this worker actually holds (``None`` = legacy server).
    """

    id: str
    queue_name: str
    payload: JsonValue
    retry_count: int
    max_retries: int
    timeout_seconds: int
    lease_expires_at: datetime | None = None
    lease_id: str | None = None


class ClaimJobsResponse(BaseModel):
    """Response from claiming jobs."""

    jobs: list[ClaimedJob]


class CompleteJobParams(BaseModel):
    """Parameters for completing a job."""

    worker_id: str
    result: JsonValue = None
    lease_id: str | None = None

    model_config = {"extra": "forbid"}


class CompleteJobResponse(BaseModel):
    """Response from completing a job."""

    success: bool


class FailJobParams(BaseModel):
    """Parameters for failing a job."""

    worker_id: str
    error: str = Field(..., min_length=1, max_length=2048)
    lease_id: str | None = None

    model_config = {"extra": "forbid"}


class FailJobResponse(BaseModel):
    """Response from failing a job."""

    success: bool
    error: str | None = None


class JobHeartbeatParams(BaseModel):
    """Parameters for job heartbeat."""

    worker_id: str
    lease_duration_secs: int = Field(default=30, ge=5, le=3600)
    lease_id: str | None = None

    model_config = {"extra": "forbid"}


class ListDlqParams(BaseModel):
    """Parameters for listing DLQ jobs."""

    queue_name: str | None = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    model_config = {"extra": "forbid"}


class RetryDlqParams(BaseModel):
    """Parameters for retrying DLQ jobs."""

    queue_name: str | None = None
    job_ids: list[str] | None = None
    limit: int | None = Field(default=None, ge=1, le=100)

    model_config = {"extra": "forbid"}


class RetryDlqResponse(BaseModel):
    """Response from retrying DLQ jobs."""

    retried_count: int
    retried_jobs: list[str] = []
    job_ids: list[str] | None = None  # Alias for backwards compatibility


class PurgeDlqParams(BaseModel):
    """Parameters for purging DLQ jobs.

    ``POST /jobs/dlq/purge`` is ``{ queue_name?, older_than?, limit?, confirm }``.
    ``confirm`` must be true or the API returns 400. There is no ``job_ids``
    filter (retry has that). ``older_than_days`` is converted to ``older_than``.
    """

    queue_name: str | None = None
    older_than: datetime | None = None
    older_than_days: int | None = Field(default=None, ge=1)
    limit: int | None = Field(default=None, ge=1, le=10000)
    confirm: bool = True

    model_config = {"extra": "forbid"}

    def to_payload(self) -> dict[str, Any]:
        """Build the API body: ``confirm`` plus ``older_than``, never ``older_than_days``."""
        if not self.confirm:
            raise ValueError("Must set confirm=True to purge dead-letter queue")
        payload: dict[str, Any] = {"confirm": True}
        if self.queue_name is not None:
            payload["queue_name"] = self.queue_name
        if self.limit is not None:
            payload["limit"] = self.limit
        older_than = self.older_than
        if older_than is None and self.older_than_days is not None:
            older_than = datetime.now(timezone.utc) - timedelta(days=self.older_than_days)
        if older_than is not None:
            if older_than.tzinfo is None:
                older_than = older_than.replace(tzinfo=timezone.utc)
            payload["older_than"] = older_than.isoformat()
        return payload


class PurgeDlqResponse(BaseModel):
    """Response from purging DLQ jobs."""

    purged_count: int
