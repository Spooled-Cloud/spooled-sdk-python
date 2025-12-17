"""
Real-time event types for Spooled SDK.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

# Event types from the server
RealtimeEventType = Literal[
    "job.status",
    "job.created",
    "job.completed",
    "job.failed",
    "queue.stats",
    "worker.heartbeat",
    "worker.registered",
    "worker.deregistered",
    "system.health",
    "ping",
    "error",
]

# Server event type mapping
SERVER_EVENT_MAP: dict[str, RealtimeEventType] = {
    "JobStatusChange": "job.status",
    "JobCreated": "job.created",
    "JobCompleted": "job.completed",
    "JobFailed": "job.failed",
    "QueueStats": "queue.stats",
    "WorkerHeartbeat": "worker.heartbeat",
    "WorkerRegistered": "worker.registered",
    "WorkerDeregistered": "worker.deregistered",
    "SystemHealth": "system.health",
    "Ping": "ping",
    "Error": "error",
}


class RealtimeEvent(BaseModel):
    """Real-time event from WebSocket or SSE."""

    type: RealtimeEventType
    data: dict[str, Any]
    timestamp: datetime | None = None

    @classmethod
    def from_server_event(cls, server_type: str, data: dict[str, Any]) -> RealtimeEvent:
        """Create event from server event format."""
        event_type = SERVER_EVENT_MAP.get(server_type, "error")
        return cls(
            type=event_type,
            data=data,
            timestamp=datetime.now(),
        )


class SubscribeCommand(BaseModel):
    """Subscribe command for WebSocket."""

    cmd: Literal["Subscribe"] = "Subscribe"
    queue: str | None = None
    job_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for sending."""
        result: dict[str, Any] = {"cmd": self.cmd}
        if self.queue:
            result["queue"] = self.queue
        if self.job_id:
            result["job_id"] = self.job_id
        return result


class UnsubscribeCommand(BaseModel):
    """Unsubscribe command for WebSocket."""

    cmd: Literal["Unsubscribe"] = "Unsubscribe"
    queue: str | None = None
    job_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for sending."""
        result: dict[str, Any] = {"cmd": self.cmd}
        if self.queue:
            result["queue"] = self.queue
        if self.job_id:
            result["job_id"] = self.job_id
        return result


class PingCommand(BaseModel):
    """Ping command for WebSocket."""

    cmd: Literal["Ping"] = "Ping"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for sending."""
        return {"cmd": self.cmd}


