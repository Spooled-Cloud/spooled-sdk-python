"""
Schedule-related types.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Schedule(BaseModel):
    """Full schedule model."""

    id: str
    organization_id: str
    name: str
    description: str | None = None
    cron_expression: str
    timezone: str
    queue_name: str
    payload_template: dict[str, Any]
    priority: int
    max_retries: int
    timeout_seconds: int
    is_active: bool
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    run_count: int
    tags: dict[str, str] | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class ScheduleRun(BaseModel):
    """Schedule execution history entry."""

    id: str
    schedule_id: str
    job_id: str | None = None
    status: str  # 'pending' | 'running' | 'completed' | 'failed'
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class CreateScheduleParams(BaseModel):
    """Parameters for creating a schedule."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    cron_expression: str
    timezone: str = Field(default="UTC")
    queue_name: str = Field(..., min_length=1, max_length=100)
    payload_template: dict[str, Any]
    priority: int = Field(default=0, ge=-100, le=100)
    max_retries: int = Field(default=3, ge=0, le=100)
    timeout_seconds: int = Field(default=300, ge=1, le=86400)
    tags: dict[str, str] | None = None
    metadata: dict[str, Any] | None = None

    model_config = {"extra": "forbid"}


class CreateScheduleResponse(BaseModel):
    """Response from creating a schedule."""

    id: str
    name: str
    cron_expression: str
    next_run_at: datetime | None = None


class UpdateScheduleParams(BaseModel):
    """Parameters for updating a schedule."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    cron_expression: str | None = None
    timezone: str | None = None
    queue_name: str | None = Field(default=None, min_length=1, max_length=100)
    payload_template: dict[str, Any] | None = None
    priority: int | None = Field(default=None, ge=-100, le=100)
    max_retries: int | None = Field(default=None, ge=0, le=100)
    timeout_seconds: int | None = Field(default=None, ge=1, le=86400)
    tags: dict[str, str] | None = None
    metadata: dict[str, Any] | None = None

    model_config = {"extra": "forbid"}


class ListSchedulesParams(BaseModel):
    """Parameters for listing schedules."""

    queue_name: str | None = None
    is_active: bool | None = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    model_config = {"extra": "forbid"}


class TriggerScheduleResponse(BaseModel):
    """Response from manually triggering a schedule."""

    job_id: str
    triggered_at: datetime
