"""
Worker types for Spooled SDK.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import Event
from typing import Any, Literal

from pydantic import BaseModel, Field

# Worker states
WorkerState = Literal["idle", "starting", "running", "stopping", "stopped", "error"]

# Worker events
WorkerEvent = Literal[
    "started",
    "stopped",
    "error",
    "job:claimed",
    "job:started",
    "job:completed",
    "job:failed",
]


@dataclass
class JobContext:
    """Context provided to job handlers."""

    job_id: str
    queue_name: str
    payload: dict[str, Any]
    retry_count: int
    max_retries: int
    signal: Event  # For abort signaling

    def progress(self, percent: int, message: str | None = None) -> None:
        """Report job progress (0-100)."""
        # Progress tracking could be implemented via heartbeat metadata
        pass

    def log(
        self,
        level: Literal["debug", "info", "warn", "error"],
        message: str,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Log a message associated with this job."""
        # Logging implementation - could be enhanced
        import logging

        logger = logging.getLogger(f"spooled.worker.job.{self.job_id}")
        log_fn = getattr(logger, level if level != "warn" else "warning")
        if meta:
            log_fn(f"{message} {meta}")
        else:
            log_fn(message)


@dataclass
class AsyncJobContext:
    """Context provided to async job handlers."""

    job_id: str
    queue_name: str
    payload: dict[str, Any]
    retry_count: int
    max_retries: int
    signal: Any  # asyncio.Event for abort signaling

    async def progress(self, percent: int, message: str | None = None) -> None:
        """Report job progress (0-100)."""
        pass

    async def log(
        self,
        level: Literal["debug", "info", "warn", "error"],
        message: str,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Log a message associated with this job."""
        import logging

        logger = logging.getLogger(f"spooled.worker.job.{self.job_id}")
        log_fn = getattr(logger, level if level != "warn" else "warning")
        if meta:
            log_fn(f"{message} {meta}")
        else:
            log_fn(message)


# Job handler type
JobHandler = Callable[[JobContext], dict[str, Any] | None]
AsyncJobHandler = Callable[[AsyncJobContext], Any]


# Event data classes
@dataclass
class StartedEventData:
    """Data for worker started event."""

    worker_id: str
    queue_name: str


@dataclass
class StoppedEventData:
    """Data for worker stopped event."""

    worker_id: str
    reason: str


@dataclass
class ErrorEventData:
    """Data for worker error event."""

    error: Exception


@dataclass
class JobClaimedEventData:
    """Data for job claimed event."""

    job_id: str
    queue_name: str


@dataclass
class JobStartedEventData:
    """Data for job started event."""

    job_id: str
    queue_name: str


@dataclass
class JobCompletedEventData:
    """Data for job completed event."""

    job_id: str
    queue_name: str
    result: dict[str, Any] | None


@dataclass
class JobFailedEventData:
    """Data for job failed event."""

    job_id: str
    queue_name: str
    error: str
    will_retry: bool


class SpooledWorkerOptions(BaseModel):
    """Options for SpooledWorker."""

    queue_name: str = Field(..., min_length=1, max_length=100)
    concurrency: int = Field(default=5, ge=1, le=100)
    poll_interval: float = Field(default=1.0, gt=0)  # seconds
    lease_duration: int = Field(default=30, ge=5, le=3600)  # seconds
    heartbeat_fraction: float = Field(default=0.5, gt=0, le=1)
    shutdown_timeout: float = Field(default=30.0, gt=0)  # seconds
    hostname: str | None = None
    worker_type: str = Field(default="python")
    version: str = Field(default="1.0.0")
    metadata: dict[str, Any] = Field(default_factory=dict)
    auto_start: bool = Field(default=False)

    model_config = {"extra": "forbid"}
