"""
Queue-related types.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class QueueConfig(BaseModel):
    """Full queue configuration."""

    id: str
    organization_id: str
    queue_name: str
    max_retries: int
    default_timeout: int
    rate_limit: int | None = None
    enabled: bool
    settings: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class QueueConfigSummary(BaseModel):
    """Summary view of queue configuration."""

    queue_name: str
    max_retries: int
    default_timeout: int
    rate_limit: int | None = None
    enabled: bool


class QueueStats(BaseModel):
    """Queue statistics."""

    queue_name: str
    pending_jobs: int
    processing_jobs: int
    completed_jobs_24h: int
    failed_jobs_24h: int
    avg_processing_time_ms: float | None = None
    max_job_age_seconds: int | None = None
    active_workers: int


class UpdateQueueConfigParams(BaseModel):
    """Parameters for updating queue configuration."""

    max_retries: int | None = Field(default=None, ge=0, le=100)
    default_timeout: int | None = Field(default=None, ge=1, le=86400)
    rate_limit: int | None = Field(default=None, ge=1)
    enabled: bool | None = None
    settings: dict[str, Any] | None = None

    model_config = {"extra": "forbid"}


class PauseQueueResponse(BaseModel):
    """Response from pausing a queue."""

    queue_name: str
    paused: bool
    paused_at: datetime
    reason: str | None = None


class ResumeQueueResponse(BaseModel):
    """Response from resuming a queue."""

    queue_name: str
    resumed: bool
    paused_duration_secs: int
