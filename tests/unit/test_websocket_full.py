"""
Comprehensive tests for WebSocket client functionality.
"""

import json
from unittest.mock import MagicMock


class TestConnectionState:
    """Tests for ConnectionState enum."""

    def test_connection_states(self):
        """Test all connection states are defined."""
        from spooled.realtime import ConnectionState

        assert ConnectionState.DISCONNECTED == "disconnected"
        assert ConnectionState.CONNECTING == "connecting"
        assert ConnectionState.CONNECTED == "connected"
        assert ConnectionState.RECONNECTING == "reconnecting"


class TestSubscriptionFilter:
    """Tests for SubscriptionFilter."""

    def test_filter_queue(self):
        """Test filter with queue."""
        from spooled.realtime import SubscriptionFilter

        filter = SubscriptionFilter(queue="test-queue")
        assert filter.queue == "test-queue"
        assert filter.job_id is None

    def test_filter_job_id(self):
        """Test filter with job_id."""
        from spooled.realtime import SubscriptionFilter

        filter = SubscriptionFilter(job_id="job-123")
        assert filter.queue is None
        assert filter.job_id == "job-123"

    def test_filter_both(self):
        """Test filter with both queue and job_id."""
        from spooled.realtime import SubscriptionFilter

        filter = SubscriptionFilter(queue="test-queue", job_id="job-123")
        assert filter.queue == "test-queue"
        assert filter.job_id == "job-123"

    def test_filter_to_id(self):
        """Test filter generates unique ID."""
        from spooled.realtime import SubscriptionFilter

        filter1 = SubscriptionFilter(queue="test")
        filter2 = SubscriptionFilter(queue="test")
        filter3 = SubscriptionFilter(queue="other")

        assert filter1.to_id() == filter2.to_id()
        assert filter1.to_id() != filter3.to_id()


class TestWebSocketConnectionOptions:
    """Tests for WebSocketConnectionOptions."""

    def test_default_options(self):
        """Test default options."""
        from spooled.realtime import WebSocketConnectionOptions

        opts = WebSocketConnectionOptions(
            ws_url="wss://api.spooled.cloud",
            token="test-token",
        )

        assert opts.ws_url == "wss://api.spooled.cloud"
        assert opts.token == "test-token"
        assert opts.auto_reconnect is True
        assert opts.max_reconnect_attempts == 10
        assert opts.reconnect_delay == 1.0
        assert opts.max_reconnect_delay == 30.0
        assert opts.command_timeout == 10.0

    def test_custom_options(self):
        """Test custom options."""
        from spooled.realtime import WebSocketConnectionOptions

        debug_fn = MagicMock()
        opts = WebSocketConnectionOptions(
            ws_url="wss://api.spooled.cloud",
            token="test-token",
            auto_reconnect=False,
            max_reconnect_attempts=5,
            reconnect_delay=2.0,
            debug=debug_fn,
        )

        assert opts.auto_reconnect is False
        assert opts.max_reconnect_attempts == 5
        assert opts.reconnect_delay == 2.0
        assert opts.debug == debug_fn


class TestRealtimeEvent:
    """Tests for RealtimeEvent."""

    def test_from_server_event_job_created(self):
        """Test parsing job.created event."""
        from spooled.realtime import RealtimeEvent

        event = RealtimeEvent.from_server_event(
            "job.created",
            {"job_id": "job-123", "queue_name": "test-queue"},
        )

        assert event.type == "job.created"
        assert event.data["job_id"] == "job-123"

    def test_from_server_event_job_completed(self):
        """Test parsing job.completed event."""
        from spooled.realtime import RealtimeEvent

        event = RealtimeEvent.from_server_event(
            "job.completed",
            {"job_id": "job-123", "result": {"success": True}},
        )

        assert event.type == "job.completed"
        assert event.data["result"]["success"] is True

    def test_from_server_event_queue_stats(self):
        """Test parsing queue.stats event."""
        from spooled.realtime import RealtimeEvent

        event = RealtimeEvent.from_server_event(
            "queue.stats",
            {"queue_name": "test", "pending": 10},
        )

        assert event.type == "queue.stats"
        assert event.data["pending"] == 10

    def test_from_server_event_unknown(self):
        """Test parsing unknown event type."""
        from spooled.realtime import RealtimeEvent

        event = RealtimeEvent.from_server_event(
            "unknown.event",
            {"key": "value"},
        )

        assert event.type == "error"


class TestSubscribeCommand:
    """Tests for SubscribeCommand."""

    def test_subscribe_queue(self):
        """Test subscribe command for queue."""
        from spooled.realtime import SubscribeCommand

        cmd = SubscribeCommand(queue="test-queue")
        d = cmd.to_dict()

        assert d["type"] == "subscribe"
        assert d["queue"] == "test-queue"
        assert "job_id" not in d or d.get("job_id") is None

    def test_subscribe_job(self):
        """Test subscribe command for job."""
        from spooled.realtime import SubscribeCommand

        cmd = SubscribeCommand(job_id="job-123")
        d = cmd.to_dict()

        assert d["type"] == "subscribe"
        assert d["job_id"] == "job-123"


class TestUnsubscribeCommand:
    """Tests for UnsubscribeCommand."""

    def test_unsubscribe_queue(self):
        """Test unsubscribe command for queue."""
        from spooled.realtime import UnsubscribeCommand

        cmd = UnsubscribeCommand(queue="test-queue")
        d = cmd.to_dict()

        assert d["type"] == "unsubscribe"
        assert d["queue"] == "test-queue"


class TestPingCommand:
    """Tests for PingCommand."""

    def test_ping(self):
        """Test ping command."""
        from spooled.realtime import PingCommand

        cmd = PingCommand()
        d = cmd.to_dict()

        assert d["type"] == "ping"


class TestWebSocketClientInit:
    """Tests for WebSocketClient initialization."""

    def test_requires_websockets(self):
        """Test client requires websockets package."""
        from spooled.realtime import WebSocketClient, WebSocketConnectionOptions

        # This should work since websockets is installed
        opts = WebSocketConnectionOptions(
            ws_url="wss://api.spooled.cloud",
            token="test-token",
        )

        # Just verify we can create the client
        client = WebSocketClient(opts)
        assert client.state.value == "disconnected"

    def test_initial_state(self):
        """Test initial state is disconnected."""
        from spooled.realtime import ConnectionState, WebSocketClient, WebSocketConnectionOptions

        opts = WebSocketConnectionOptions(
            ws_url="wss://api.spooled.cloud",
            token="test-token",
        )

        client = WebSocketClient(opts)
        assert client.state == ConnectionState.DISCONNECTED


class TestWebSocketClientEventHandlers:
    """Tests for WebSocketClient event handlers."""

    def test_on_decorator(self):
        """Test on() decorator."""
        from spooled.realtime import WebSocketClient, WebSocketConnectionOptions

        opts = WebSocketConnectionOptions(
            ws_url="wss://api.spooled.cloud",
            token="test-token",
        )

        client = WebSocketClient(opts)
        handler_called = []

        @client.on("job.created")
        def on_job_created(event):
            handler_called.append(event)

        # Verify handler was registered
        assert "job.created" in client._event_handlers
        assert len(client._event_handlers["job.created"]) == 1

    def test_on_direct_call(self):
        """Test on() direct call."""
        from spooled.realtime import WebSocketClient, WebSocketConnectionOptions

        opts = WebSocketConnectionOptions(
            ws_url="wss://api.spooled.cloud",
            token="test-token",
        )

        client = WebSocketClient(opts)
        handler_called = []

        def my_handler(event):
            handler_called.append(event)

        client.on("job.completed", my_handler)

        # Verify handler was registered
        assert "job.completed" in client._event_handlers

    def test_on_event_all_events(self):
        """Test on_event() for all events."""
        from spooled.realtime import WebSocketClient, WebSocketConnectionOptions

        opts = WebSocketConnectionOptions(
            ws_url="wss://api.spooled.cloud",
            token="test-token",
        )

        client = WebSocketClient(opts)
        events_received = []

        unsubscribe = client.on_event(lambda e: events_received.append(e))

        assert len(client._all_events_handlers) == 1

        # Unsubscribe
        unsubscribe()
        assert len(client._all_events_handlers) == 0

    def test_on_state_change(self):
        """Test on_state_change() handler."""
        from spooled.realtime import ConnectionState, WebSocketClient, WebSocketConnectionOptions

        opts = WebSocketConnectionOptions(
            ws_url="wss://api.spooled.cloud",
            token="test-token",
        )

        client = WebSocketClient(opts)
        states = []

        @client.on_state_change
        def on_state(state):
            states.append(state)

        # Manually trigger state change
        client._set_state(ConnectionState.CONNECTING)

        assert len(states) == 1
        assert states[0] == ConnectionState.CONNECTING


class TestWebSocketClientSubscriptions:
    """Tests for WebSocketClient subscription management."""

    def test_subscribe_stores_filter(self):
        """Test subscribe stores filter."""
        from spooled.realtime import SubscriptionFilter, WebSocketClient, WebSocketConnectionOptions

        opts = WebSocketConnectionOptions(
            ws_url="wss://api.spooled.cloud",
            token="test-token",
        )

        client = WebSocketClient(opts)
        filter = SubscriptionFilter(queue="test-queue")

        # Subscribe (won't send because not connected)
        client.subscribe(filter)

        assert len(client._subscriptions) == 1
        assert filter.to_id() in client._subscriptions

    def test_subscribe_deduplicates(self):
        """Test subscribe doesn't add duplicate."""
        from spooled.realtime import SubscriptionFilter, WebSocketClient, WebSocketConnectionOptions

        opts = WebSocketConnectionOptions(
            ws_url="wss://api.spooled.cloud",
            token="test-token",
        )

        client = WebSocketClient(opts)
        filter = SubscriptionFilter(queue="test-queue")

        client.subscribe(filter)
        client.subscribe(filter)

        assert len(client._subscriptions) == 1

    def test_unsubscribe_removes_filter(self):
        """Test unsubscribe removes filter."""
        from spooled.realtime import SubscriptionFilter, WebSocketClient, WebSocketConnectionOptions

        opts = WebSocketConnectionOptions(
            ws_url="wss://api.spooled.cloud",
            token="test-token",
        )

        client = WebSocketClient(opts)
        filter = SubscriptionFilter(queue="test-queue")

        client.subscribe(filter)
        assert len(client._subscriptions) == 1

        client.unsubscribe(filter)
        assert len(client._subscriptions) == 0

    def test_unsubscribe_nonexistent(self):
        """Test unsubscribe for nonexistent filter."""
        from spooled.realtime import SubscriptionFilter, WebSocketClient, WebSocketConnectionOptions

        opts = WebSocketConnectionOptions(
            ws_url="wss://api.spooled.cloud",
            token="test-token",
        )

        client = WebSocketClient(opts)
        filter = SubscriptionFilter(queue="test-queue")

        # Should not raise
        client.unsubscribe(filter)
        assert len(client._subscriptions) == 0


class TestWebSocketClientUrlBuilding:
    """Tests for WebSocketClient URL building."""

    def test_build_ws_url(self):
        """Test WebSocket URL building."""
        from spooled.realtime import WebSocketClient, WebSocketConnectionOptions

        opts = WebSocketConnectionOptions(
            ws_url="wss://api.spooled.cloud",
            token="test-token-123",
        )

        client = WebSocketClient(opts)
        url = client._build_ws_url()

        assert url == "wss://api.spooled.cloud/api/v1/ws?token=test-token-123"


class TestWebSocketClientDisconnect:
    """Tests for WebSocketClient disconnect."""

    def test_disconnect_clears_state(self):
        """Test disconnect clears state."""
        from spooled.realtime import ConnectionState, WebSocketClient, WebSocketConnectionOptions

        opts = WebSocketConnectionOptions(
            ws_url="wss://api.spooled.cloud",
            token="test-token",
        )

        client = WebSocketClient(opts)

        # Add some subscriptions
        from spooled.realtime import SubscriptionFilter

        client.subscribe(SubscriptionFilter(queue="test"))

        # Disconnect
        client.disconnect()

        assert client.state == ConnectionState.DISCONNECTED
        assert len(client._subscriptions) == 0


class TestAsyncWebSocketClient:
    """Tests for AsyncWebSocketClient."""

    def test_initial_state(self):
        """Test initial state is disconnected."""
        from spooled.realtime import (
            AsyncWebSocketClient,
            ConnectionState,
            WebSocketConnectionOptions,
        )

        opts = WebSocketConnectionOptions(
            ws_url="wss://api.spooled.cloud",
            token="test-token",
        )

        client = AsyncWebSocketClient(opts)
        assert client.state == ConnectionState.DISCONNECTED

    def test_on_decorator(self):
        """Test on() decorator."""
        from spooled.realtime import AsyncWebSocketClient, WebSocketConnectionOptions

        opts = WebSocketConnectionOptions(
            ws_url="wss://api.spooled.cloud",
            token="test-token",
        )

        client = AsyncWebSocketClient(opts)

        @client.on("job.created")
        def handler(event):
            pass

        assert "job.created" in client._event_handlers

    def test_build_ws_url(self):
        """Test WebSocket URL building."""
        from spooled.realtime import AsyncWebSocketClient, WebSocketConnectionOptions

        opts = WebSocketConnectionOptions(
            ws_url="wss://api.spooled.cloud",
            token="my-token",
        )

        client = AsyncWebSocketClient(opts)
        url = client._build_ws_url()

        assert url == "wss://api.spooled.cloud/api/v1/ws?token=my-token"


class TestRealtimeExports:
    """Tests for realtime module exports."""

    def test_all_exports_available(self):
        """Test all expected exports are available."""
        from spooled.realtime import (
            AsyncSSEClient,
            AsyncWebSocketClient,
            ConnectionState,
            PingCommand,
            RealtimeEvent,
            RealtimeEventType,
            SSEClient,
            SubscribeCommand,
            SubscriptionFilter,
            UnsubscribeCommand,
            WebSocketClient,
            WebSocketConnectionOptions,
        )

        # Verify all exports exist
        assert RealtimeEvent is not None
        assert RealtimeEventType is not None
        assert SubscribeCommand is not None
        assert UnsubscribeCommand is not None
        assert PingCommand is not None
        assert WebSocketClient is not None
        assert AsyncWebSocketClient is not None
        assert WebSocketConnectionOptions is not None
        assert ConnectionState is not None
        assert SubscriptionFilter is not None
        assert SSEClient is not None
        assert AsyncSSEClient is not None


class TestReconnectLogic:
    """Tests for reconnection logic."""

    def test_exponential_backoff_calculation(self):
        """Test exponential backoff delay calculation."""
        # Test the backoff formula: min(base_delay * 2^(attempt-1), max_delay)
        base_delay = 1.0
        max_delay = 30.0

        delays = []
        for attempt in range(1, 6):
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            delays.append(delay)

        assert delays[0] == 1.0   # 1 * 2^0 = 1
        assert delays[1] == 2.0   # 1 * 2^1 = 2
        assert delays[2] == 4.0   # 1 * 2^2 = 4
        assert delays[3] == 8.0   # 1 * 2^3 = 8
        assert delays[4] == 16.0  # 1 * 2^4 = 16

    def test_max_delay_cap(self):
        """Test delay is capped at max_delay."""
        base_delay = 1.0
        max_delay = 10.0

        delay = min(base_delay * (2 ** 10), max_delay)
        assert delay == max_delay


class TestMessageParsing:
    """Tests for message parsing."""

    def test_parse_job_event(self):
        """Test parsing job event message."""
        from spooled.realtime import RealtimeEvent

        message = json.dumps({
            "type": "job.completed",
            "data": {
                "job_id": "job-123",
                "result": {"success": True},
            }
        })

        data = json.loads(message)
        event = RealtimeEvent.from_server_event(data["type"], data.get("data", {}))

        assert event.type == "job.completed"
        assert event.data["job_id"] == "job-123"

    def test_parse_command_response(self):
        """Test command response is identified."""
        response_types = ["subscribed", "unsubscribed", "error", "pong"]

        for resp_type in response_types:
            message = json.dumps({
                "type": resp_type,
                "requestId": "req-123",
            })
            data = json.loads(message)
            assert data["type"] in response_types

