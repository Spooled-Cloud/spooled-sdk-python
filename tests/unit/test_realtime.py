"""Unit tests for realtime module."""

from __future__ import annotations

from datetime import datetime

import pytest

from spooled.realtime.events import (
    PingCommand,
    RealtimeEvent,
    RealtimeEventType,
    SERVER_EVENT_MAP,
    SubscribeCommand,
    UnsubscribeCommand,
)


class TestRealtimeEvent:
    """Tests for RealtimeEvent."""

    def test_create_event(self) -> None:
        """Test creating a realtime event."""
        event = RealtimeEvent(
            type="job.created",
            data={"job_id": "job_123"},
        )
        assert event.type == "job.created"
        assert event.data == {"job_id": "job_123"}

    def test_event_with_timestamp(self) -> None:
        """Test event with timestamp."""
        now = datetime.now()
        event = RealtimeEvent(
            type="job.completed",
            data={},
            timestamp=now,
        )
        assert event.timestamp == now

    def test_from_server_event_job_status(self) -> None:
        """Test creating event from server event."""
        event = RealtimeEvent.from_server_event(
            "JobStatusChange",
            {"job_id": "j_1", "status": "completed"},
        )
        assert event.type == "job.status"
        assert event.data["job_id"] == "j_1"

    def test_from_server_event_unknown(self) -> None:
        """Test unknown server event type defaults to error."""
        event = RealtimeEvent.from_server_event(
            "UnknownEventType",
            {"some": "data"},
        )
        assert event.type == "error"


class TestServerEventMap:
    """Tests for server event mapping."""

    def test_all_event_types_mapped(self) -> None:
        """Test all known server events have mappings."""
        expected_events = [
            "JobStatusChange",
            "JobCreated",
            "JobCompleted",
            "JobFailed",
            "QueueStats",
            "WorkerHeartbeat",
            "WorkerRegistered",
            "WorkerDeregistered",
            "SystemHealth",
            "Ping",
            "Error",
        ]
        for event in expected_events:
            assert event in SERVER_EVENT_MAP


class TestSubscribeCommand:
    """Tests for SubscribeCommand."""

    def test_subscribe_to_queue(self) -> None:
        """Test subscribe to queue command."""
        cmd = SubscribeCommand(queue="emails")
        data = cmd.to_dict()
        assert data["cmd"] == "Subscribe"
        assert data["queue"] == "emails"
        assert "job_id" not in data

    def test_subscribe_to_job(self) -> None:
        """Test subscribe to job command."""
        cmd = SubscribeCommand(job_id="job_123")
        data = cmd.to_dict()
        assert data["cmd"] == "Subscribe"
        assert data["job_id"] == "job_123"
        assert "queue" not in data

    def test_subscribe_to_both(self) -> None:
        """Test subscribe to queue and job."""
        cmd = SubscribeCommand(queue="emails", job_id="job_123")
        data = cmd.to_dict()
        assert data["queue"] == "emails"
        assert data["job_id"] == "job_123"


class TestUnsubscribeCommand:
    """Tests for UnsubscribeCommand."""

    def test_unsubscribe_from_queue(self) -> None:
        """Test unsubscribe from queue command."""
        cmd = UnsubscribeCommand(queue="emails")
        data = cmd.to_dict()
        assert data["cmd"] == "Unsubscribe"
        assert data["queue"] == "emails"

    def test_unsubscribe_from_job(self) -> None:
        """Test unsubscribe from job command."""
        cmd = UnsubscribeCommand(job_id="job_123")
        data = cmd.to_dict()
        assert data["cmd"] == "Unsubscribe"
        assert data["job_id"] == "job_123"


class TestPingCommand:
    """Tests for PingCommand."""

    def test_ping_command(self) -> None:
        """Test ping command."""
        cmd = PingCommand()
        data = cmd.to_dict()
        assert data == {"cmd": "Ping"}


class TestRealtimeEventTypes:
    """Tests for RealtimeEventType literal."""

    def test_all_event_types(self) -> None:
        """Test all event types are valid."""
        valid_types: list[RealtimeEventType] = [
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
        # All should be valid RealtimeEventType literals
        for t in valid_types:
            event = RealtimeEvent(type=t, data={})
            assert event.type == t


