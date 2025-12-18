"""
Job-related types.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

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
    payload: dict[str, Any]
    priority: int = Field(default=0, ge=-100, le=100)
    max_retries: int = Field(default=3, ge=0, le=100)
    timeout_seconds: int = Field(default=300, ge=1, le=86400)
    scheduled_at: datetime | None = None
    expires_at: datetime | None = None
    idempotency_key: str | None = Field(default=None, max_length=255)
    tags: dict[str, str] | None = None
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
    payload: dict[str, Any]
    result: dict[str, Any] | None = None
    retry_count: int
    max_retries: int
    last_error: str | None = None
    created_at: datetime
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime | None = None
    priority: int
    tags: dict[str, str] | None = None
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
    retry_count: int | None = None  # Not always returned by API
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
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    order_by: str | None = None
    order_dir: str | None = Field(default=None, pattern="^(asc|desc)$")

    model_config = {"extra": "forbid"}


class BatchJobStatus(BaseModel):
    """Status of a single job in batch status lookup."""

    id: str
    status: JobStatus
    queue_name: str


class BoostPriorityResponse(BaseModel):
    """Response from boosting job priority."""

    job_id: str
    old_priority: int
    new_priority: int


class BulkJobItem(BaseModel):
    """Single job in bulk enqueue request."""

    payload: dict[str, Any]
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
    """A claimed job ready for processing."""

    id: str
    queue_name: str
    payload: dict[str, Any]
    retry_count: int
    max_retries: int
    timeout_seconds: int
    lease_expires_at: datetime | None = None


class ClaimJobsResponse(BaseModel):
    """Response from claiming jobs."""

    jobs: list[ClaimedJob]


class CompleteJobParams(BaseModel):
    """Parameters for completing a job."""

    worker_id: str
    result: dict[str, Any] | None = None

    model_config = {"extra": "forbid"}


class CompleteJobResponse(BaseModel):
    """Response from completing a job."""

    success: bool


class FailJobParams(BaseModel):
    """Parameters for failing a job."""

    worker_id: str
    error: str = Field(..., min_length=1, max_length=2048)

    model_config = {"extra": "forbid"}


class FailJobResponse(BaseModel):
    """Response from failing a job."""

    success: bool
    error: str | None = None


class JobHeartbeatParams(BaseModel):
    """Parameters for job heartbeat."""

    worker_id: str
    lease_duration_secs: int = Field(default=30, ge=5, le=3600)

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
    """Parameters for purging DLQ jobs."""

    queue_name: str | None = None
    job_ids: list[str] | None = None
    older_than_days: int | None = Field(default=None, ge=1)

    model_config = {"extra": "forbid"}


class PurgeDlqResponse(BaseModel):
    """Response from purging DLQ jobs."""

    purged_count: int
