"""
Dashboard-related types.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SystemInfo(BaseModel):
    """System information."""

    version: str
    uptime_seconds: int
    started_at: datetime
    database_status: str
    cache_status: str
    environment: str


class JobSummaryStats(BaseModel):
    """Job statistics summary."""

    total: int
    pending: int
    processing: int
    completed_24h: int
    failed_24h: int
    deadletter: int
    avg_wait_time_ms: float | None = None
    avg_processing_time_ms: float | None = None


class QueueSummaryInfo(BaseModel):
    """Queue summary for dashboard."""

    name: str
    pending: int
    processing: int
    paused: bool


class WorkerSummaryInfo(BaseModel):
    """Worker summary for dashboard."""

    total: int
    healthy: int
    unhealthy: int


class RecentActivity(BaseModel):
    """Recent activity metrics."""

    jobs_created_1h: int
    jobs_completed_1h: int
    jobs_failed_1h: int


class DashboardData(BaseModel):
    """Full dashboard data."""

    system: SystemInfo
    jobs: JobSummaryStats
    queues: list[QueueSummaryInfo]
    workers: WorkerSummaryInfo
    recent_activity: RecentActivity
