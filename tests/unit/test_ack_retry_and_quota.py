"""Retried worker acks, plan-limit (QUOTA_EXCEEDED) handling, 422 mapping, token refresh.

SDKNP-05: ``complete`` / ``fail`` / job ``heartbeat`` / worker ``heartbeat`` were POSTs,
so a single 502 or timeout was never retried and the job ran twice.
SDKNP-06: a 429 ``QUOTA_EXCEEDED`` (no ``Retry-After``) was retried with 30 s sleeps
and tripped the circuit breaker for all traffic, acks included.
SDKNP-07: with a refresh token, only one of N concurrent 401s recovered.
SDKNP-14: 422 (missing/mistyped field) was not a ``ValidationError``.
"""

from __future__ import annotations

import asyncio
import threading
import time

import httpx
import pytest
import respx

from spooled import AsyncSpooledClient, SpooledClient
from spooled.config import CircuitBreakerConfig, RetryConfig
from spooled.errors import (
    AuthenticationError,
    QuotaExceededError,
    RateLimitError,
    ServerError,
    SpooledError,
    ValidationError,
    create_error_from_response,
)

BASE_URL = "http://localhost:8080"
API = f"{BASE_URL}/api/v1"
API_KEY = "sp_test_xxxxxxxxxxxxxxxxxxxx"
FAST_RETRY = RetryConfig(max_retries=3, base_delay=0.001, max_delay=0.005, jitter=False)

COMPLETE = {"worker_id": "w1", "lease_id": "l1", "result": {"ok": True}}
FAIL = {"worker_id": "w1", "lease_id": "l1", "error": "boom"}
BEAT = {"worker_id": "w1", "lease_id": "l1"}

QUOTA_BODY = {
    "error": "limit_exceeded",
    "code": "QUOTA_EXCEEDED",
    "message": "Daily job limit reached",
    "resource": "daily_jobs",
    "current": 1000,
    "limit": 1000,
    "plan": "free",
    "upgrade_to": "starter",
}


def _client(**kwargs: object) -> SpooledClient:
    return SpooledClient(api_key=API_KEY, base_url=BASE_URL, retry=FAST_RETRY, **kwargs)  # type: ignore[arg-type]


class TestAckRetries:
    """Lease-fenced acks are retried on network errors, timeouts and 5xx."""

    @respx.mock
    @pytest.mark.parametrize(
        ("call", "path", "ok_json"),
        [
            (lambda c: c.jobs.complete("j1", COMPLETE), "/jobs/j1/complete", {"success": True}),
            (lambda c: c.jobs.fail("j1", FAIL), "/jobs/j1/fail", {"success": True}),
            (lambda c: c.jobs.heartbeat("j1", BEAT), "/jobs/j1/heartbeat", {"success": True}),
            (
                lambda c: c.workers.heartbeat("w1", {"current_jobs": 1, "status": "healthy"}),
                "/workers/w1/heartbeat",
                {},
            ),
        ],
    )
    def test_ack_survives_a_502(self, call: object, path: str, ok_json: dict[str, object]) -> None:
        route = respx.post(f"{API}{path}").mock(
            side_effect=[
                httpx.Response(502, json={"message": "bad gateway"}),
                httpx.Response(502, json={"message": "bad gateway"}),
                httpx.Response(200, json=ok_json),
            ]
        )
        with _client() as client:
            call(client)  # type: ignore[operator]
        assert route.call_count == 3

    @respx.mock
    def test_ack_survives_a_timeout_and_a_connection_error(self) -> None:
        route = respx.post(f"{API}/jobs/j1/complete").mock(
            side_effect=[
                httpx.ReadTimeout("slow"),
                httpx.ConnectError("reset"),
                httpx.Response(200, json={"success": True}),
            ]
        )
        with _client() as client:
            assert client.jobs.complete("j1", COMPLETE).success is True
        assert route.call_count == 3

    @respx.mock
    def test_ack_retries_408(self) -> None:
        route = respx.post(f"{API}/jobs/j1/complete").mock(
            side_effect=[
                httpx.Response(408, json={"message": "request timeout"}),
                httpx.Response(200, json={"success": True}),
            ]
        )
        with _client() as client:
            client.jobs.complete("j1", COMPLETE)
        assert route.call_count == 2

    @respx.mock
    @pytest.mark.parametrize("status", [400, 401, 403, 404, 409])
    def test_ack_is_not_retried_on_other_4xx(self, status: int) -> None:
        route = respx.post(f"{API}/jobs/j1/complete").mock(
            return_value=httpx.Response(status, json={"message": "no"})
        )
        with _client() as client, pytest.raises(SpooledError):
            client.jobs.complete("j1", COMPLETE)
        assert route.call_count == 1

    @respx.mock
    def test_ack_gives_up_after_the_bounded_retries(self) -> None:
        route = respx.post(f"{API}/jobs/j1/complete").mock(
            return_value=httpx.Response(502, json={})
        )
        with _client() as client, pytest.raises(ServerError):
            client.jobs.complete("j1", COMPLETE)
        assert route.call_count == 4  # 1 attempt + max_retries

    @respx.mock
    def test_job_creation_is_still_not_retried_on_502(self) -> None:
        route = respx.post(f"{API}/jobs").mock(return_value=httpx.Response(502, json={}))
        with _client() as client, pytest.raises(ServerError):
            client.jobs.create({"queue_name": "q", "payload": {}})
        assert route.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_ack_survives_a_502(self) -> None:
        route = respx.post(f"{API}/jobs/j1/complete").mock(
            side_effect=[
                httpx.Response(502, json={}),
                httpx.Response(200, json={"success": True}),
            ]
        )
        beat = respx.post(f"{API}/workers/w1/heartbeat").mock(
            side_effect=[httpx.ConnectError("reset"), httpx.Response(200, json={})]
        )
        async with AsyncSpooledClient(api_key=API_KEY, base_url=BASE_URL, retry=FAST_RETRY) as c:
            assert (await c.jobs.complete("j1", COMPLETE)).success is True
            await c.workers.heartbeat("w1", {"current_jobs": 0, "status": "healthy"})
        assert route.call_count == 2
        assert beat.call_count == 2


class TestQuotaExceeded:
    """A plan limit is not transient: no retries, no breaker."""

    def test_quota_body_maps_to_quota_error_with_details(self) -> None:
        error = create_error_from_response(429, QUOTA_BODY)
        assert isinstance(error, QuotaExceededError)
        assert isinstance(error, RateLimitError)  # existing handlers keep working
        assert error.status_code == 429
        assert error.code == "QUOTA_EXCEEDED"
        assert error.is_retryable() is False
        assert (error.resource, error.current, error.limit, error.plan, error.upgrade_to) == (
            "daily_jobs",
            1000,
            1000,
            "free",
            "starter",
        )

    def test_plan_limit_body_without_retry_after_is_quota_even_without_a_code(self) -> None:
        body = {"error": "limit_exceeded", "message": "cap", "resource": "queues", "limit": 3}
        assert isinstance(create_error_from_response(429, body), QuotaExceededError)

    def test_plain_rate_limit_stays_retryable(self) -> None:
        error = create_error_from_response(
            429,
            {"code": "RATE_LIMIT_EXCEEDED", "message": "slow down"},
            headers={"Retry-After": "2"},
        )
        assert type(error) is RateLimitError
        assert error.is_retryable() is True
        assert error.retry_after == 2

    def test_plan_limit_body_with_retry_after_is_a_rate_limit(self) -> None:
        error = create_error_from_response(
            429, {"error": "limit_exceeded", "message": "x"}, headers={"Retry-After": "5"}
        )
        assert type(error) is RateLimitError

    @respx.mock
    def test_quota_429_is_raised_at_once_without_sleeping(self) -> None:
        route = respx.post(f"{API}/jobs").mock(return_value=httpx.Response(429, json=QUOTA_BODY))
        # Default backoff (1 s base) would sleep 1+2+4 s if the 429 were retried.
        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            started = time.monotonic()
            with pytest.raises(QuotaExceededError) as raised:
                client.jobs.create({"queue_name": "q", "payload": {}})
            assert time.monotonic() - started < 0.5
        assert route.call_count == 1
        assert raised.value.plan == "free"

    @respx.mock
    def test_quota_errors_do_not_trip_the_breaker_or_block_acks(self) -> None:
        respx.post(f"{API}/jobs").mock(return_value=httpx.Response(429, json=QUOTA_BODY))
        complete = respx.post(f"{API}/jobs/j1/complete").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        with _client(circuit_breaker=CircuitBreakerConfig(failure_threshold=2)) as client:
            for _ in range(6):
                with pytest.raises(QuotaExceededError):
                    client.jobs.create({"queue_name": "q", "payload": {}})
            assert client.get_circuit_breaker_stats()["state"] == "CLOSED"
            assert client.jobs.complete("j1", COMPLETE).success is True
        assert complete.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_quota_429_is_raised_at_once(self) -> None:
        route = respx.post(f"{API}/jobs").mock(return_value=httpx.Response(429, json=QUOTA_BODY))
        async with AsyncSpooledClient(
            api_key=API_KEY,
            base_url=BASE_URL,
            circuit_breaker=CircuitBreakerConfig(failure_threshold=2),
        ) as client:
            for _ in range(4):
                with pytest.raises(QuotaExceededError):
                    await client.jobs.create({"queue_name": "q", "payload": {}})
            assert client.get_circuit_breaker_stats()["state"] == "CLOSED"
        assert route.call_count == 4  # one attempt per call, never retried


class TestValidationStatus:
    def test_422_maps_to_validation_error(self) -> None:
        body = {
            "code": "VALIDATION_ERROR",
            "message": "Validation failed",
            "details": [{"field": "queue_name", "message": "Field `queue_name` is required"}],
        }
        error = create_error_from_response(422, body, "req-1")
        assert isinstance(error, ValidationError)
        assert error.status_code == 422
        assert error.code == "VALIDATION_ERROR"
        assert error.request_id == "req-1"
        assert error.details == body["details"]  # the API sends a list

    def test_400_is_still_a_validation_error(self) -> None:
        error = create_error_from_response(400, {"code": "VALIDATION_ERROR", "message": "bad"})
        assert isinstance(error, ValidationError)
        assert error.status_code == 400

    @respx.mock
    def test_422_from_the_wire(self) -> None:
        respx.post(f"{API}/jobs").mock(
            return_value=httpx.Response(422, json={"code": "VALIDATION_ERROR", "message": "m"})
        )
        with _client() as client, pytest.raises(ValidationError) as raised:
            client.jobs.create({"queue_name": "q", "payload": {}})
        assert raised.value.status_code == 422


class TestSingleFlightRefresh:
    """Concurrent 401s share one refresh and every request recovers (SDKNP-07)."""

    CALLS = 5

    def _bearer_route(self) -> respx.Route:
        def respond(request: httpx.Request) -> httpx.Response:
            if request.headers["Authorization"] == "Bearer fresh":
                return httpx.Response(200, json=[])
            return httpx.Response(401, json={"code": "token_expired", "message": "expired"})

        return respx.get(f"{API}/jobs").mock(side_effect=respond)

    @respx.mock
    def test_threads(self) -> None:
        route = self._bearer_route()
        refreshes: list[int] = []
        client = SpooledClient(
            access_token="stale",
            refresh_token="refresh-token-1",
            base_url=BASE_URL,
            retry=FAST_RETRY,
        )

        def refresh() -> str:
            refreshes.append(1)
            time.sleep(0.15)  # long enough for the other threads' 401s to arrive
            client._http.set_auth_token("fresh")
            return "fresh"

        client._http.set_refresh_token_fn(refresh)
        barrier = threading.Barrier(self.CALLS)
        outcomes: list[object] = []

        def worker() -> None:
            barrier.wait()
            try:
                outcomes.append(client.jobs.list())
            except Exception as exc:
                outcomes.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(self.CALLS)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        client.close()

        assert outcomes == [[]] * self.CALLS, outcomes
        assert len(refreshes) == 1
        assert route.call_count == self.CALLS * 2  # one 401 + one replay each

    @respx.mock
    @pytest.mark.asyncio
    async def test_tasks(self) -> None:
        route = self._bearer_route()
        refreshes: list[int] = []
        client = AsyncSpooledClient(
            access_token="stale",
            refresh_token="refresh-token-1",
            base_url=BASE_URL,
            retry=FAST_RETRY,
        )

        async def refresh() -> str:
            refreshes.append(1)
            await asyncio.sleep(0.15)
            client._http.set_auth_token("fresh")
            return "fresh"

        client._http.set_refresh_token_fn(refresh)
        results = await asyncio.gather(
            *(client.jobs.list() for _ in range(self.CALLS)), return_exceptions=True
        )
        await client.close()

        assert results == [[]] * self.CALLS, results
        assert len(refreshes) == 1
        assert route.call_count == self.CALLS * 2

    @respx.mock
    def test_a_401_from_the_refresh_call_itself_does_not_recurse(self) -> None:
        respx.get(f"{API}/jobs").mock(return_value=httpx.Response(401, json={"message": "no"}))
        refresh_route = respx.post(f"{API}/auth/refresh").mock(
            return_value=httpx.Response(401, json={"message": "refresh token revoked"})
        )
        with SpooledClient(
            access_token="stale",
            refresh_token="refresh-token-1",
            base_url=BASE_URL,
            retry=FAST_RETRY,
        ) as client:
            with pytest.raises(AuthenticationError):
                client.jobs.list()
        assert refresh_route.call_count == 1
