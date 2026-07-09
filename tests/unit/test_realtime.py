"""Unit tests for realtime module."""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

from spooled.realtime.events import (
    SERVER_EVENT_MAP,
    PingCommand,
    RealtimeEvent,
    RealtimeEventType,
    SubscribeCommand,
    UnsubscribeCommand,
)
from spooled.realtime.sse import _event_from_sse_payload
from spooled.realtime.websocket import (
    ConnectionState,
    SubscriptionFilter,
    WebSocketClient,
    WebSocketConnectionOptions,
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
        """Test unknown server event type is dropped (not misrouted to error)."""
        event = RealtimeEvent.from_server_event(
            "UnknownEventType",
            {"some": "data"},
        )
        assert event is None

    def test_from_server_event_uses_server_timestamp(self) -> None:
        """Test the server-provided timestamp is preserved when present."""
        from datetime import timezone

        event = RealtimeEvent.from_server_event(
            "JobCompleted",
            {"job_id": "j_1", "timestamp": "2026-07-08T12:00:00Z"},
        )
        assert event is not None
        assert event.timestamp is not None
        assert event.timestamp == datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)

    def test_from_server_event_error_still_maps(self) -> None:
        """Test the server's own Error event still maps to the 'error' type."""
        event = RealtimeEvent.from_server_event("Error", {"message": "boom"})
        assert event is not None
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
    """Tests for SubscribeCommand.

    The backend's ``ClientCommand`` enum is internally tagged with ``cmd``,
    so the wire shape must be ``{"cmd": "subscribe", ...}`` (not ``type``).
    """

    def test_subscribe_to_queue(self) -> None:
        """Test subscribe to queue command."""
        cmd = SubscribeCommand(queue="emails")
        data = cmd.to_dict()
        assert data["cmd"] == "subscribe"
        assert "type" not in data
        assert data["queue"] == "emails"
        assert "job_id" not in data

    def test_subscribe_to_job(self) -> None:
        """Test subscribe to job command."""
        cmd = SubscribeCommand(job_id="job_123")
        data = cmd.to_dict()
        assert data["cmd"] == "subscribe"
        assert data["job_id"] == "job_123"
        assert "queue" not in data

    def test_subscribe_to_both(self) -> None:
        """Test subscribe to queue and job."""
        cmd = SubscribeCommand(queue="emails", job_id="job_123")
        data = cmd.to_dict()
        assert data["cmd"] == "subscribe"
        assert data["queue"] == "emails"
        assert data["job_id"] == "job_123"


class TestUnsubscribeCommand:
    """Tests for UnsubscribeCommand."""

    def test_unsubscribe_from_queue(self) -> None:
        """Test unsubscribe from queue command."""
        cmd = UnsubscribeCommand(queue="emails")
        data = cmd.to_dict()
        assert data["cmd"] == "unsubscribe"
        assert "type" not in data
        assert data["queue"] == "emails"

    def test_unsubscribe_from_job(self) -> None:
        """Test unsubscribe from job command."""
        cmd = UnsubscribeCommand(job_id="job_123")
        data = cmd.to_dict()
        assert data["cmd"] == "unsubscribe"
        assert data["job_id"] == "job_123"


class TestPingCommand:
    """Tests for PingCommand."""

    def test_ping_command(self) -> None:
        """Test ping command."""
        cmd = PingCommand()
        data = cmd.to_dict()
        assert data == {"cmd": "ping"}


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


class _FakeWebSocket:
    """Minimal stand-in for a connected websocket used in unit tests."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    def send(self, payload: str) -> None:
        self.sent.append(payload)

    def close(self) -> None:  # pragma: no cover - not exercised here
        pass


def _connected_ws_client() -> tuple[Any, _FakeWebSocket]:
    """Build a WebSocketClient wired to a fake socket in the CONNECTED state."""
    client = WebSocketClient(
        WebSocketConnectionOptions(ws_url="wss://api.example.test", token="tok")
    )
    fake = _FakeWebSocket()
    client._ws = fake
    client._state = ConnectionState.CONNECTED
    return client, fake


class TestWebSocketDispatch:
    """Inbound PascalCase events must dispatch to dotted typed handlers."""

    def test_inbound_pascalcase_triggers_typed_handler(self) -> None:
        """A ``{"type": "JobCompleted", ...}`` frame fires a job.completed handler."""
        client, _ = _connected_ws_client()
        received: list[RealtimeEvent] = []
        client.on("job.completed", received.append)

        client._handle_message(
            json.dumps(
                {
                    "type": "JobCompleted",
                    "data": {"job_id": "j1", "queue_name": "emails", "duration_ms": 5},
                }
            )
        )

        assert len(received) == 1
        assert received[0].type == "job.completed"
        # Payload fields are preserved verbatim (not the {type,data} envelope).
        assert received[0].data == {
            "job_id": "j1",
            "queue_name": "emails",
            "duration_ms": 5,
        }

    def test_inbound_also_reaches_catch_all_handler(self) -> None:
        """The untyped on_event handler still receives mapped events."""
        client, _ = _connected_ws_client()
        seen: list[RealtimeEvent] = []
        client.on_event(seen.append)

        client._handle_message(json.dumps({"type": "JobCreated", "data": {"job_id": "j2"}}))

        assert [e.type for e in seen] == ["job.created"]


class TestWebSocketSubscribe:
    """subscribe() sends the backend {cmd:...} shape and does not block on an ack."""

    def test_subscribe_sends_cmd_shape_and_returns_promptly(self) -> None:
        """subscribe() emits {cmd:'subscribe',queue} and returns without waiting."""
        client, fake = _connected_ws_client()

        start = time.monotonic()
        client.subscribe(SubscriptionFilter(queue="emails"))
        elapsed = time.monotonic() - start

        # Must not block on an ack the server never sends.
        assert elapsed < 1.0
        assert len(fake.sent) == 1
        assert json.loads(fake.sent[0]) == {"cmd": "subscribe", "queue": "emails"}
        # Subscription is tracked so it can be re-sent on reconnect.
        assert SubscriptionFilter(queue="emails").to_id() in client._subscriptions

    def test_unsubscribe_sends_cmd_shape(self) -> None:
        """unsubscribe() emits {cmd:'unsubscribe',...} for a tracked filter."""
        client, fake = _connected_ws_client()
        client.subscribe(SubscriptionFilter(queue="emails"))
        fake.sent.clear()

        client.unsubscribe(SubscriptionFilter(queue="emails"))

        assert json.loads(fake.sent[0]) == {"cmd": "unsubscribe", "queue": "emails"}


class TestSSEEnvelopeUnwrap:
    """SSE payloads are adjacently-tagged; handlers must receive inner fields."""

    def test_unwraps_envelope_to_inner_fields(self) -> None:
        """An enveloped SSE payload maps type and unwraps data verbatim."""
        event = _event_from_sse_payload(
            "job.completed",
            {"type": "JobCompleted", "data": {"job_id": "j1", "duration_ms": 5}},
        )
        assert event is not None
        assert event.type == "job.completed"
        assert event.data == {"job_id": "j1", "duration_ms": 5}

    def test_falls_back_to_event_name_when_not_enveloped(self) -> None:
        """A flat payload keeps working via the dotted SSE event name."""
        event = _event_from_sse_payload("job.created", {"job_id": "j2"})
        assert event is not None
        assert event.type == "job.created"
        assert event.data == {"job_id": "j2"}
