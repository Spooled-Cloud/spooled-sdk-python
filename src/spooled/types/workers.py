"""
Worker-related types.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

WorkerStatus = Literal["healthy", "degraded", "offline", "draining"]


class Worker(BaseModel):
    """Full worker model."""

    id: str
    organization_id: str | None = None
    queue_name: str
    queue_names: list[str] | None = None
    hostname: str
    worker_type: str | None = None
    # Support both field names (max_concurrency from list, max_concurrent_jobs from get)
    max_concurrency: int | None = Field(default=None, alias="max_concurrent_jobs")
    current_jobs: int | None = Field(default=None, alias="current_job_count")
    status: WorkerStatus
    last_heartbeat: datetime
    metadata: dict[str, Any] | None = None
    version: str | None = None
    registered_at: datetime | None = Field(default=None, alias="created_at")
    updated_at: datetime | None = None

    model_config = {"populate_by_name": True}


class WorkerSummary(BaseModel):
    """Summary view of a worker."""

    id: str
    queue_name: str
    hostname: str
    status: WorkerStatus
    current_jobs: int
    max_concurrency: int
    last_heartbeat: datetime


class RegisterWorkerParams(BaseModel):
    """Parameters for registering a worker."""

    queue_name: str = Field(..., min_length=1, max_length=100)
    hostname: str
    worker_type: str | None = None
    max_concurrency: int = Field(default=5, ge=1, le=100)
    metadata: dict[str, Any] | None = None
    version: str | None = None

    model_config = {"extra": "forbid"}


class RegisterWorkerResponse(BaseModel):
    """Response from registering a worker."""

    id: str
    queue_name: str
    lease_duration_secs: int
    heartbeat_interval_secs: int


class WorkerHeartbeatParams(BaseModel):
    """Parameters for worker heartbeat."""

    current_jobs: int = Field(ge=0)
    status: WorkerStatus | None = None
    metadata: dict[str, Any] | None = None

    model_config = {"extra": "forbid"}
