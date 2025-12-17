"""
WebSocket client for real-time events.
"""

from __future__ import annotations

import contextlib
import json
import threading
from collections.abc import AsyncGenerator, Callable
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


class WebSocketClient:
    """
    Synchronous WebSocket client for real-time events.

    Note: Requires the 'realtime' extra: pip install spooled[realtime]

    Example:
        >>> ws = client.realtime.websocket(
        ...     on_open=lambda: print("Connected"),
        ...     on_close=lambda code, reason: print(f"Disconnected: {code}"),
        ... )
        >>> ws.subscribe(queue="emails")
        >>> @ws.on("job.created")
        ... def on_job_created(event):
        ...     print(f"Job created: {event.data}")
        >>> ws.connect()
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        on_open: Callable[[], None] | None = None,
        on_close: Callable[[int, str], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        """
        Initialize WebSocket client.

        Args:
            base_url: Base WebSocket URL (wss://...)
            token: JWT token for authentication
            on_open: Callback when connection opens
            on_close: Callback when connection closes
            on_error: Callback when error occurs
        """
        if not HAS_WEBSOCKETS:
            raise ImportError(
                "websockets package required. Install with: pip install spooled[realtime]"
            )

        self._base_url = base_url
        self._token = token
        self._on_open = on_open
        self._on_close = on_close
        self._on_error = on_error

        self._ws: Any = None
        self._connected = False
        self._event_handlers: dict[RealtimeEventType, list[Callable[[RealtimeEvent], None]]] = {}
        self._receive_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

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

    def subscribe(self, *, queue: str | None = None, job_id: str | None = None) -> None:
        """Subscribe to events for a queue or job."""
        if not self._ws:
            raise RuntimeError("WebSocket not connected")

        cmd = SubscribeCommand(queue=queue, job_id=job_id)
        self._ws.send(json.dumps(cmd.to_dict()))

    def unsubscribe(self, *, queue: str | None = None, job_id: str | None = None) -> None:
        """Unsubscribe from events."""
        if not self._ws:
            raise RuntimeError("WebSocket not connected")

        cmd = UnsubscribeCommand(queue=queue, job_id=job_id)
        self._ws.send(json.dumps(cmd.to_dict()))

    def ping(self) -> None:
        """Send ping to keep connection alive."""
        if not self._ws:
            raise RuntimeError("WebSocket not connected")

        cmd = PingCommand()
        self._ws.send(json.dumps(cmd.to_dict()))

    def connect(self) -> None:
        """Connect to WebSocket (blocking)."""
        ws_url = f"{self._base_url}/api/v1/ws?token={self._token}"

        try:
            self._ws = sync_ws.connect(ws_url)
            self._connected = True
            self._stop_event.clear()

            if self._on_open:
                self._on_open()

            # Start receive loop
            self._receive_loop()

        except Exception as e:
            if self._on_error:
                self._on_error(e)
            raise

    def connect_background(self) -> None:
        """Connect to WebSocket in background thread."""

        def run() -> None:
            try:
                self.connect()
            except Exception as e:
                if self._on_error:
                    self._on_error(e)

        self._receive_thread = threading.Thread(target=run, daemon=True)
        self._receive_thread.start()

    def disconnect(self) -> None:
        """Disconnect from WebSocket."""
        self._stop_event.set()
        self._connected = False

        if self._ws:
            with contextlib.suppress(Exception):
                self._ws.close()
            self._ws = None

        if self._on_close:
            self._on_close(1000, "Client disconnected")

    def _receive_loop(self) -> None:
        """Receive messages from WebSocket."""
        while self._connected and not self._stop_event.is_set():
            try:
                message = self._ws.recv()
                self._handle_message(message)
            except Exception as e:
                if not self._stop_event.is_set():
                    self._connected = False
                    if self._on_error:
                        self._on_error(e)
                    if self._on_close:
                        self._on_close(1006, str(e))
                break

    def _handle_message(self, message: str) -> None:
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            server_type = data.get("type", "error")
            event_data = data.get("data", {})

            event = RealtimeEvent.from_server_event(server_type, event_data)

            # Call handlers
            handlers = self._event_handlers.get(event.type, [])
            for handler in handlers:
                with contextlib.suppress(Exception):
                    handler(event)

        except json.JSONDecodeError:
            pass


class AsyncWebSocketClient:
    """
    Asynchronous WebSocket client for real-time events.

    Note: Requires the 'realtime' extra: pip install spooled[realtime]

    Example:
        >>> async with client.realtime.websocket() as ws:
        ...     await ws.subscribe(queue="emails")
        ...     async for event in ws.events():
        ...         print(f"Event: {event.type}")
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        on_open: Callable[[], None] | None = None,
        on_close: Callable[[int, str], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        """
        Initialize async WebSocket client.

        Args:
            base_url: Base WebSocket URL (wss://...)
            token: JWT token for authentication
            on_open: Callback when connection opens
            on_close: Callback when connection closes
            on_error: Callback when error occurs
        """
        if not HAS_WEBSOCKETS:
            raise ImportError(
                "websockets package required. Install with: pip install spooled[realtime]"
            )

        self._base_url = base_url
        self._token = token
        self._on_open = on_open
        self._on_close = on_close
        self._on_error = on_error

        self._ws: Any = None
        self._connected = False
        self._event_handlers: dict[RealtimeEventType, list[Callable[[RealtimeEvent], None]]] = {}

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

    async def subscribe(self, *, queue: str | None = None, job_id: str | None = None) -> None:
        """Subscribe to events for a queue or job."""
        if not self._ws:
            raise RuntimeError("WebSocket not connected")

        cmd = SubscribeCommand(queue=queue, job_id=job_id)
        await self._ws.send(json.dumps(cmd.to_dict()))

    async def unsubscribe(
        self, *, queue: str | None = None, job_id: str | None = None
    ) -> None:
        """Unsubscribe from events."""
        if not self._ws:
            raise RuntimeError("WebSocket not connected")

        cmd = UnsubscribeCommand(queue=queue, job_id=job_id)
        await self._ws.send(json.dumps(cmd.to_dict()))

    async def ping(self) -> None:
        """Send ping to keep connection alive."""
        if not self._ws:
            raise RuntimeError("WebSocket not connected")

        cmd = PingCommand()
        await self._ws.send(json.dumps(cmd.to_dict()))

    async def connect(self) -> None:
        """Connect to WebSocket."""
        ws_url = f"{self._base_url}/api/v1/ws?token={self._token}"

        try:
            self._ws = await websockets.connect(ws_url)
            self._connected = True

            if self._on_open:
                self._on_open()

        except Exception as e:
            if self._on_error:
                self._on_error(e)
            raise

    async def disconnect(self) -> None:
        """Disconnect from WebSocket."""
        self._connected = False

        if self._ws:
            with contextlib.suppress(Exception):
                await self._ws.close()
            self._ws = None

        if self._on_close:
            self._on_close(1000, "Client disconnected")

    async def events(self) -> AsyncGenerator[RealtimeEvent, None]:
        """
        Async generator that yields events.

        Example:
            >>> async for event in ws.events():
            ...     print(event)
        """
        if not self._ws:
            raise RuntimeError("WebSocket not connected")

        try:
            async for message in self._ws:
                event = self._parse_message(message)
                if event:
                    # Call handlers
                    handlers = self._event_handlers.get(event.type, [])
                    for handler in handlers:
                        with contextlib.suppress(Exception):
                            handler(event)
                    yield event
        except Exception as e:
            self._connected = False
            if self._on_error:
                self._on_error(e)
            if self._on_close:
                self._on_close(1006, str(e))

    def _parse_message(self, message: str) -> RealtimeEvent | None:
        """Parse WebSocket message to event."""
        try:
            data = json.loads(message)
            server_type = data.get("type", "error")
            event_data = data.get("data", {})
            return RealtimeEvent.from_server_event(server_type, event_data)
        except json.JSONDecodeError:
            return None

    async def __aenter__(self) -> AsyncWebSocketClient:
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.disconnect()


