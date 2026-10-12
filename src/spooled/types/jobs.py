"""
Job-related types.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator

from spooled.types.common import to_rfc3339

# Backend `tags` is serde_json::Value: object (`{"urgent": true}`) or string array.
JsonTags = dict[str, Any] | list[Any] | None
# Backend `payload` / `result` is serde_json::Value (any JSON).
JsonValue = Any

# POST /jobs/{id}/fail rejects an empty or longer-than-2048-character `error`
# with 400, which would leave the job `processing` until its lease expired.
FAIL_ERROR_MAX_LENGTH = 2048
FAIL_ERROR_FALLBACK = "Job failed"


def coerce_fail_error(message: object) -> str:
    """Return ``message`` as a failure text the API will accept.

    Empty text becomes ``"Job failed"``; text longer than 2048 characters is cut
    to 2048. Python slices by code point, so a multi-byte character is never split.
    """
    text = message if isinstance(message, str) else str(message)
    if not text:
        return FAIL_ERROR_FALLBACK
    return text[:FAIL_ERROR_MAX_LENGTH]


# Job status enum. Response models read ``status`` as ``JobStatus | str`` so a
# status added by a newer server still parses.
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
    completion_webhook_secret: str | None = Field(default=None, max_length=255)

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
    status: JobStatus | str
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
    status: JobStatus | str
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


def _split_status_list(value: Any) -> Any:
    """Accept ``"failed,deadletter"`` as well as a list or a single status."""
    if isinstance(value, str) and "," in value:
        return [part.strip() for part in value.split(",") if part.strip()]
    return value


def _job_list_query(params: BaseModel) -> dict[str, Any]:
    """Query parameters of a job list: status list joined, times in RFC 3339."""
    query: dict[str, Any] = params.model_dump(exclude_none=True)
    status = query.get("status")
    if isinstance(status, list):
        if status:
            query["status"] = ",".join(status)
        else:
            del query["status"]
    for key in ("created_after", "created_before"):
        value = getattr(params, key, None)
        if isinstance(value, datetime):
            query[key] = to_rfc3339(value)
    return query


class ListJobsParams(BaseModel):
    """Parameters for listing jobs.

    * ``status`` - one status, a list, or a comma-separated string
      (``"failed,deadletter"``); a job matching any of them is listed.
    * ``q`` - search text, case-insensitive: a job whose id starts with it,
      or whose queue name or ``payload.job_type`` contains it.
    * ``job_type`` - exact ``payload.job_type``.
    * ``created_after`` / ``created_before`` - creation window (after is
      inclusive, before exclusive); a naive ``datetime`` is taken as UTC.

    ``jobs.list()`` returns a :class:`~spooled.types.common.Page`, whose
    ``has_more`` says whether another page follows.
    """

    queue_name: str | None = None
    status: JobStatus | list[JobStatus] | None = None
    q: str | None = None
    job_type: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    tag: str | None = Field(default=None, max_length=1024)
    """Filter by a single tag (matches Postgres `tags ? tag` semantics)."""
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    order_by: str | None = None
    order_dir: str | None = Field(default=None, pattern="^(asc|desc)$")

    model_config = {"extra": "forbid"}

    @field_validator("status", mode="before")
    @classmethod
    def split_status_list(cls, value: Any) -> Any:
        return _split_status_list(value)

    def to_query(self) -> dict[str, Any]:
        """Query parameters for ``GET /jobs``."""
        return _job_list_query(self)


class BatchJobStatus(BaseModel):
    """Status of a single job in batch status lookup.

    ``GET /jobs/status`` sends ``retry_count``, not ``attempt``, and has no
    ``max_retries``.
    """

    id: str
    status: JobStatus | str
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
    the lease this worker actually holds. The API requires it on all three
    (422 without it).
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
    """Parameters for completing a job.

    ``lease_id`` (from the claimed job) is required by the API: a request
    without it is rejected with 422.
    """

    worker_id: str
    result: JsonValue = None
    lease_id: str | None = None

    model_config = {"extra": "forbid"}


class CompleteJobResponse(BaseModel):
    """Response from completing a job."""

    success: bool


class FailJobParams(BaseModel):
    """Parameters for failing a job.

    ``lease_id`` (from the claimed job) is required by the API: a request
    without it is rejected with 422.
    """

    worker_id: str
    error: str = Field(..., min_length=1, max_length=FAIL_ERROR_MAX_LENGTH)
    lease_id: str | None = None

    model_config = {"extra": "forbid"}


class FailJobResponse(BaseModel):
    """Response from failing a job."""

    success: bool
    error: str | None = None


class JobHeartbeatParams(BaseModel):
    """Parameters for job heartbeat.

    ``lease_id`` (from the claimed job) is required by the API: a request
    without it is rejected with 422.
    """

    worker_id: str
    lease_duration_secs: int = Field(default=30, ge=5, le=3600)
    lease_id: str | None = None

    model_config = {"extra": "forbid"}


class ListDlqParams(BaseModel):
    """Parameters for listing DLQ jobs.

    The search filters (``q``, ``job_type``, ``created_after``,
    ``created_before``, ``tag``) work as on :class:`ListJobsParams`; there is
    no ``status`` (always ``deadletter``).
    """

    queue_name: str | None = None
    q: str | None = None
    job_type: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    tag: str | None = Field(default=None, max_length=1024)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    order_by: str | None = None
    order_dir: str | None = Field(default=None, pattern="^(asc|desc)$")

    model_config = {"extra": "forbid"}

    def to_query(self) -> dict[str, Any]:
        """Query parameters for ``GET /jobs/dlq``."""
        return _job_list_query(self)


class JobHistoryEvent(BaseModel):
    """One recorded lifecycle event of a job (``GET /jobs/{id}/history``).

    ``event_type`` is a free-form string (for example ``created``,
    ``claimed``, ``completed``, ``failed``, ``retried``); new kinds can appear
    without an SDK update. ``details`` is any JSON (at most 64 KB).
    """

    id: str
    job_id: str
    event_type: str
    worker_id: str | None = None
    details: JsonValue = None
    created_at: datetime


class JobHistoryParams(BaseModel):
    """Paging of ``GET /jobs/{id}/history``.

    ``order_dir`` is ``asc`` (server default, oldest first) or ``desc``;
    ``limit`` is 1-500 (server default 100).
    """

    order_dir: Literal["asc", "desc"] | None = None
    limit: int | None = Field(default=None, ge=1, le=500)
    offset: int | None = Field(default=None, ge=0)

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

    ``confirm`` has no default on purpose: with no filter the purge deletes up
    to 10 000 dead-lettered jobs of the whole organization, so ``purge({})`` must
    fail validation instead of being confirmed on the caller's behalf.
    """

    queue_name: str | None = None
    older_than: datetime | None = None
    older_than_days: int | None = Field(default=None, ge=1)
    limit: int | None = Field(default=None, ge=1, le=10000)
    confirm: bool

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
