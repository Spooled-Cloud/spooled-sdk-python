"""
Unit tests for new client features.

Tests for:
- client.grpc property (lazy initialization)
- client.realtime() factory method
- client.with_options() method
- SpooledRealtime unified class
- SSE client event handlers
"""

from __future__ import annotations

from typing import Any

import pytest

from spooled import AsyncSpooledClient, SpooledClient

# ─────────────────────────────────────────────────────────────────────────────
# Test with_options()
# ─────────────────────────────────────────────────────────────────────────────


class TestWithOptions:
    """Tests for client.with_options() method."""

    def test_with_options_creates_new_client(self) -> None:
        """Test that with_options creates a new client instance."""
        client = SpooledClient(api_key="sk_live_test")
        new_client = client.with_options(debug=True)

        assert new_client is not client
        assert new_client.get_config().debug_fn is not None
        client.close()
        new_client.close()

    def test_with_options_preserves_existing_config(self) -> None:
        """Test that with_options preserves existing configuration."""
        client = SpooledClient(
            api_key="sk_live_test",
            base_url="https://custom.api.com",
        )
        new_client = client.with_options(debug=True)

        assert new_client.get_config().api_key == "sk_live_test"
        assert new_client.get_config().base_url == "https://custom.api.com"
        assert new_client.get_config().debug_fn is not None
        client.close()
        new_client.close()

    def test_with_options_overrides_api_key(self) -> None:
        """Test that with_options can override API key."""
        client = SpooledClient(api_key="sk_live_original")
        new_client = client.with_options(api_key="sk_live_new")

        assert new_client.get_config().api_key == "sk_live_new"
        client.close()
        new_client.close()

    def test_with_options_overrides_base_url(self) -> None:
        """Test that with_options can override base URL."""
        client = SpooledClient(api_key="sk_live_test")
        new_client = client.with_options(base_url="https://staging.api.com")

        assert new_client.get_config().base_url == "https://staging.api.com"
        client.close()
        new_client.close()

    def test_with_options_overrides_timeout(self) -> None:
        """Test that with_options can override timeout."""
        client = SpooledClient(api_key="sk_live_test", timeout=30.0)
        new_client = client.with_options(timeout=60.0)

        assert new_client.get_config().timeout == 60.0
        client.close()
        new_client.close()

    def test_async_client_with_options(self) -> None:
        """Test that AsyncSpooledClient also has with_options."""
        client = AsyncSpooledClient(api_key="sk_live_test")
        new_client = client.with_options(debug=True)

        assert new_client is not client
        assert isinstance(new_client, AsyncSpooledClient)
        assert new_client.get_config().debug_fn is not None


# ─────────────────────────────────────────────────────────────────────────────
# Test grpc property
# ─────────────────────────────────────────────────────────────────────────────


class TestGrpcProperty:
    """Tests for client.grpc lazy property."""

    def test_grpc_client_attribute_init(self) -> None:
        """Test that grpc client is not created on client init."""
        client = SpooledClient(api_key="sk_live_test")

        # The _grpc attribute should exist but be None initially
        assert hasattr(client, "_grpc")
        assert client._grpc is None

        client.close()

    def test_grpc_is_lazy_loaded(self) -> None:
        """Test that gRPC client is created lazily."""
        client = SpooledClient(api_key="sk_live_test")

        # gRPC client should not exist initially
        assert client._grpc is None

        client.close()

    def test_grpc_created_on_access(self) -> None:
        """Test that gRPC client is created on first access."""
        client = SpooledClient(api_key="sk_live_test", base_url="https://api.spooled.cloud")

        # Access the grpc property - will raise ImportError if grpc not installed
        try:
            grpc_client = client.grpc
            # If grpc is available, verify it was created
            assert grpc_client is not None
            assert client._grpc is not None
        except ImportError:
            # Expected if grpc module not available
            pass

        client.close()


# ─────────────────────────────────────────────────────────────────────────────
# Test realtime() factory
# ─────────────────────────────────────────────────────────────────────────────


class TestRealtimeFactory:
    """Tests for client.realtime() factory method."""

    def test_realtime_creates_websocket_by_default(self) -> None:
        """Test that realtime() creates WebSocket client by default."""
        client = SpooledClient(api_key="sk_live_test", access_token="test_token")

        try:
            realtime = client.realtime()
            # If successful, verify type
            assert realtime._options.type == "websocket"
        except ImportError:
            # Expected if realtime modules not available
            pass

        client.close()

    def test_realtime_creates_sse_when_specified(self) -> None:
        """Test that realtime() creates SSE client when specified."""
        client = SpooledClient(api_key="sk_live_test", access_token="test_token")

        try:
            realtime = client.realtime(type="sse")
            assert realtime._options.type == "sse"
        except ImportError:
            pass

        client.close()

    def test_realtime_passes_reconnect_options(self) -> None:
        """Test that realtime() passes reconnection options."""
        client = SpooledClient(api_key="sk_live_test", access_token="test_token")

        try:
            realtime = client.realtime(
                auto_reconnect=False,
                max_reconnect_attempts=5,
                reconnect_delay=2.0,
                max_reconnect_delay=60.0,
            )
            assert realtime._options.auto_reconnect is False
            assert realtime._options.max_reconnect_attempts == 5
            assert realtime._options.reconnect_delay == 2.0
            assert realtime._options.max_reconnect_delay == 60.0
        except ImportError:
            pass

        client.close()


# ─────────────────────────────────────────────────────────────────────────────
# Test SpooledRealtime unified class
# ─────────────────────────────────────────────────────────────────────────────


class TestSpooledRealtimeUnified:
    """Tests for unified SpooledRealtime class."""

    def test_realtime_options_defaults(self) -> None:
        """Test SpooledRealtimeOptions default values."""
        try:
            from spooled.realtime.unified import SpooledRealtimeOptions

            options = SpooledRealtimeOptions(
                base_url="https://api.spooled.cloud",
                token="test_token",
            )

            assert options.type == "websocket"
            assert options.auto_reconnect is True
            assert options.max_reconnect_attempts == 10
            assert options.reconnect_delay == 1.0
            assert options.max_reconnect_delay == 30.0
        except ImportError:
            pytest.skip("realtime module not available")

    def test_realtime_initial_state(self) -> None:
        """Test SpooledRealtime initial state."""
        try:
            from spooled.realtime.unified import (
                ConnectionState,
                SpooledRealtime,
                SpooledRealtimeOptions,
            )

            options = SpooledRealtimeOptions(
                base_url="https://api.spooled.cloud",
                token="test_token",
            )
            realtime = SpooledRealtime(options)

            assert realtime.state == ConnectionState.DISCONNECTED
            assert realtime.get_state() == ConnectionState.DISCONNECTED
        except ImportError:
            pytest.skip("realtime module not available")

    def test_realtime_on_decorator(self) -> None:
        """Test SpooledRealtime on() decorator."""
        try:
            from spooled.realtime.unified import (
                SpooledRealtime,
                SpooledRealtimeOptions,
            )

            options = SpooledRealtimeOptions(
                base_url="https://api.spooled.cloud",
                token="test_token",
            )
            realtime = SpooledRealtime(options)

            handler_called = False

            @realtime.on("job.created")
            def on_job_created(data: dict[str, Any]) -> None:
                nonlocal handler_called
                handler_called = True

            # Handler should be registered
            assert "job.created" in realtime._event_handlers
            assert len(realtime._event_handlers["job.created"]) == 1
        except ImportError:
            pytest.skip("realtime module not available")

    def test_realtime_on_direct_call(self) -> None:
        """Test SpooledRealtime on() direct call returns unsubscribe."""
        try:
            from spooled.realtime.unified import (
                SpooledRealtime,
                SpooledRealtimeOptions,
            )

            options = SpooledRealtimeOptions(
                base_url="https://api.spooled.cloud",
                token="test_token",
            )
            realtime = SpooledRealtime(options)

            def handler(data: dict[str, Any]) -> None:
                pass

            unsubscribe = realtime.on("job.created", handler)

            # Handler should be registered
            assert len(realtime._event_handlers["job.created"]) == 1

            # Unsubscribe should remove handler
            unsubscribe()
            assert len(realtime._event_handlers["job.created"]) == 0
        except ImportError:
            pytest.skip("realtime module not available")

    def test_realtime_on_event_handler(self) -> None:
        """Test SpooledRealtime on_event() for all events."""
        try:
            from spooled.realtime.events import RealtimeEvent
            from spooled.realtime.unified import (
                SpooledRealtime,
                SpooledRealtimeOptions,
            )

            options = SpooledRealtimeOptions(
                base_url="https://api.spooled.cloud",
                token="test_token",
            )
            realtime = SpooledRealtime(options)

            events_received: list[RealtimeEvent] = []

            def handler(event: RealtimeEvent) -> None:
                events_received.append(event)

            unsubscribe = realtime.on_event(handler)

            # Handler should be registered
            assert len(realtime._all_events_handlers) == 1

            # Unsubscribe should remove handler
            unsubscribe()
            assert len(realtime._all_events_handlers) == 0
        except ImportError:
            pytest.skip("realtime module not available")

    def test_realtime_on_state_change(self) -> None:
        """Test SpooledRealtime on_state_change()."""
        try:
            from spooled.realtime.unified import (
                ConnectionState,
                SpooledRealtime,
                SpooledRealtimeOptions,
            )

            options = SpooledRealtimeOptions(
                base_url="https://api.spooled.cloud",
                token="test_token",
            )
            realtime = SpooledRealtime(options)

            states: list[ConnectionState] = []

            @realtime.on_state_change
            def on_state(state: ConnectionState) -> None:
                states.append(state)

            # Handler should be registered
            assert len(realtime._state_change_handlers) == 1
        except ImportError:
            pytest.skip("realtime module not available")

    def test_realtime_subscription_filter(self) -> None:
        """Test SubscriptionFilter creation."""
        try:
            from spooled.realtime.unified import SubscriptionFilter

            filter1 = SubscriptionFilter(queue="emails")
            assert filter1.queue == "emails"
            assert filter1.job_id is None

            filter2 = SubscriptionFilter(job_id="job_123")
            assert filter2.queue is None
            assert filter2.job_id == "job_123"

            filter3 = SubscriptionFilter(queue="orders", job_id="job_456")
            assert filter3.queue == "orders"
            assert filter3.job_id == "job_456"
        except ImportError:
            pytest.skip("realtime module not available")


# ─────────────────────────────────────────────────────────────────────────────
# Test SSE Client Event Handlers
# ─────────────────────────────────────────────────────────────────────────────


class TestSSEClientEventHandlers:
    """Tests for SSE client event handler methods."""

    def test_sse_client_on_decorator(self) -> None:
        """Test SSEClient on() decorator."""
        try:
            from spooled.realtime.sse import SSEClient
        except ImportError:
            pytest.skip("SSE client not available")

        try:
            sse = SSEClient(
                base_url="https://api.spooled.cloud",
                token="test_token",
            )

            @sse.on("job.created")
            def handler(data: dict[str, Any]) -> None:
                pass

            assert "job.created" in sse._event_handlers
            assert len(sse._event_handlers["job.created"]) == 1
        except ImportError:
            pytest.skip("sseclient-py not installed")

    def test_sse_client_off(self) -> None:
        """Test SSEClient off() removes handler."""
        try:
            from spooled.realtime.sse import SSEClient
        except ImportError:
            pytest.skip("SSE client not available")

        try:
            sse = SSEClient(
                base_url="https://api.spooled.cloud",
                token="test_token",
            )

            def handler(data: dict[str, Any]) -> None:
                pass

            sse.on("job.created", handler)
            assert len(sse._event_handlers["job.created"]) == 1

            sse.off("job.created", handler)
            assert len(sse._event_handlers["job.created"]) == 0
        except ImportError:
            pytest.skip("sseclient-py not installed")

    def test_sse_client_on_event(self) -> None:
        """Test SSEClient on_event() for all events."""
        try:
            from spooled.realtime.events import RealtimeEvent
            from spooled.realtime.sse import SSEClient
        except ImportError:
            pytest.skip("SSE client not available")

        try:
            sse = SSEClient(
                base_url="https://api.spooled.cloud",
                token="test_token",
            )

            def handler(event: RealtimeEvent) -> None:
                pass

            unsubscribe = sse.on_event(handler)
            assert len(sse._all_events_handlers) == 1

            unsubscribe()
            assert len(sse._all_events_handlers) == 0
        except ImportError:
            pytest.skip("sseclient-py not installed")

    def test_sse_client_on_state_change(self) -> None:
        """Test SSEClient on_state_change()."""
        try:
            from spooled.realtime.sse import SSEClient, SSEConnectionState
        except ImportError:
            pytest.skip("SSE client not available")

        try:
            sse = SSEClient(
                base_url="https://api.spooled.cloud",
                token="test_token",
            )

            states: list[SSEConnectionState] = []

            @sse.on_state_change
            def on_state(state: SSEConnectionState) -> None:
                states.append(state)

            assert len(sse._state_change_handlers) == 1
        except ImportError:
            pytest.skip("sseclient-py not installed")

    def test_sse_client_state_property(self) -> None:
        """Test SSEClient state property."""
        try:
            from spooled.realtime.sse import SSEClient, SSEConnectionState
        except ImportError:
            pytest.skip("SSE client not available")

        try:
            sse = SSEClient(
                base_url="https://api.spooled.cloud",
                token="test_token",
            )

            assert sse.state == SSEConnectionState.DISCONNECTED
            assert sse.get_state() == SSEConnectionState.DISCONNECTED
        except ImportError:
            pytest.skip("sseclient-py not installed")


# ─────────────────────────────────────────────────────────────────────────────
# Test Async SSE Client Event Handlers
# ─────────────────────────────────────────────────────────────────────────────


class TestAsyncSSEClientEventHandlers:
    """Tests for async SSE client event handler methods."""

    def test_async_sse_client_on_decorator(self) -> None:
        """Test AsyncSSEClient on() decorator."""
        try:
            from spooled.realtime.sse import AsyncSSEClient
        except ImportError:
            pytest.skip("Async SSE client not available")

        sse = AsyncSSEClient(
            base_url="https://api.spooled.cloud",
            token="test_token",
        )

        @sse.on("job.created")
        def handler(data: dict[str, Any]) -> None:
            pass

        assert "job.created" in sse._event_handlers
        assert len(sse._event_handlers["job.created"]) == 1

    def test_async_sse_client_off(self) -> None:
        """Test AsyncSSEClient off() removes handler."""
        try:
            from spooled.realtime.sse import AsyncSSEClient
        except ImportError:
            pytest.skip("Async SSE client not available")

        sse = AsyncSSEClient(
            base_url="https://api.spooled.cloud",
            token="test_token",
        )

        def handler(data: dict[str, Any]) -> None:
            pass

        sse.on("job.created", handler)
        assert len(sse._event_handlers["job.created"]) == 1

        sse.off("job.created", handler)
        assert len(sse._event_handlers["job.created"]) == 0

    def test_async_sse_client_on_event(self) -> None:
        """Test AsyncSSEClient on_event() for all events."""
        try:
            from spooled.realtime.events import RealtimeEvent
            from spooled.realtime.sse import AsyncSSEClient
        except ImportError:
            pytest.skip("Async SSE client not available")

        sse = AsyncSSEClient(
            base_url="https://api.spooled.cloud",
            token="test_token",
        )

        def handler(event: RealtimeEvent) -> None:
            pass

        unsubscribe = sse.on_event(handler)
        assert len(sse._all_events_handlers) == 1

        unsubscribe()
        assert len(sse._all_events_handlers) == 0

    def test_async_sse_client_on_state_change(self) -> None:
        """Test AsyncSSEClient on_state_change()."""
        try:
            from spooled.realtime.sse import AsyncSSEClient, SSEConnectionState
        except ImportError:
            pytest.skip("Async SSE client not available")

        sse = AsyncSSEClient(
            base_url="https://api.spooled.cloud",
            token="test_token",
        )

        states: list[SSEConnectionState] = []

        @sse.on_state_change
        def on_state(state: SSEConnectionState) -> None:
            states.append(state)

        assert len(sse._state_change_handlers) == 1

    def test_async_sse_client_state_property(self) -> None:
        """Test AsyncSSEClient state property."""
        try:
            from spooled.realtime.sse import AsyncSSEClient, SSEConnectionState
        except ImportError:
            pytest.skip("Async SSE client not available")

        sse = AsyncSSEClient(
            base_url="https://api.spooled.cloud",
            token="test_token",
        )

        assert sse.state == SSEConnectionState.DISCONNECTED
        assert sse.get_state() == SSEConnectionState.DISCONNECTED

