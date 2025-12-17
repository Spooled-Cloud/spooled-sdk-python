"""
Server-Sent Events (SSE) client for real-time events.
"""

from __future__ import annotations

import json
from typing import Any, Generator

import httpx

from spooled.realtime.events import RealtimeEvent

# Optional sseclient import
try:
    import sseclient

    HAS_SSE = True
except ImportError:
    HAS_SSE = False
    sseclient = None  # type: ignore


class SSEClient:
    """
    Server-Sent Events client for real-time events.

    Note: Requires the 'realtime' extra: pip install spooled[realtime]

    Example:
        >>> # SSE for all events
        >>> sse = client.realtime.sse()
        >>>
        >>> # SSE for specific queue
        >>> sse = client.realtime.sse(queue="emails")
        >>>
        >>> # SSE for specific job
        >>> sse = client.realtime.sse(job_id="job_xxx")
        >>>
        >>> for event in sse.events():
        ...     print(f"Event: {event.type} - {event.data}")
        >>> sse.close()
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        queue: str | None = None,
        job_id: str | None = None,
    ) -> None:
        """
        Initialize SSE client.

        Args:
            base_url: Base API URL
            token: JWT token for authentication
            queue: Optional queue name to filter events
            job_id: Optional job ID to filter events
        """
        if not HAS_SSE:
            raise ImportError(
                "sseclient-py package required. Install with: pip install spooled[realtime]"
            )

        self._base_url = base_url
        self._token = token
        self._queue = queue
        self._job_id = job_id

        self._client: httpx.Client | None = None
        self._response: httpx.Response | None = None
        self._sse_client: Any = None
        self._closed = False

    def _build_url(self) -> str:
        """Build SSE endpoint URL."""
        if self._job_id:
            return f"{self._base_url}/api/v1/events/jobs/{self._job_id}"
        if self._queue:
            return f"{self._base_url}/api/v1/events/queues/{self._queue}"
        return f"{self._base_url}/api/v1/events"

    def connect(self) -> None:
        """Connect to SSE stream."""
        url = self._build_url()

        self._client = httpx.Client()
        self._response = self._client.stream(
            "GET",
            url,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "text/event-stream",
            },
        ).__enter__()

        self._sse_client = sseclient.SSEClient(self._response.iter_lines())

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
            try:
                self._response.close()
            except Exception:
                pass
            self._response = None

        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def __enter__(self) -> "SSEClient":
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class AsyncSSEClient:
    """
    Async Server-Sent Events client for real-time events.

    Note: Requires the 'realtime' extra: pip install spooled[realtime]

    Example:
        >>> async with client.realtime.sse(queue="emails") as sse:
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
    ) -> None:
        """
        Initialize async SSE client.

        Args:
            base_url: Base API URL
            token: JWT token for authentication
            queue: Optional queue name to filter events
            job_id: Optional job ID to filter events
        """
        self._base_url = base_url
        self._token = token
        self._queue = queue
        self._job_id = job_id

        self._client: httpx.AsyncClient | None = None
        self._response: httpx.Response | None = None
        self._closed = False

    def _build_url(self) -> str:
        """Build SSE endpoint URL."""
        if self._job_id:
            return f"{self._base_url}/api/v1/events/jobs/{self._job_id}"
        if self._queue:
            return f"{self._base_url}/api/v1/events/queues/{self._queue}"
        return f"{self._base_url}/api/v1/events"

    async def connect(self) -> None:
        """Connect to SSE stream."""
        url = self._build_url()

        self._client = httpx.AsyncClient()
        self._response = await self._client.stream(
            "GET",
            url,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "text/event-stream",
            },
        ).__aenter__()

    async def events(self):
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

            async for line in self._response.aiter_lines():
                if self._closed:
                    break

                if line.startswith("event:"):
                    current_event = line[6:].strip()
                elif line.startswith("data:"):
                    current_data = line[5:].strip()
                elif line == "" and current_data:
                    # Empty line signals end of event
                    parsed = self._parse_event(current_event, current_data)
                    if parsed:
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
            try:
                await self._response.aclose()
            except Exception:
                pass
            self._response = None

        if self._client:
            try:
                await self._client.aclose()
            except Exception:
                pass
            self._client = None

    async def __aenter__(self) -> "AsyncSSEClient":
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()


