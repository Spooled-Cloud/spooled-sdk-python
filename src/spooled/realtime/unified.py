"""
Unified Realtime Client for Spooled SDK.

Provides a common interface for both WebSocket and SSE connections.
"""

from __future__ import annotations

import contextlib
import json
import random
import threading
import time
from collections.abc import Callable, Generator
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from spooled.realtime.events import (
    RealtimeEvent,
    RealtimeEventType,
    SubscribeCommand,
    UnsubscribeCommand,
)

# Optional imports
try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    httpx = None  # type: ignore[assignment]

try:
    import sseclient

    HAS_SSE = True
except ImportError:
    HAS_SSE = False
    sseclient = None  # type: ignore[assignment]

try:
    import websockets
    import websockets.sync.client as sync_ws

    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    websockets = None  # type: ignore[assignment]
    sync_ws = None  # type: ignore[assignment]


# ─────────────────────────────────────────────────────────────────────────────
# Connection State
# ─────────────────────────────────────────────────────────────────────────────


class ConnectionState(str, Enum):
    """Connection state for realtime clients."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


# ─────────────────────────────────────────────────────────────────────────────
# Options
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SpooledRealtimeOptions:
    """Options for SpooledRealtime client."""

    base_url: str
    ws_url: str | None = None
    token: str = ""
    type: Literal["websocket", "sse"] = "websocket"
    auto_reconnect: bool = True
    max_reconnect_attempts: int = 10
    reconnect_delay: float = 1.0
    max_reconnect_delay: float = 30.0
    debug: Callable[[str, Any], None] | None = None


@dataclass
class SubscriptionFilter:
    """Filter for subscriptions."""

    queue: str | None = None
    job_id: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Event Handler Types
# ─────────────────────────────────────────────────────────────────────────────

EventHandler = Callable[[dict[str, Any]], None]
GenericEventHandler = Callable[[RealtimeEvent], None]
StateChangeHandler = Callable[[ConnectionState], None]


# ─────────────────────────────────────────────────────────────────────────────
# Unified Realtime Client
# ─────────────────────────────────────────────────────────────────────────────


class SpooledRealtime:
    """
    Unified Realtime Client.

    Provides a common interface for both WebSocket and SSE connections,
    matching the Node.js SDK API.

    Example:
        >>> # Create realtime client
        >>> realtime = client.realtime(type="websocket")
        >>>
        >>> # Add event listeners
        >>> @realtime.on("job.created")
        ... def on_job_created(data):
        ...     print(f"Job created: {data}")
        >>>
        >>> # Connect and subscribe
        >>> realtime.connect()
        >>> realtime.subscribe(SubscriptionFilter(queue="emails"))
        >>>
        >>> # Disconnect when done
        >>> realtime.disconnect()
    """

    def __init__(self, options: SpooledRealtimeOptions) -> None:
        """
        Initialize unified realtime client.

        Args:
            options: Realtime connection options
        """
        self._options = options
        self._debug = options.debug or (lambda msg, data: None)

        self._state = ConnectionState.DISCONNECTED
        self._reconnect_attempts = 0
        self._reconnect_timer: threading.Timer | None = None
        self._subscriptions: dict[str, SubscriptionFilter] = {}

        # Event handlers
        self._event_handlers: dict[RealtimeEventType, list[EventHandler]] = {}
        self._all_events_handlers: list[GenericEventHandler] = []
        self._state_change_handlers: list[StateChangeHandler] = []

        # Internal connection
        self._ws: Any = None
        self._sse_client: Any = None
        self._sse_response: Any = None
        self._http_client: Any = None
        self._receive_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    @property
    def state(self) -> ConnectionState:
        """Get current connection state."""
        return self._state

    def get_state(self) -> ConnectionState:
        """Get current connection state (alias for compatibility)."""
        return self._state

    # ─────────────────────────────────────────────────────────────────────────
    # Event Handlers
    # ─────────────────────────────────────────────────────────────────────────

    def on(
        self,
        event_type: RealtimeEventType,
        handler: EventHandler | None = None,
    ) -> Callable[..., Any]:
        """
        Add an event listener for a specific event type.

        Can be used as a decorator or called directly.

        Example (decorator):
            >>> @realtime.on("job.completed")
            ... def on_completed(data):
            ...     print(f"Job completed: {data}")

        Example (direct):
            >>> def handler(data):
            ...     print(data)
            >>> unsubscribe = realtime.on("job.created", handler)
            >>> unsubscribe()  # Remove listener
        """

        def decorator(fn: EventHandler) -> EventHandler:
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = []
            self._event_handlers[event_type].append(fn)
            return fn

        if handler is not None:
            decorator(handler)
            # Return unsubscribe function
            return lambda: self.off(event_type, handler)
        return decorator

    def off(self, event_type: RealtimeEventType, handler: EventHandler) -> None:
        """
        Remove an event listener.

        Args:
            event_type: Event type to remove handler from
            handler: Handler function to remove
        """
        if event_type in self._event_handlers:
            with contextlib.suppress(ValueError):
                self._event_handlers[event_type].remove(handler)

    def on_event(self, handler: GenericEventHandler) -> Callable[[], None]:
        """
        Add a listener for all events.

        Returns:
            Unsubscribe function

        Example:
            >>> unsubscribe = realtime.on_event(lambda e: print(e.type))
            >>> unsubscribe()  # Remove listener
        """
        self._all_events_handlers.append(handler)
        return lambda: self._all_events_handlers.remove(handler)

    def on_state_change(
        self, handler: StateChangeHandler | None = None
    ) -> Callable[..., Any]:
        """
        Add a listener for connection state changes.

        Can be used as a decorator or called directly.

        Returns:
            Unsubscribe function (when called directly)

        Example:
            >>> @realtime.on_state_change
            ... def on_state(state):
            ...     print(f"State: {state}")
        """

        def decorator(fn: StateChangeHandler) -> StateChangeHandler:
            self._state_change_handlers.append(fn)
            return fn

        if handler is not None:
            decorator(handler)
            return lambda: self._state_change_handlers.remove(handler)
        return decorator

    # ─────────────────────────────────────────────────────────────────────────
    # Connection Management
    # ─────────────────────────────────────────────────────────────────────────

    def connect(self, filter: SubscriptionFilter | None = None) -> None:
        """
        Connect to the realtime server.

        Args:
            filter: Optional subscription filter (for SSE)
        """
        if self._state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
            return

        self._set_state(ConnectionState.CONNECTING)

        if self._options.type == "sse":
            self._connect_sse(filter)
        else:
            self._connect_websocket()

    def disconnect(self) -> None:
        """Disconnect from the realtime server."""
        # Cancel reconnect timer
        if self._reconnect_timer:
            self._reconnect_timer.cancel()
            self._reconnect_timer = None

        self._stop_event.set()

        if self._options.type == "sse":
            self._disconnect_sse()
        else:
            self._disconnect_websocket()

        self._set_state(ConnectionState.DISCONNECTED)
        self._subscriptions.clear()

    def reconnect(self, filter: SubscriptionFilter | None = None) -> None:
        """
        Reconnect to the server, optionally with a new filter.

        Args:
            filter: Optional new subscription filter
        """
        self.disconnect()
        self.connect(filter)

    # ─────────────────────────────────────────────────────────────────────────
    # Subscriptions
    # ─────────────────────────────────────────────────────────────────────────

    def subscribe(self, filter: SubscriptionFilter) -> None:
        """
        Subscribe to events matching a filter.

        Args:
            filter: Subscription filter (queue and/or job_id)
        """
        filter_id = self._filter_to_id(filter)

        if filter_id in self._subscriptions:
            return

        self._subscriptions[filter_id] = filter

        if self._options.type == "sse":
            # SSE requires reconnection to change subscription
            if self._state == ConnectionState.CONNECTED:
                self.reconnect(filter)
        else:
            # WebSocket can subscribe dynamically
            if self._state == ConnectionState.CONNECTED and self._ws:
                self._send_ws_command(
                    SubscribeCommand(queue=filter.queue, job_id=filter.job_id)
                )

    def unsubscribe(self, filter: SubscriptionFilter) -> None:
        """
        Unsubscribe from events matching a filter.

        Args:
            filter: Subscription filter to remove
        """
        filter_id = self._filter_to_id(filter)

        if filter_id not in self._subscriptions:
            return

        del self._subscriptions[filter_id]

        if self._options.type == "websocket" and self._state == ConnectionState.CONNECTED:
            self._send_ws_command(
                UnsubscribeCommand(queue=filter.queue, job_id=filter.job_id)
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Event Generator (for iteration)
    # ─────────────────────────────────────────────────────────────────────────

    def events(self) -> Generator[RealtimeEvent, None, None]:
        """
        Generator that yields events.

        This is an alternative to using event handlers.

        Example:
            >>> realtime.connect()
            >>> for event in realtime.events():
            ...     print(f"Event: {event.type}")
        """
        if self._state != ConnectionState.CONNECTED:
            self.connect()

        if self._options.type == "sse":
            yield from self._sse_events()
        else:
            yield from self._ws_events()

    # ─────────────────────────────────────────────────────────────────────────
    # WebSocket Implementation
    # ─────────────────────────────────────────────────────────────────────────

    def _connect_websocket(self) -> None:
        """Connect via WebSocket."""
        if not HAS_WEBSOCKETS:
            raise ImportError(
                "websockets package required. Install with: pip install spooled[realtime]"
            )

        ws_url = self._build_ws_url()
        self._debug(f"Connecting to WebSocket: {ws_url}", None)

        try:
            self._ws = sync_ws.connect(ws_url)
            self._set_state(ConnectionState.CONNECTED)
            self._reconnect_attempts = 0
            self._stop_event.clear()

            # Start receive thread
            self._receive_thread = threading.Thread(
                target=self._ws_receive_loop, daemon=True
            )
            self._receive_thread.start()

            # Resubscribe
            self._resubscribe_all()

            self._debug("WebSocket connected", None)

        except Exception as e:
            self._debug(f"WebSocket connection failed: {e}", None)
            self._set_state(ConnectionState.DISCONNECTED)
            raise

    def _disconnect_websocket(self) -> None:
        """Disconnect WebSocket."""
        if self._ws:
            with contextlib.suppress(Exception):
                self._ws.close()
            self._ws = None

    def _ws_receive_loop(self) -> None:
        """Receive messages from WebSocket."""
        while not self._stop_event.is_set() and self._ws:
            try:
                message = self._ws.recv(timeout=1.0)
                self._handle_message(message)
            except TimeoutError:
                continue
            except Exception as e:
                if not self._stop_event.is_set():
                    self._debug(f"WebSocket receive error: {e}", None)
                    self._handle_disconnect()
                break

    def _ws_events(self) -> Generator[RealtimeEvent, None, None]:
        """Generator for WebSocket events."""
        while not self._stop_event.is_set() and self._ws:
            try:
                message = self._ws.recv(timeout=1.0)
                event = self._parse_message(message)
                if event:
                    yield event
            except TimeoutError:
                continue
            except Exception:
                if not self._stop_event.is_set():
                    break

    def _build_ws_url(self) -> str:
        """Build WebSocket URL."""
        ws_url = self._options.ws_url or self._options.base_url.replace(
            "http://", "ws://"
        ).replace("https://", "wss://")
        return f"{ws_url}/api/v1/ws?token={self._options.token}"

    def _send_ws_command(self, command: SubscribeCommand | UnsubscribeCommand) -> None:
        """Send WebSocket command."""
        if self._ws:
            cmd_dict = command.to_dict()
            cmd_dict["requestId"] = f"req_{int(time.time() * 1000)}_{random.randint(0, 999999):06d}"
            self._ws.send(json.dumps(cmd_dict))

    def _resubscribe_all(self) -> None:
        """Resubscribe to all subscriptions."""
        for filter in self._subscriptions.values():
            if self._options.type == "websocket" and self._ws:
                self._send_ws_command(
                    SubscribeCommand(queue=filter.queue, job_id=filter.job_id)
                )

    # ─────────────────────────────────────────────────────────────────────────
    # SSE Implementation
    # ─────────────────────────────────────────────────────────────────────────

    def _connect_sse(self, filter: SubscriptionFilter | None = None) -> None:
        """Connect via SSE."""
        if not HAS_HTTPX:
            raise ImportError(
                "httpx package required. Install with: pip install spooled[realtime]"
            )

        url = self._build_sse_url(filter)
        self._debug(f"Connecting to SSE: {url}", None)

        try:
            self._http_client = httpx.Client()
            self._sse_response = self._http_client.stream(
                "GET",
                url,
                headers={
                    "Authorization": f"Bearer {self._options.token}",
                    "Accept": "text/event-stream",
                },
            ).__enter__()

            if HAS_SSE:
                self._sse_client = sseclient.SSEClient(self._sse_response.iter_lines())

            self._set_state(ConnectionState.CONNECTED)
            self._reconnect_attempts = 0
            self._stop_event.clear()

            # Start receive thread
            self._receive_thread = threading.Thread(
                target=self._sse_receive_loop, daemon=True
            )
            self._receive_thread.start()

            self._debug("SSE connected", None)

        except Exception as e:
            self._debug(f"SSE connection failed: {e}", None)
            self._set_state(ConnectionState.DISCONNECTED)
            raise

    def _disconnect_sse(self) -> None:
        """Disconnect SSE."""
        if self._sse_response:
            with contextlib.suppress(Exception):
                self._sse_response.close()
            self._sse_response = None

        if self._http_client:
            with contextlib.suppress(Exception):
                self._http_client.close()
            self._http_client = None

        self._sse_client = None

    def _sse_receive_loop(self) -> None:
        """Receive events from SSE."""
        if not self._sse_client:
            return

        try:
            for event in self._sse_client.events():
                if self._stop_event.is_set():
                    break

                if event.data:
                    parsed = self._parse_sse_event(event.event, event.data)
                    if parsed:
                        self._emit_event(parsed)
        except Exception as e:
            if not self._stop_event.is_set():
                self._debug(f"SSE receive error: {e}", None)
                self._handle_disconnect()

    def _sse_events(self) -> Generator[RealtimeEvent, None, None]:
        """Generator for SSE events."""
        if not self._sse_client:
            return

        try:
            for event in self._sse_client.events():
                if self._stop_event.is_set():
                    break

                if event.data:
                    parsed = self._parse_sse_event(event.event, event.data)
                    if parsed:
                        yield parsed
        except Exception:
            if not self._stop_event.is_set():
                pass

    def _build_sse_url(self, filter: SubscriptionFilter | None = None) -> str:
        """Build SSE endpoint URL."""
        # Check subscriptions for filter
        if not filter and self._subscriptions:
            filter = next(iter(self._subscriptions.values()))

        if filter:
            if filter.job_id:
                return f"{self._options.base_url}/api/v1/events/jobs/{filter.job_id}"
            if filter.queue:
                return f"{self._options.base_url}/api/v1/events/queues/{filter.queue}"

        return f"{self._options.base_url}/api/v1/events"

    def _parse_sse_event(self, event_type: str, data: str) -> RealtimeEvent | None:
        """Parse SSE event."""
        try:
            event_data = json.loads(data)
            return RealtimeEvent.from_server_event(event_type or "message", event_data)
        except json.JSONDecodeError:
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Common Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _set_state(self, state: ConnectionState) -> None:
        """Update connection state and notify handlers."""
        if self._state != state:
            self._state = state
            for handler in self._state_change_handlers:
                with contextlib.suppress(Exception):
                    handler(state)

    def _handle_message(self, message: str) -> None:
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            msg_type = data.get("type", "")

            # Skip command responses
            if msg_type in ("subscribed", "unsubscribed", "error", "pong"):
                return

            event = RealtimeEvent.from_server_event(msg_type, data.get("data", {}))
            self._emit_event(event)

        except json.JSONDecodeError:
            pass

    def _parse_message(self, message: str) -> RealtimeEvent | None:
        """Parse WebSocket message to event."""
        try:
            data = json.loads(message)
            msg_type = data.get("type", "")

            if msg_type in ("subscribed", "unsubscribed", "error", "pong"):
                return None

            return RealtimeEvent.from_server_event(msg_type, data.get("data", {}))
        except json.JSONDecodeError:
            return None

    def _emit_event(self, event: RealtimeEvent) -> None:
        """Emit event to handlers."""
        # Specific handlers
        handlers = self._event_handlers.get(event.type, [])
        for event_handler in handlers:
            with contextlib.suppress(Exception):
                event_handler(event.data)

        # All-events handlers
        for generic_handler in self._all_events_handlers:
            with contextlib.suppress(Exception):
                generic_handler(event)

    def _handle_disconnect(self) -> None:
        """Handle disconnection and attempt reconnect."""
        if self._options.type == "sse":
            self._disconnect_sse()
        else:
            self._disconnect_websocket()

        if (
            self._options.auto_reconnect
            and self._reconnect_attempts < self._options.max_reconnect_attempts
        ):
            self._schedule_reconnect()
        else:
            self._set_state(ConnectionState.DISCONNECTED)

    def _schedule_reconnect(self) -> None:
        """Schedule reconnection attempt."""
        self._set_state(ConnectionState.RECONNECTING)
        self._reconnect_attempts += 1

        delay = min(
            self._options.reconnect_delay * (2 ** (self._reconnect_attempts - 1)),
            self._options.max_reconnect_delay,
        )
        delay += delay * 0.25 * random.random()

        self._debug(f"Scheduling reconnect in {delay:.1f}s", None)

        def do_reconnect() -> None:
            try:
                self.connect()
            except Exception as e:
                self._debug(f"Reconnect failed: {e}", None)
                self._handle_disconnect()

        self._reconnect_timer = threading.Timer(delay, do_reconnect)
        self._reconnect_timer.daemon = True
        self._reconnect_timer.start()

    @staticmethod
    def _filter_to_id(filter: SubscriptionFilter) -> str:
        """Generate unique ID for filter."""
        return json.dumps(
            {"queue": filter.queue, "job_id": filter.job_id}, sort_keys=True
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Context Manager
    # ─────────────────────────────────────────────────────────────────────────

    def __enter__(self) -> SpooledRealtime:
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.disconnect()
