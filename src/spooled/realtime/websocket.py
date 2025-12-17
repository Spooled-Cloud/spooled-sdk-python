"""
WebSocket client for real-time events with auto-reconnect support.

Provides full feature parity with the Node.js SDK WebSocket client,
including auto-reconnect with exponential backoff, connection state management,
and typed event handling.
"""

from __future__ import annotations

import contextlib
import json
import random
import threading
import time
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from spooled.realtime.events import (
    PingCommand,
    RealtimeEvent,
    RealtimeEventType,
    SubscribeCommand,
    UnsubscribeCommand,
)

# Optional websockets import
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
    """WebSocket connection state."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


# ─────────────────────────────────────────────────────────────────────────────
# Subscription Filter
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SubscriptionFilter:
    """Filter for subscriptions."""

    queue: str | None = None
    job_id: str | None = None

    def to_id(self) -> str:
        """Generate unique ID for this filter."""
        return json.dumps({"queue": self.queue, "job_id": self.job_id}, sort_keys=True)


# ─────────────────────────────────────────────────────────────────────────────
# Connection Options
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class WebSocketConnectionOptions:
    """Options for WebSocket connection."""

    ws_url: str
    token: str
    auto_reconnect: bool = True
    max_reconnect_attempts: int = 10
    reconnect_delay: float = 1.0  # seconds
    max_reconnect_delay: float = 30.0  # seconds
    command_timeout: float = 10.0  # seconds
    debug: Callable[[str, Any], None] | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Pending Command
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PendingCommand:
    """Represents a pending command waiting for response."""

    event: threading.Event = field(default_factory=threading.Event)
    error: str | None = None
    resolved: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket Client
# ─────────────────────────────────────────────────────────────────────────────


class WebSocketClient:
    """
    Synchronous WebSocket client with auto-reconnect support.

    Provides full feature parity with the Node.js SDK WebSocket client.

    Note: Requires the 'realtime' extra: pip install spooled[realtime]

    Example:
        >>> ws = WebSocketClient(WebSocketConnectionOptions(
        ...     ws_url="wss://api.spooled.cloud",
        ...     token="sk_live_...",
        ... ))
        >>>
        >>> # Set up handlers
        >>> @ws.on("job.created")
        ... def on_job_created(event):
        ...     print(f"Job created: {event.data}")
        >>>
        >>> @ws.on_state_change
        ... def on_state(state):
        ...     print(f"State: {state}")
        >>>
        >>> # Connect and subscribe
        >>> ws.connect()
        >>> ws.subscribe(SubscriptionFilter(queue="emails"))
        >>>
        >>> # Run until interrupted
        >>> try:
        ...     while ws.state == ConnectionState.CONNECTED:
        ...         time.sleep(1)
        ... finally:
        ...     ws.disconnect()
    """

    def __init__(self, options: WebSocketConnectionOptions) -> None:
        """
        Initialize WebSocket client.

        Args:
            options: Connection options
        """
        if not HAS_WEBSOCKETS:
            raise ImportError(
                "websockets package required. Install with: pip install spooled[realtime]"
            )

        self._options = options
        self._debug = options.debug or (lambda msg, data: None)

        self._ws: Any = None
        self._state = ConnectionState.DISCONNECTED
        self._reconnect_attempts = 0
        self._reconnect_timer: threading.Timer | None = None
        self._subscriptions: dict[str, SubscriptionFilter] = {}
        self._pending_commands: dict[str, PendingCommand] = {}

        # Event handlers
        self._event_handlers: dict[RealtimeEventType, list[Callable[[RealtimeEvent], None]]] = {}
        self._all_events_handlers: list[Callable[[RealtimeEvent], None]] = []
        self._state_change_handlers: list[Callable[[ConnectionState], None]] = []

        # Threading
        self._receive_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    @property
    def state(self) -> ConnectionState:
        """Get current connection state."""
        return self._state

    def on(
        self,
        event_type: RealtimeEventType,
        handler: Callable[[RealtimeEvent], None] | None = None,
    ) -> Callable[..., Any]:
        """
        Register event handler (decorator).

        Example:
            >>> @ws.on("job.created")
            ... def on_job_created(event):
            ...     print(f"Job created: {event.data}")
        """

        def decorator(fn: Callable[[RealtimeEvent], None]) -> Callable[[RealtimeEvent], None]:
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = []
            self._event_handlers[event_type].append(fn)
            return fn

        if handler is not None:
            decorator(handler)
            return handler
        return decorator

    def on_event(self, handler: Callable[[RealtimeEvent], None]) -> Callable[[], None]:
        """
        Add a listener for all events.

        Returns unsubscribe function.
        """
        self._all_events_handlers.append(handler)
        return lambda: self._all_events_handlers.remove(handler)

    def on_state_change(
        self, handler: Callable[[ConnectionState], None] | None = None
    ) -> Callable[..., Any]:
        """
        Register state change handler (decorator).

        Returns unsubscribe function if used directly.
        """

        def decorator(fn: Callable[[ConnectionState], None]) -> Callable[[ConnectionState], None]:
            self._state_change_handlers.append(fn)
            return fn

        if handler is not None:
            decorator(handler)
            # Return unsubscribe function
            return lambda: self._state_change_handlers.remove(handler)
        return decorator

    def connect(self) -> None:
        """
        Connect to WebSocket server.

        Blocks until connected or raises an exception.
        """
        if self._state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
            return

        self._set_state(ConnectionState.CONNECTING)
        ws_url = self._build_ws_url()

        self._debug(f"Connecting to {ws_url}", None)

        try:
            self._ws = sync_ws.connect(ws_url)
            self._set_state(ConnectionState.CONNECTED)
            self._reconnect_attempts = 0
            self._stop_event.clear()

            # Start receive thread
            self._receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._receive_thread.start()

            # Resubscribe to all subscriptions
            self._resubscribe_all()

            self._debug("WebSocket connected", None)

        except Exception as e:
            self._debug(f"WebSocket connection failed: {e}", None)
            self._set_state(ConnectionState.DISCONNECTED)
            raise

    def connect_async(self) -> None:
        """Connect to WebSocket server in background thread."""

        def run() -> None:
            try:
                self.connect()
            except Exception as e:
                self._debug(f"Background connection failed: {e}", None)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def disconnect(self) -> None:
        """Disconnect from WebSocket server."""
        # Cancel any pending reconnect
        if self._reconnect_timer:
            self._reconnect_timer.cancel()
            self._reconnect_timer = None

        # Stop receive loop
        self._stop_event.set()

        # Close WebSocket
        if self._ws:
            with contextlib.suppress(Exception):
                self._ws.close()
            self._ws = None

        self._set_state(ConnectionState.DISCONNECTED)
        self._subscriptions.clear()
        self._clear_pending_commands()

    def subscribe(self, filter: SubscriptionFilter) -> None:
        """
        Subscribe to events matching a filter.

        Args:
            filter: Subscription filter (queue and/or job_id)
        """
        filter_id = filter.to_id()

        if filter_id in self._subscriptions:
            return  # Already subscribed

        self._subscriptions[filter_id] = filter

        if self._state == ConnectionState.CONNECTED:
            self._send_command(SubscribeCommand(queue=filter.queue, job_id=filter.job_id))

    def unsubscribe(self, filter: SubscriptionFilter) -> None:
        """
        Unsubscribe from events matching a filter.

        Args:
            filter: Subscription filter to remove
        """
        filter_id = filter.to_id()

        if filter_id not in self._subscriptions:
            return  # Not subscribed

        del self._subscriptions[filter_id]

        if self._state == ConnectionState.CONNECTED:
            self._send_command(UnsubscribeCommand(queue=filter.queue, job_id=filter.job_id))

    def ping(self) -> None:
        """Send ping to keep connection alive."""
        if self._ws:
            self._send_command(PingCommand())

    # ─────────────────────────────────────────────────────────────────────────
    # Private methods
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ws_url(self) -> str:
        """Build WebSocket URL with token."""
        return f"{self._options.ws_url}/api/v1/ws?token={self._options.token}"

    def _set_state(self, state: ConnectionState) -> None:
        """Update connection state and notify handlers."""
        if self._state != state:
            self._state = state
            for handler in self._state_change_handlers:
                with contextlib.suppress(Exception):
                    handler(state)

    def _receive_loop(self) -> None:
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

    def _handle_message(self, message: str) -> None:
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)

            # Check if this is a command response
            msg_type = data.get("type", "")
            if msg_type in ("subscribed", "unsubscribed", "error", "pong"):
                self._handle_command_response(data)
                return

            # Handle as event
            event_data = data.get("data", {})
            event = RealtimeEvent.from_server_event(msg_type, event_data)

            self._debug(f"Received event: {event.type}", event_data)

            # Emit to specific handlers
            handlers = self._event_handlers.get(event.type, [])
            for handler in handlers:
                with contextlib.suppress(Exception):
                    handler(event)

            # Emit to all-events handlers
            for handler in self._all_events_handlers:
                with contextlib.suppress(Exception):
                    handler(event)

        except json.JSONDecodeError:
            self._debug(f"Failed to parse message: {message}", None)

    def _handle_command_response(self, data: dict[str, Any]) -> None:
        """Handle command response."""
        request_id = data.get("requestId")
        if not request_id:
            return

        with self._lock:
            pending = self._pending_commands.get(request_id)
            if not pending:
                return

            if data.get("type") == "error":
                pending.error = data.get("error", "Unknown error")
            pending.resolved = True
            pending.event.set()

    def _handle_disconnect(self) -> None:
        """Handle WebSocket disconnection."""
        self._ws = None
        self._clear_pending_commands()

        if (
            self._options.auto_reconnect
            and self._reconnect_attempts < self._options.max_reconnect_attempts
        ):
            self._schedule_reconnect()
        else:
            self._set_state(ConnectionState.DISCONNECTED)

    def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt."""
        self._set_state(ConnectionState.RECONNECTING)
        self._reconnect_attempts += 1

        # Calculate delay with exponential backoff and jitter
        delay = min(
            self._options.reconnect_delay * (2 ** (self._reconnect_attempts - 1)),
            self._options.max_reconnect_delay,
        )
        # Add jitter (up to 25%)
        jitter = delay * 0.25 * random.random()
        delay += jitter

        self._debug(
            f"Scheduling reconnect attempt {self._reconnect_attempts} in {delay:.1f}s",
            None,
        )

        def do_reconnect() -> None:
            try:
                self._ws = sync_ws.connect(self._build_ws_url())
                self._set_state(ConnectionState.CONNECTED)
                self._reconnect_attempts = 0

                # Restart receive loop
                self._stop_event.clear()
                self._receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
                self._receive_thread.start()

                # Resubscribe
                self._resubscribe_all()

                self._debug("Reconnected successfully", None)

            except Exception as e:
                self._debug(f"Reconnect failed: {e}", None)
                self._handle_disconnect()

        self._reconnect_timer = threading.Timer(delay, do_reconnect)
        self._reconnect_timer.daemon = True
        self._reconnect_timer.start()

    def _resubscribe_all(self) -> None:
        """Resubscribe to all subscriptions after reconnect."""
        for filter in self._subscriptions.values():
            try:
                self._send_command(SubscribeCommand(queue=filter.queue, job_id=filter.job_id))
            except Exception as e:
                self._debug(f"Failed to resubscribe: {e}", filter)

    def _send_command(self, command: SubscribeCommand | UnsubscribeCommand | PingCommand) -> None:
        """Send a command to the server."""
        if not self._ws or self._state != ConnectionState.CONNECTED:
            raise RuntimeError("WebSocket not connected")

        # Generate request ID
        request_id = f"req_{int(time.time() * 1000)}_{random.randint(0, 999999):06d}"

        # Create pending command
        pending = PendingCommand()
        with self._lock:
            self._pending_commands[request_id] = pending

        try:
            # Send command
            cmd_dict = command.to_dict()
            cmd_dict["requestId"] = request_id
            self._ws.send(json.dumps(cmd_dict))

            # Wait for response with timeout
            if not pending.event.wait(timeout=self._options.command_timeout):
                raise TimeoutError("Command timeout")

            if pending.error:
                raise RuntimeError(pending.error)

        finally:
            with self._lock:
                self._pending_commands.pop(request_id, None)

    def _clear_pending_commands(self) -> None:
        """Clear all pending commands with error."""
        with self._lock:
            for pending in self._pending_commands.values():
                pending.error = "Connection closed"
                pending.event.set()
            self._pending_commands.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Async WebSocket Client
# ─────────────────────────────────────────────────────────────────────────────


class AsyncWebSocketClient:
    """
    Asynchronous WebSocket client with auto-reconnect support.

    Provides full feature parity with the Node.js SDK WebSocket client.

    Note: Requires the 'realtime' extra: pip install spooled[realtime]

    Example:
        >>> async with AsyncWebSocketClient(WebSocketConnectionOptions(
        ...     ws_url="wss://api.spooled.cloud",
        ...     token="sk_live_...",
        ... )) as ws:
        ...     await ws.subscribe(SubscriptionFilter(queue="emails"))
        ...     async for event in ws.events():
        ...         print(f"Event: {event.type}")
    """

    def __init__(self, options: WebSocketConnectionOptions) -> None:
        """
        Initialize async WebSocket client.

        Args:
            options: Connection options
        """
        if not HAS_WEBSOCKETS:
            raise ImportError(
                "websockets package required. Install with: pip install spooled[realtime]"
            )

        self._options = options
        self._debug = options.debug or (lambda msg, data: None)

        self._ws: Any = None
        self._state = ConnectionState.DISCONNECTED
        self._reconnect_attempts = 0
        self._subscriptions: dict[str, SubscriptionFilter] = {}
        self._pending_commands: dict[str, PendingCommand] = {}

        # Event handlers
        self._event_handlers: dict[RealtimeEventType, list[Callable[[RealtimeEvent], None]]] = {}
        self._all_events_handlers: list[Callable[[RealtimeEvent], None]] = []
        self._state_change_handlers: list[Callable[[ConnectionState], None]] = []

    @property
    def state(self) -> ConnectionState:
        """Get current connection state."""
        return self._state

    def on(
        self,
        event_type: RealtimeEventType,
        handler: Callable[[RealtimeEvent], None] | None = None,
    ) -> Callable[..., Any]:
        """Register event handler (decorator)."""

        def decorator(fn: Callable[[RealtimeEvent], None]) -> Callable[[RealtimeEvent], None]:
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = []
            self._event_handlers[event_type].append(fn)
            return fn

        if handler is not None:
            decorator(handler)
            return handler
        return decorator

    def on_event(self, handler: Callable[[RealtimeEvent], None]) -> Callable[[], None]:
        """Add a listener for all events."""
        self._all_events_handlers.append(handler)
        return lambda: self._all_events_handlers.remove(handler)

    def on_state_change(
        self, handler: Callable[[ConnectionState], None] | None = None
    ) -> Callable[..., Any]:
        """Register state change handler (decorator)."""

        def decorator(fn: Callable[[ConnectionState], None]) -> Callable[[ConnectionState], None]:
            self._state_change_handlers.append(fn)
            return fn

        if handler is not None:
            decorator(handler)
            return lambda: self._state_change_handlers.remove(handler)
        return decorator

    async def connect(self) -> None:
        """Connect to WebSocket server."""
        if self._state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
            return

        self._set_state(ConnectionState.CONNECTING)
        ws_url = self._build_ws_url()

        self._debug(f"Connecting to {ws_url}", None)

        try:
            self._ws = await websockets.connect(ws_url)
            self._set_state(ConnectionState.CONNECTED)
            self._reconnect_attempts = 0

            # Resubscribe to all subscriptions
            await self._resubscribe_all()

            self._debug("WebSocket connected", None)

        except Exception as e:
            self._debug(f"WebSocket connection failed: {e}", None)
            self._set_state(ConnectionState.DISCONNECTED)
            raise

    async def disconnect(self) -> None:
        """Disconnect from WebSocket server."""
        if self._ws:
            with contextlib.suppress(Exception):
                await self._ws.close()
            self._ws = None

        self._set_state(ConnectionState.DISCONNECTED)
        self._subscriptions.clear()

    async def subscribe(self, filter: SubscriptionFilter) -> None:
        """Subscribe to events matching a filter."""
        filter_id = filter.to_id()

        if filter_id in self._subscriptions:
            return

        self._subscriptions[filter_id] = filter

        if self._state == ConnectionState.CONNECTED:
            await self._send_command(SubscribeCommand(queue=filter.queue, job_id=filter.job_id))

    async def unsubscribe(self, filter: SubscriptionFilter) -> None:
        """Unsubscribe from events matching a filter."""
        filter_id = filter.to_id()

        if filter_id not in self._subscriptions:
            return

        del self._subscriptions[filter_id]

        if self._state == ConnectionState.CONNECTED:
            await self._send_command(UnsubscribeCommand(queue=filter.queue, job_id=filter.job_id))

    async def ping(self) -> None:
        """Send ping to keep connection alive."""
        if self._ws:
            await self._send_command(PingCommand())

    async def events(self) -> AsyncGenerator[RealtimeEvent, None]:
        """
        Async generator that yields events.

        Automatically handles reconnection if auto_reconnect is enabled.

        Example:
            >>> async for event in ws.events():
            ...     print(f"Event: {event.type}")
        """
        if not self._ws:
            raise RuntimeError("WebSocket not connected")

        while True:
            try:
                async for message in self._ws:
                    event = self._parse_message(message)
                    if event:
                        # Call handlers
                        handlers = self._event_handlers.get(event.type, [])
                        for handler in handlers:
                            with contextlib.suppress(Exception):
                                handler(event)

                        for handler in self._all_events_handlers:
                            with contextlib.suppress(Exception):
                                handler(event)

                        yield event

                # Stream ended normally
                break

            except Exception as e:
                self._debug(f"WebSocket error: {e}", None)

                if not self._options.auto_reconnect:
                    self._set_state(ConnectionState.DISCONNECTED)
                    raise

                if self._reconnect_attempts >= self._options.max_reconnect_attempts:
                    self._set_state(ConnectionState.DISCONNECTED)
                    raise

                # Try to reconnect
                await self._do_reconnect()

    async def _do_reconnect(self) -> None:
        """Attempt to reconnect."""
        import asyncio

        self._set_state(ConnectionState.RECONNECTING)
        self._reconnect_attempts += 1

        # Calculate delay with exponential backoff
        delay = min(
            self._options.reconnect_delay * (2 ** (self._reconnect_attempts - 1)),
            self._options.max_reconnect_delay,
        )
        delay += delay * 0.25 * random.random()

        self._debug(f"Reconnecting in {delay:.1f}s (attempt {self._reconnect_attempts})", None)

        await asyncio.sleep(delay)

        try:
            self._ws = await websockets.connect(self._build_ws_url())
            self._set_state(ConnectionState.CONNECTED)
            self._reconnect_attempts = 0
            await self._resubscribe_all()
            self._debug("Reconnected successfully", None)
        except Exception as e:
            self._debug(f"Reconnect failed: {e}", None)
            raise

    # ─────────────────────────────────────────────────────────────────────────
    # Private methods
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ws_url(self) -> str:
        """Build WebSocket URL with token."""
        return f"{self._options.ws_url}/api/v1/ws?token={self._options.token}"

    def _set_state(self, state: ConnectionState) -> None:
        """Update connection state and notify handlers."""
        if self._state != state:
            self._state = state
            for handler in self._state_change_handlers:
                with contextlib.suppress(Exception):
                    handler(state)

    def _parse_message(self, message: str) -> RealtimeEvent | None:
        """Parse WebSocket message to event."""
        try:
            data = json.loads(message)
            msg_type = data.get("type", "")

            # Skip command responses
            if msg_type in ("subscribed", "unsubscribed", "error", "pong"):
                return None

            event_data = data.get("data", {})
            return RealtimeEvent.from_server_event(msg_type, event_data)
        except json.JSONDecodeError:
            return None

    async def _send_command(
        self, command: SubscribeCommand | UnsubscribeCommand | PingCommand
    ) -> None:
        """Send a command to the server."""
        if not self._ws or self._state != ConnectionState.CONNECTED:
            raise RuntimeError("WebSocket not connected")

        request_id = f"req_{int(time.time() * 1000)}_{random.randint(0, 999999):06d}"
        cmd_dict = command.to_dict()
        cmd_dict["requestId"] = request_id
        await self._ws.send(json.dumps(cmd_dict))

    async def _resubscribe_all(self) -> None:
        """Resubscribe to all subscriptions after reconnect."""
        for filter in self._subscriptions.values():
            try:
                await self._send_command(SubscribeCommand(queue=filter.queue, job_id=filter.job_id))
            except Exception as e:
                self._debug(f"Failed to resubscribe: {e}", filter)

    async def __aenter__(self) -> AsyncWebSocketClient:
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.disconnect()
