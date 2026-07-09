"""
Real-time event types for Spooled SDK.
"""

from __future__ import annotations

from datetime import datetime, timezone
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

# Server event type mapping - maps both PascalCase and dot-notation
SERVER_EVENT_MAP: dict[str, RealtimeEventType] = {
    # PascalCase from server
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
    # Dot-notation (sometimes used)
    "job.status": "job.status",
    "job.created": "job.created",
    "job.completed": "job.completed",
    "job.failed": "job.failed",
    "queue.stats": "queue.stats",
    "worker.heartbeat": "worker.heartbeat",
    "worker.registered": "worker.registered",
    "worker.deregistered": "worker.deregistered",
    "system.health": "system.health",
    "ping": "ping",
    "error": "error",
}


class RealtimeEvent(BaseModel):
    """Real-time event from WebSocket or SSE."""

    type: RealtimeEventType
    data: dict[str, Any]
    timestamp: datetime | None = None

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        """Best-effort parse of a server-provided timestamp value."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(value, tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                return None
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            # Accept RFC 3339 with a trailing 'Z'.
            normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
            try:
                return datetime.fromisoformat(normalized)
            except ValueError:
                return None
        return None

    @classmethod
    def from_server_event(
        cls,
        server_type: str,
        data: dict[str, Any],
        *,
        timestamp: Any = None,
    ) -> RealtimeEvent | None:
        """Create event from server event format.

        Returns ``None`` for unrecognized server event types so that new or
        unknown event kinds are dropped rather than being misrouted to
        consumers as spurious ``error`` events. The ``error`` type is reserved
        for the server's actual ``Error``/``error`` events.

        The server-provided timestamp (passed explicitly or carried in the
        event data) is preserved when present, falling back to the local
        receive time only when the server does not supply one.
        """
        event_type = SERVER_EVENT_MAP.get(server_type)
        if event_type is None:
            return None

        parsed_ts = cls._parse_timestamp(timestamp)
        if parsed_ts is None and isinstance(data, dict):
            parsed_ts = cls._parse_timestamp(data.get("timestamp"))

        return cls(
            type=event_type,
            data=data,
            timestamp=parsed_ts or datetime.now(timezone.utc),
        )


class SubscribeCommand(BaseModel):
    """Subscribe command for WebSocket.

    The backend's ``ClientCommand`` enum is internally tagged with ``cmd``
    (``#[serde(tag = "cmd")]``), so the wire shape is
    ``{"cmd": "subscribe", "queue": ..., "job_id": ...}``. Emitting ``type``
    here fails to deserialize server-side and the command is silently dropped.
    """

    queue: str | None = None
    job_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to the backend command shape ``{"cmd": "subscribe", ...}``."""
        result: dict[str, Any] = {"cmd": "subscribe"}
        if self.queue:
            result["queue"] = self.queue
        if self.job_id:
            result["job_id"] = self.job_id
        return result


class UnsubscribeCommand(BaseModel):
    """Unsubscribe command for WebSocket (backend shape ``{"cmd": ...}``)."""

    queue: str | None = None
    job_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to the backend command shape ``{"cmd": "unsubscribe", ...}``."""
        result: dict[str, Any] = {"cmd": "unsubscribe"}
        if self.queue:
            result["queue"] = self.queue
        if self.job_id:
            result["job_id"] = self.job_id
        return result


class PingCommand(BaseModel):
    """Ping command for WebSocket (backend shape ``{"cmd": "ping"}``)."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to the backend command shape ``{"cmd": "ping"}``."""
        return {"cmd": "ping"}
