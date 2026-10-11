"""SSE clients: read timeout, HTTP status handling, retry budget, clean stream end.

SDKNP-03: the SSE clients used httpx's default 5 s read timeout, so a quiet stream
reconnected every 5 s and lost the events published in the gap.
SDKNP-04: the response status was never checked and the retry counter was reset on
every "successful" connect, so a revoked token reconnected forever without an error;
the unified SSE client went silently dead when the server ended the stream.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

import httpx
import pytest

import spooled.realtime.sse as sse_module
from spooled.errors import AuthenticationError, AuthorizationError, ServerError, SpooledError
from spooled.realtime.sse import SSE_TIMEOUT, AsyncSSEClient, SSEClient, SSEConnectionState
from spooled.realtime.unified import (
    ConnectionState,
    SpooledRealtime,
    SpooledRealtimeOptions,
    SubscriptionFilter,
)

if sse_module.sseclient is None:  # pragma: no cover - optional extra
    pytest.skip("sseclient-py not installed", allow_module_level=True)

BASE = "https://api.example.test"


def _event(name: str, data: dict[str, Any]) -> bytes:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n".encode()


def created(job_id: str = "job_1") -> bytes:
    return _event(
        "job.created",
        {"type": "JobCreated", "data": {"job_id": job_id, "queue_name": "orders", "priority": 0}},
    )


def status(new_status: str, job_id: str = "job_1") -> bytes:
    return _event(
        "job.status",
        {
            "type": "JobStatusChange",
            "data": {
                "job_id": job_id,
                "queue_name": "orders",
                "old_status": "",
                "new_status": new_status,
            },
        },
    )


def stream(body: bytes) -> httpx.Response:
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body)


def rejected(code: int = 401) -> httpx.Response:
    return httpx.Response(code, json={"code": "invalid_token", "message": "Token expired"})


class Server:
    """Scripted SSE server: one response per request, the last repeats."""

    def __init__(self, *responses: httpx.Response | Callable[[], httpx.Response]) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        index = min(len(self.requests), len(self.responses)) - 1
        response = self.responses[index]
        if callable(response):
            return response()
        # Each request needs its own response object (streams are single-use).
        return httpx.Response(
            response.status_code, headers=response.headers, content=response.read()
        )


@pytest.fixture
def sync_http(monkeypatch: pytest.MonkeyPatch) -> Callable[[Server], dict[str, Any]]:
    real = httpx.Client

    def install(server: Server) -> dict[str, Any]:
        seen: dict[str, Any] = {}

        def factory(*_args: Any, **kwargs: Any) -> httpx.Client:
            seen["timeout"] = kwargs.get("timeout")
            return real(transport=httpx.MockTransport(server))

        monkeypatch.setattr(httpx, "Client", factory)
        return seen

    return install


@pytest.fixture
def async_http(monkeypatch: pytest.MonkeyPatch) -> Callable[[Server], dict[str, Any]]:
    real = httpx.AsyncClient

    def install(server: Server) -> dict[str, Any]:
        seen: dict[str, Any] = {}

        def factory(*_args: Any, **kwargs: Any) -> httpx.AsyncClient:
            seen["timeout"] = kwargs.get("timeout")
            return real(transport=httpx.MockTransport(server))

        monkeypatch.setattr(httpx, "AsyncClient", factory)
        return seen

    return install


def _sse(**kwargs: Any) -> SSEClient:
    options: dict[str, Any] = {"reconnect_delay": 0.001, "max_reconnect_attempts": 3}
    options.update(kwargs)
    return SSEClient(base_url=BASE, token="t", **options)


def _async_sse(**kwargs: Any) -> AsyncSSEClient:
    options: dict[str, Any] = {"reconnect_delay": 0.001, "max_reconnect_attempts": 3}
    options.update(kwargs)
    return AsyncSSEClient(base_url=BASE, token="t", **options)


# ─────────────────────────────────────────────────────────────────────────────
# SDKNP-03: read timeout
# ─────────────────────────────────────────────────────────────────────────────


class TestStreamTimeout:
    def test_constant_is_not_the_httpx_default(self) -> None:
        assert SSE_TIMEOUT.read is not None
        assert SSE_TIMEOUT.read >= 45.0  # > 3 keep-alives (15 s); httpx's default is 5 s
        assert SSE_TIMEOUT.connect == 10.0

    def test_sync_client_passes_it(self, sync_http: Callable[[Server], dict[str, Any]]) -> None:
        seen = sync_http(Server(stream(created())))
        client = _sse(auto_reconnect=False)
        client.connect()
        client.close()
        assert seen["timeout"] is SSE_TIMEOUT

    @pytest.mark.asyncio
    async def test_async_client_passes_it(
        self, async_http: Callable[[Server], dict[str, Any]]
    ) -> None:
        seen = async_http(Server(stream(created())))
        client = _async_sse(auto_reconnect=False)
        await client.connect()
        await client.close()
        assert seen["timeout"] is SSE_TIMEOUT

    def test_unified_client_passes_it(self, sync_http: Callable[[Server], dict[str, Any]]) -> None:
        seen = sync_http(Server(stream(b": connected\n\n")))
        realtime = SpooledRealtime(
            SpooledRealtimeOptions(base_url=BASE, token="t", type="sse", auto_reconnect=False)
        )
        realtime.connect()
        realtime.disconnect()
        assert seen["timeout"] is SSE_TIMEOUT


# ─────────────────────────────────────────────────────────────────────────────
# SDKNP-04: HTTP status, retry budget, stream end
# ─────────────────────────────────────────────────────────────────────────────


class TestSyncSseStatus:
    @pytest.mark.parametrize(
        ("code", "error"), [(401, AuthenticationError), (403, AuthorizationError)]
    )
    def test_rejected_token_raises_a_typed_error_and_stops(
        self,
        sync_http: Callable[[Server], dict[str, Any]],
        code: int,
        error: type[SpooledError],
    ) -> None:
        server = Server(rejected(code))
        sync_http(server)
        client = _sse()
        with pytest.raises(error) as raised:
            list(client.events())
        assert raised.value.status_code == code
        assert raised.value.message == "Token expired"
        assert len(server.requests) == 1  # no reconnect loop
        assert client.state == SSEConnectionState.DISCONNECTED

    def test_rejection_after_a_drop_stops_instead_of_reconnecting(
        self, sync_http: Callable[[Server], dict[str, Any]]
    ) -> None:
        server = Server(stream(created()), rejected(401))
        sync_http(server)
        client = _sse()
        received = []
        with pytest.raises(AuthenticationError):
            for event in client.events():
                received.append(event)
        assert len(received) == 1
        assert len(server.requests) == 2

    def test_failed_connects_use_up_the_retry_budget(
        self, sync_http: Callable[[Server], dict[str, Any]]
    ) -> None:
        # A 503 used to count as a successful connect and reset the counter, so
        # this loop never ended.
        server = Server(stream(created()), httpx.Response(503, json={"message": "down"}))
        sync_http(server)
        client = _sse(max_reconnect_attempts=3)
        received = []
        with pytest.raises(ServerError):
            for event in client.events():
                received.append(event)
        assert len(received) == 1
        assert len(server.requests) == 1 + 3

    def test_streams_that_open_but_deliver_nothing_run_out_of_attempts(
        self, sync_http: Callable[[Server], dict[str, Any]]
    ) -> None:
        # A connect that returns 200 and closes at once proves nothing: counting it
        # as a success used to make this reconnect forever.
        server = Server(stream(b": connected\n\n"))
        sync_http(server)
        events = list(_sse(max_reconnect_attempts=3).events())
        assert events == []
        assert len(server.requests) == 1 + 3

    def test_retry_budget_is_restored_by_a_delivered_event(
        self, sync_http: Callable[[Server], dict[str, Any]]
    ) -> None:
        # One attempt only, but every stream delivers an event before it ends.
        server = Server(*[stream(created(f"job_{i}")) for i in range(4)], rejected(401))
        sync_http(server)
        client = _sse(max_reconnect_attempts=1)
        received = []
        with pytest.raises(AuthenticationError):
            for event in client.events():
                received.append(event)
        assert len(received) == 4

    def test_job_stream_ends_after_the_terminal_status(
        self, sync_http: Callable[[Server], dict[str, Any]]
    ) -> None:
        server = Server(stream(status("processing") + status("completed")))
        sync_http(server)
        client = _sse(job_id="job_1")
        events = list(client.events())
        # The server closes the stream after the terminal status; reconnecting
        # would replay it once per reconnect forever.
        assert [e.data["new_status"] for e in events] == ["processing", "completed"]
        assert len(server.requests) == 1
        assert client.state == SSEConnectionState.DISCONNECTED

    def test_job_stream_reconnects_when_not_terminal(
        self, sync_http: Callable[[Server], dict[str, Any]]
    ) -> None:
        server = Server(stream(status("processing")), stream(status("completed")))
        sync_http(server)
        events = list(_sse(job_id="job_1").events())
        assert [e.data["new_status"] for e in events] == ["processing", "completed"]
        assert len(server.requests) == 2

    def test_error_event_ends_a_job_stream(
        self, sync_http: Callable[[Server], dict[str, Any]]
    ) -> None:
        body = _event("error", {"type": "Error", "data": {"message": "Job not found"}})
        server = Server(stream(body))
        sync_http(server)
        events = list(_sse(job_id="job_1").events())
        assert [e.type for e in events] == ["error"]
        assert len(server.requests) == 1

    def test_terminal_status_does_not_end_an_org_stream(
        self, sync_http: Callable[[Server], dict[str, Any]]
    ) -> None:
        server = Server(
            stream(status("completed")), stream(status("completed", "job_2")), rejected()
        )
        sync_http(server)
        received = []
        with pytest.raises(AuthenticationError):
            for event in _sse().events():
                received.append(event)
        assert len(received) == 2  # org-wide stream keeps going across reconnects


class TestAsyncSseStatus:
    @pytest.mark.asyncio
    async def test_rejected_token_raises_a_typed_error_and_stops(
        self, async_http: Callable[[Server], dict[str, Any]]
    ) -> None:
        server = Server(rejected(401))
        async_http(server)
        client = _async_sse()
        with pytest.raises(AuthenticationError) as raised:
            async for _ in client.events():
                pass
        assert raised.value.message == "Token expired"
        assert len(server.requests) == 1
        assert client.state == SSEConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_failed_connects_use_up_the_retry_budget(
        self, async_http: Callable[[Server], dict[str, Any]]
    ) -> None:
        server = Server(stream(created() + b"\n"), httpx.Response(503, json={"message": "down"}))
        async_http(server)
        client = _async_sse(max_reconnect_attempts=3)
        received = []
        with pytest.raises(ServerError):
            async for event in client.events():
                received.append(event)
        assert len(received) == 1
        assert len(server.requests) == 1 + 3

    @pytest.mark.asyncio
    async def test_streams_that_open_but_deliver_nothing_run_out_of_attempts(
        self, async_http: Callable[[Server], dict[str, Any]]
    ) -> None:
        server = Server(stream(b": connected\n\n"))
        async_http(server)
        events = [event async for event in _async_sse(max_reconnect_attempts=3).events()]
        assert events == []
        assert len(server.requests) == 1 + 3

    @pytest.mark.asyncio
    async def test_retry_budget_is_restored_by_a_delivered_event(
        self, async_http: Callable[[Server], dict[str, Any]]
    ) -> None:
        server = Server(*[stream(created(f"job_{i}") + b"\n") for i in range(4)], rejected(401))
        async_http(server)
        client = _async_sse(max_reconnect_attempts=1)
        received = []
        with pytest.raises(AuthenticationError):
            async for event in client.events():
                received.append(event)
        assert len(received) == 4

    @pytest.mark.asyncio
    async def test_job_stream_ends_after_the_terminal_status(
        self, async_http: Callable[[Server], dict[str, Any]]
    ) -> None:
        server = Server(stream(status("completed") + b"\n"))
        async_http(server)
        client = _async_sse(job_id="job_1")
        events = [event async for event in client.events()]
        assert [e.data["new_status"] for e in events] == ["completed"]
        assert len(server.requests) == 1


# ─────────────────────────────────────────────────────────────────────────────
# SDKNP-04: unified SSE client
# ─────────────────────────────────────────────────────────────────────────────


def _unified(**kwargs: Any) -> SpooledRealtime:
    options: dict[str, Any] = {
        "base_url": BASE,
        "token": "t",
        "type": "sse",
        "reconnect_delay": 0.01,
        "max_reconnect_delay": 0.02,
        "max_reconnect_attempts": 3,
    }
    options.update(kwargs)
    return SpooledRealtime(SpooledRealtimeOptions(**options))


def _wait_for(predicate: Callable[[], bool], timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not reached in time")


class TestUnifiedSse:
    def test_rejected_token_raises_on_connect(
        self, sync_http: Callable[[Server], dict[str, Any]]
    ) -> None:
        server = Server(rejected(401))
        sync_http(server)
        realtime = _unified()
        with pytest.raises(AuthenticationError):
            realtime.connect()
        assert realtime.state == ConnectionState.DISCONNECTED
        assert len(server.requests) == 1

    def test_reconnects_after_the_server_ends_the_stream_cleanly(
        self, sync_http: Callable[[Server], dict[str, Any]]
    ) -> None:
        # The server caps a stream at 30 minutes and closes it; the client used to
        # stay "connected" with a dead thread and deliver nothing more.
        server = Server(
            stream(created("job_1")), stream(created("job_2")), stream(created("job_3"))
        )
        sync_http(server)
        realtime = _unified()
        seen: list[str] = []
        realtime.on("job.created", lambda data: seen.append(data["job_id"]))
        realtime.connect()
        _wait_for(lambda: len(seen) >= 3)
        realtime.disconnect()
        assert seen[:3] == ["job_1", "job_2", "job_3"]
        assert len(server.requests) >= 3

    def test_gives_up_on_a_rejected_token_during_reconnect(
        self, sync_http: Callable[[Server], dict[str, Any]]
    ) -> None:
        server = Server(stream(created()), rejected(401))
        sync_http(server)
        realtime = _unified()
        errors: list[dict[str, Any]] = []
        realtime.on("error", errors.append)
        realtime.connect()
        _wait_for(lambda: realtime.last_error is not None)
        assert isinstance(realtime.last_error, AuthenticationError)
        assert realtime.state == ConnectionState.DISCONNECTED
        assert errors and errors[0]["status_code"] == 401
        time.sleep(0.2)
        assert len(server.requests) == 2  # no further attempts
        realtime.disconnect()

    def test_streams_that_close_without_events_run_out_of_attempts(
        self, sync_http: Callable[[Server], dict[str, Any]]
    ) -> None:
        # connect() used to reset the counter, so this reconnected forever.
        server = Server(stream(b": connected\n\n"))
        sync_http(server)
        realtime = _unified(max_reconnect_attempts=3)
        realtime.connect()
        _wait_for(lambda: realtime.state == ConnectionState.DISCONNECTED)
        assert len(server.requests) == 1 + 3
        realtime.disconnect()

    def test_job_stream_is_not_reconnected_after_the_terminal_status(
        self, sync_http: Callable[[Server], dict[str, Any]]
    ) -> None:
        server = Server(stream(status("completed")))
        sync_http(server)
        realtime = _unified()
        statuses: list[str] = []
        realtime.on("job.status_changed", lambda data: statuses.append(data["new_status"]))
        realtime.subscribe(SubscriptionFilter(job_id="job_1"))
        realtime.connect()
        _wait_for(lambda: realtime.state == ConnectionState.DISCONNECTED)
        time.sleep(0.2)
        assert statuses == ["completed"]
        assert len(server.requests) == 1
        realtime.disconnect()
