"""
Server-Sent Events (SSE) client for real-time events.
"""

from __future__ import annotations

import contextlib
import json
import threading
from collections.abc import AsyncGenerator, Callable, Generator
from enum import Enum
from typing import Any

import httpx

from spooled.realtime.events import RealtimeEvent, RealtimeEventType

# Optional sseclient import
try:
    import sseclient

    HAS_SSE = True
except ImportError:
    HAS_SSE = False
    sseclient = None  # type: ignore[assignment]


# ─────────────────────────────────────────────────────────────────────────────
# Connection State
# ─────────────────────────────────────────────────────────────────────────────


class SSEConnectionState(str, Enum):
    """Connection state for SSE clients."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


# ─────────────────────────────────────────────────────────────────────────────
# Handler Types
# ─────────────────────────────────────────────────────────────────────────────

EventHandler = Callable[[dict[str, Any]], None]
GenericEventHandler = Callable[[RealtimeEvent], None]
StateChangeHandler = Callable[[SSEConnectionState], None]


class SSEClient:
    """
    Server-Sent Events client for real-time events.

    Note: Requires the 'realtime' extra: pip install spooled[realtime]

    Example:
        >>> # SSE for all events
        >>> sse = SSEClient(base_url="https://api.spooled.cloud", token="...")
        >>>
        >>> # Add event handlers
        >>> @sse.on("job.created")
        ... def on_job_created(data):
        ...     print(f"Job created: {data}")
        >>>
        >>> # Connect and iterate events
        >>> with sse:
        ...     for event in sse.events():
        ...         print(f"Event: {event.type}")
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        queue: str | None = None,
        job_id: str | None = None,
        auto_reconnect: bool = True,
        max_reconnect_attempts: int = 10,
        reconnect_delay: float = 1.0,
    ) -> None:
        """
        Initialize SSE client.

        Args:
            base_url: Base API URL
            token: JWT token for authentication
            queue: Optional queue name to filter events
            job_id: Optional job ID to filter events
            auto_reconnect: Whether to auto-reconnect on disconnect
            max_reconnect_attempts: Maximum reconnection attempts
            reconnect_delay: Base delay between reconnection attempts
        """
        if not HAS_SSE:
            raise ImportError(
                "sseclient-py package required. Install with: pip install spooled[realtime]"
            )

        self._base_url = base_url
        self._token = token
        self._queue = queue
        self._job_id = job_id
        self._auto_reconnect = auto_reconnect
        self._max_reconnect_attempts = max_reconnect_attempts
        self._reconnect_delay = reconnect_delay

        self._client: httpx.Client | None = None
        self._response: httpx.Response | None = None
        self._sse_client: Any = None
        self._closed = False

        # State management
        self._state = SSEConnectionState.DISCONNECTED
        self._reconnect_attempts = 0

        # Event handlers (matching Node.js API)
        self._event_handlers: dict[RealtimeEventType, list[EventHandler]] = {}
        self._all_events_handlers: list[GenericEventHandler] = []
        self._state_change_handlers: list[StateChangeHandler] = []
        self._lock = threading.Lock()

    @property
    def state(self) -> SSEConnectionState:
        """Get current connection state."""
        return self._state

    def get_state(self) -> SSEConnectionState:
        """Get current connection state (alias)."""
        return self._state

    # ─────────────────────────────────────────────────────────────────────────
    # Event Handlers (matching Node.js API)
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
            >>> @sse.on("job.completed")
            ... def on_completed(data):
            ...     print(f"Job completed: {data}")

        Example (direct):
            >>> def handler(data):
            ...     print(data)
            >>> unsubscribe = sse.on("job.created", handler)
            >>> unsubscribe()  # Remove listener
        """

        def decorator(fn: EventHandler) -> EventHandler:
            with self._lock:
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
        with self._lock:
            if event_type in self._event_handlers:
                with contextlib.suppress(ValueError):
                    self._event_handlers[event_type].remove(handler)

    def on_event(self, handler: GenericEventHandler) -> Callable[[], None]:
        """
        Add a listener for all events.

        Returns:
            Unsubscribe function

        Example:
            >>> unsubscribe = sse.on_event(lambda e: print(e.type))
            >>> unsubscribe()  # Remove listener
        """
        with self._lock:
            self._all_events_handlers.append(handler)
        return lambda: self._remove_all_events_handler(handler)

    def _remove_all_events_handler(self, handler: GenericEventHandler) -> None:
        """Remove all-events handler."""
        with self._lock:
            with contextlib.suppress(ValueError):
                self._all_events_handlers.remove(handler)

    def on_state_change(
        self, handler: StateChangeHandler | None = None
    ) -> Callable[..., Any]:
        """
        Add a listener for connection state changes.

        Can be used as a decorator or called directly.

        Returns:
            Unsubscribe function (when called directly) or decorator

        Example:
            >>> @sse.on_state_change
            ... def on_state(state):
            ...     print(f"State: {state}")
        """

        def decorator(fn: StateChangeHandler) -> StateChangeHandler:
            with self._lock:
                self._state_change_handlers.append(fn)
            return fn

        if handler is not None:
            decorator(handler)
            return lambda: self._remove_state_change_handler(handler)
        return decorator

    def _remove_state_change_handler(self, handler: StateChangeHandler) -> None:
        """Remove state change handler."""
        with self._lock:
            with contextlib.suppress(ValueError):
                self._state_change_handlers.remove(handler)

    def _set_state(self, state: SSEConnectionState) -> None:
        """Update connection state and notify handlers."""
        if self._state != state:
            self._state = state
            for handler in list(self._state_change_handlers):
                with contextlib.suppress(Exception):
                    handler(state)

    def _emit_event(self, event: RealtimeEvent) -> None:
        """Emit event to handlers."""
        # Specific handlers
        with self._lock:
            handlers = list(self._event_handlers.get(event.type, []))
            all_handlers = list(self._all_events_handlers)

        for event_handler in handlers:
            with contextlib.suppress(Exception):
                event_handler(event.data)

        for generic_handler in all_handlers:
            with contextlib.suppress(Exception):
                generic_handler(event)

    # ─────────────────────────────────────────────────────────────────────────
    # Connection Management
    # ─────────────────────────────────────────────────────────────────────────

    def _build_url(self) -> str:
        """Build SSE endpoint URL."""
        if self._job_id:
            return f"{self._base_url}/api/v1/events/jobs/{self._job_id}"
        if self._queue:
            return f"{self._base_url}/api/v1/events/queues/{self._queue}"
        return f"{self._base_url}/api/v1/events"

    def connect(self) -> None:
        """Connect to SSE stream."""
        if self._state == SSEConnectionState.CONNECTED:
            return

        self._set_state(SSEConnectionState.CONNECTING)

        url = self._build_url()

        try:
            self._client = httpx.Client()
            self._response = self._client.stream(
                "GET",
                url,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Accept": "text/event-stream",
                },
            ).__enter__()

            self._sse_client = sseclient.SSEClient(self._response.iter_lines())  # type: ignore[arg-type]
            self._set_state(SSEConnectionState.CONNECTED)
            self._reconnect_attempts = 0
            self._closed = False
        except Exception:
            self._set_state(SSEConnectionState.DISCONNECTED)
            raise

    def reconnect(
        self,
        *,
        queue: str | None = None,
        job_id: str | None = None,
    ) -> None:
        """
        Reconnect to the SSE stream, optionally with a new filter.

        Args:
            queue: Optional new queue filter
            job_id: Optional new job_id filter
        """
        self.close()

        # Update filter if provided
        if queue is not None:
            self._queue = queue
        if job_id is not None:
            self._job_id = job_id

        self.connect()

    def events(self) -> Generator[RealtimeEvent, None, None]:
        """
        Generator that yields events from the SSE stream.

        Example:
            >>> for event in sse.events():
            ...     print(event)
        """
        if not self._sse_client:
            self.connect()

        try:
            for event in self._sse_client.events():
                if self._closed:
                    break

                if event.data:
                    parsed = self._parse_event(event.event, event.data)
                    if parsed:
                        self._emit_event(parsed)
                        yield parsed
        except Exception:
            if not self._closed:
                raise

    def _parse_event(self, event_type: str, data: str) -> RealtimeEvent | None:
        """Parse SSE event to RealtimeEvent."""
        try:
            event_data = json.loads(data)
            return RealtimeEvent.from_server_event(event_type, event_data)
        except json.JSONDecodeError:
            return None

    def close(self) -> None:
        """Close the SSE connection."""
        self._closed = True

        if self._response:
            with contextlib.suppress(Exception):
                self._response.close()
            self._response = None

        if self._client:
            with contextlib.suppress(Exception):
                self._client.close()
            self._client = None

        self._sse_client = None
        self._set_state(SSEConnectionState.DISCONNECTED)

    def __enter__(self) -> SSEClient:
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class AsyncSSEClient:
    """
    Async Server-Sent Events client for real-time events.

    Note: Requires the 'realtime' extra: pip install spooled[realtime]

    Example:
        >>> async with AsyncSSEClient(base_url="...", token="...") as sse:
        ...     async for event in sse.events():
        ...         print(f"Event: {event.type}")
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        queue: str | None = None,
        job_id: str | None = None,
        auto_reconnect: bool = True,
        max_reconnect_attempts: int = 10,
        reconnect_delay: float = 1.0,
    ) -> None:
        """
        Initialize async SSE client.

        Args:
            base_url: Base API URL
            token: JWT token for authentication
            queue: Optional queue name to filter events
            job_id: Optional job ID to filter events
            auto_reconnect: Whether to auto-reconnect on disconnect
            max_reconnect_attempts: Maximum reconnection attempts
            reconnect_delay: Base delay between reconnection attempts
        """
        self._base_url = base_url
        self._token = token
        self._queue = queue
        self._job_id = job_id
        self._auto_reconnect = auto_reconnect
        self._max_reconnect_attempts = max_reconnect_attempts
        self._reconnect_delay = reconnect_delay

        self._client: httpx.AsyncClient | None = None
        self._response: httpx.Response | None = None
        self._closed = False

        # State management
        self._state = SSEConnectionState.DISCONNECTED
        self._reconnect_attempts = 0

        # Event handlers (matching Node.js API)
        self._event_handlers: dict[RealtimeEventType, list[EventHandler]] = {}
        self._all_events_handlers: list[GenericEventHandler] = []
        self._state_change_handlers: list[StateChangeHandler] = []

    @property
    def state(self) -> SSEConnectionState:
        """Get current connection state."""
        return self._state

    def get_state(self) -> SSEConnectionState:
        """Get current connection state (alias)."""
        return self._state

    # ─────────────────────────────────────────────────────────────────────────
    # Event Handlers (matching Node.js API)
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
            >>> @sse.on("job.completed")
            ... async def on_completed(data):
            ...     print(f"Job completed: {data}")

        Example (direct):
            >>> async def handler(data):
            ...     print(data)
            >>> unsubscribe = sse.on("job.created", handler)
            >>> unsubscribe()  # Remove listener
        """

        def decorator(fn: EventHandler) -> EventHandler:
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = []
            self._event_handlers[event_type].append(fn)
            return fn

        if handler is not None:
            decorator(handler)
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
            >>> unsubscribe = sse.on_event(lambda e: print(e.type))
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
            Unsubscribe function (when called directly) or decorator
        """

        def decorator(fn: StateChangeHandler) -> StateChangeHandler:
            self._state_change_handlers.append(fn)
            return fn

        if handler is not None:
            decorator(handler)
            return lambda: self._state_change_handlers.remove(handler)
        return decorator

    def _set_state(self, state: SSEConnectionState) -> None:
        """Update connection state and notify handlers."""
        if self._state != state:
            self._state = state
            for handler in list(self._state_change_handlers):
                with contextlib.suppress(Exception):
                    handler(state)

    def _emit_event(self, event: RealtimeEvent) -> None:
        """Emit event to handlers."""
        handlers = list(self._event_handlers.get(event.type, []))
        all_handlers = list(self._all_events_handlers)

        for event_handler in handlers:
            with contextlib.suppress(Exception):
                event_handler(event.data)

        for generic_handler in all_handlers:
            with contextlib.suppress(Exception):
                generic_handler(event)

    # ─────────────────────────────────────────────────────────────────────────
    # Connection Management
    # ─────────────────────────────────────────────────────────────────────────

    def _build_url(self) -> str:
        """Build SSE endpoint URL."""
        if self._job_id:
            return f"{self._base_url}/api/v1/events/jobs/{self._job_id}"
        if self._queue:
            return f"{self._base_url}/api/v1/events/queues/{self._queue}"
        return f"{self._base_url}/api/v1/events"

    async def connect(self) -> None:
        """Connect to SSE stream."""
        if self._state == SSEConnectionState.CONNECTED:
            return

        self._set_state(SSEConnectionState.CONNECTING)
        url = self._build_url()

        try:
            self._client = httpx.AsyncClient()
            self._response = await self._client.stream(
                "GET",
                url,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Accept": "text/event-stream",
                },
            ).__aenter__()
            self._set_state(SSEConnectionState.CONNECTED)
            self._reconnect_attempts = 0
            self._closed = False
        except Exception:
            self._set_state(SSEConnectionState.DISCONNECTED)
            raise

    async def reconnect(
        self,
        *,
        queue: str | None = None,
        job_id: str | None = None,
    ) -> None:
        """
        Reconnect to the SSE stream, optionally with a new filter.

        Args:
            queue: Optional new queue filter
            job_id: Optional new job_id filter
        """
        await self.close()

        if queue is not None:
            self._queue = queue
        if job_id is not None:
            self._job_id = job_id

        await self.connect()

    async def events(self) -> AsyncGenerator[RealtimeEvent, None]:
        """
        Async generator that yields events from the SSE stream.

        Example:
            >>> async for event in sse.events():
            ...     print(event)
        """
        if not self._response:
            await self.connect()

        try:
            current_event = ""
            current_data = ""

            assert self._response is not None
            async for line in self._response.aiter_lines():
                if self._closed:
                    break

                if line.startswith("event:"):
                    current_event = line[6:].strip()
                elif line.startswith("data:"):
                    current_data = line[5:].strip()
                elif line == "" and current_data:
                    parsed = self._parse_event(current_event, current_data)
                    if parsed:
                        self._emit_event(parsed)
                        yield parsed
                    current_event = ""
                    current_data = ""
        except Exception:
            if not self._closed:
                raise

    def _parse_event(self, event_type: str, data: str) -> RealtimeEvent | None:
        """Parse SSE event to RealtimeEvent."""
        try:
            event_data = json.loads(data)
            return RealtimeEvent.from_server_event(event_type or "message", event_data)
        except json.JSONDecodeError:
            return None

    async def close(self) -> None:
        """Close the SSE connection."""
        self._closed = True

        if self._response:
            with contextlib.suppress(Exception):
                await self._response.aclose()
            self._response = None

        if self._client:
            with contextlib.suppress(Exception):
                await self._client.aclose()
            self._client = None

        self._set_state(SSEConnectionState.DISCONNECTED)

    async def __aenter__(self) -> AsyncSSEClient:
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
