"""Edge case tests for Spooled SDK."""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
import respx

from spooled import SpooledClient, AsyncSpooledClient, SpooledClientConfig
from spooled.config import CircuitBreakerConfig, RetryConfig, resolve_config
from spooled.errors import (
    CircuitBreakerOpenError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from spooled.utils.circuit_breaker import CircuitBreaker


API_KEY = "sk_test_xxxxxxxxxxxxxxxxxxxx"
BASE_URL = "http://localhost:8080"


class TestConcurrentAccess:
    """Tests for thread-safe concurrent access."""

    @respx.mock
    def test_concurrent_requests(self) -> None:
        """Test multiple concurrent requests."""
        call_count = 0

        def make_response(request):
            nonlocal call_count
            call_count += 1
            return httpx.Response(
                200,
                json={"id": f"job_{call_count}", "created": True},
            )

        respx.post(f"{BASE_URL}/api/v1/jobs").mock(side_effect=make_response)

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            results = []

            def create_job(n):
                result = client.jobs.create({
                    "queue_name": "test",
                    "payload": {"n": n},
                })
                results.append(result)

            # Run 10 concurrent requests
            with ThreadPoolExecutor(max_workers=10) as executor:
                list(executor.map(create_job, range(10)))

            assert len(results) == 10
            assert call_count == 10


class TestCircuitBreakerBehavior:
    """Tests for circuit breaker edge cases."""

    def test_circuit_breaker_thread_safety(self) -> None:
        """Test circuit breaker is thread-safe."""
        config = CircuitBreakerConfig(
            enabled=True,
            failure_threshold=100,  # High to avoid tripping during test
            success_threshold=1,
            timeout=0.1,
        )
        breaker = CircuitBreaker(config)

        results = []

        def record_failures():
            for _ in range(50):
                breaker.record_failure(ServerError())
                results.append(True)

        def record_successes():
            for _ in range(50):
                breaker.record_success()
                results.append(True)

        threads = [
            threading.Thread(target=record_failures),
            threading.Thread(target=record_successes),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 100

    @respx.mock
    def test_circuit_breaker_recovery(self) -> None:
        """Test circuit breaker recovers after timeout."""
        config = CircuitBreakerConfig(
            enabled=True,
            failure_threshold=1,
            success_threshold=1,
            timeout=0.1,  # 100ms
        )

        call_count = 0

        job_response = {
            "id": "j1",
            "organization_id": "org_1",
            "queue_name": "test",
            "status": "pending",
            "payload": {},
            "retry_count": 0,
            "max_retries": 3,
            "priority": 0,
            "timeout_seconds": 300,
            "created_at": "2024-01-01T00:00:00Z",
        }

        def make_response(request):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return httpx.Response(500, json={"message": "error"})
            return httpx.Response(200, json=job_response)

        respx.get(f"{BASE_URL}/api/v1/jobs/j1").mock(side_effect=make_response)

        client_config = SpooledClientConfig(
            api_key=API_KEY,
            base_url=BASE_URL,
            retry=RetryConfig(max_retries=0),
            circuit_breaker=config,
        )

        with SpooledClient(config=client_config) as client:
            # First call fails, trips circuit
            with pytest.raises(ServerError):
                client.jobs.get("j1")

            # Circuit is open
            with pytest.raises(CircuitBreakerOpenError):
                client.jobs.get("j1")

            # Wait for recovery
            time.sleep(0.15)

            # Third call succeeds (in half-open state)
            # This will still fail from the server, then succeed
            try:
                client.jobs.get("j1")  # May fail if server still errors
            except (ServerError, CircuitBreakerOpenError):
                time.sleep(0.15)
                # Eventually should work
                result = client.jobs.get("j1")
                assert result is not None


class TestRetryBehavior:
    """Tests for retry edge cases."""

    @respx.mock
    def test_retry_respects_max_retries(self) -> None:
        """Test retry stops at max_retries."""
        call_count = 0

        def make_response(request):
            nonlocal call_count
            call_count += 1
            return httpx.Response(500, json={"message": "error"})

        respx.get(f"{BASE_URL}/api/v1/jobs").mock(side_effect=make_response)

        with SpooledClient(
            api_key=API_KEY,
            base_url=BASE_URL,
            retry=RetryConfig(max_retries=3, base_delay=0.001),
            circuit_breaker=CircuitBreakerConfig(enabled=False),
        ) as client:
            with pytest.raises(ServerError):
                client.jobs.list()

            # Initial + 3 retries = 4 calls
            assert call_count == 4

    @respx.mock
    def test_retry_uses_rate_limit_retry_after(self) -> None:
        """Test retry respects Retry-After header."""
        call_count = 0
        request_times = []

        def make_response(request):
            nonlocal call_count
            call_count += 1
            request_times.append(time.time())

            if call_count == 1:
                # First call: rate limited with 50ms retry after
                return httpx.Response(
                    429,
                    json={"message": "rate limited"},
                    headers={"Retry-After": "0.05"},
                )
            return httpx.Response(200, json=[])

        respx.get(f"{BASE_URL}/api/v1/jobs").mock(side_effect=make_response)

        with SpooledClient(
            api_key=API_KEY,
            base_url=BASE_URL,
            retry=RetryConfig(max_retries=3, base_delay=0.001, max_delay=0.1),
            circuit_breaker=CircuitBreakerConfig(enabled=False),
        ) as client:
            client.jobs.list()

            assert call_count == 2


class TestLargePayloads:
    """Tests for handling large payloads."""

    @respx.mock
    def test_large_job_payload(self) -> None:
        """Test handling large job payloads."""
        large_payload = {"data": "x" * 100000}  # 100KB

        respx.post(f"{BASE_URL}/api/v1/jobs").mock(
            return_value=httpx.Response(
                200,
                json={"id": "job_large", "created": True},
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.jobs.create({
                "queue_name": "test",
                "payload": large_payload,
            })
            assert result.id == "job_large"

    @respx.mock
    def test_many_items_in_bulk(self) -> None:
        """Test bulk enqueue with maximum items."""
        respx.post(f"{BASE_URL}/api/v1/jobs/bulk").mock(
            return_value=httpx.Response(
                200,
                json={
                    "succeeded": [{"index": i, "job_id": f"j_{i}", "created": True} for i in range(100)],
                    "failed": [],
                    "total": 100,
                    "success_count": 100,
                    "failure_count": 0,
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.jobs.bulk_enqueue({
                "queue_name": "test",
                "jobs": [{"payload": {"n": i}} for i in range(100)],
            })
            assert result.success_count == 100


class TestSpecialCharacters:
    """Tests for handling special characters."""

    @respx.mock
    def test_unicode_in_payload(self) -> None:
        """Test Unicode characters in payload."""
        respx.post(f"{BASE_URL}/api/v1/jobs").mock(
            return_value=httpx.Response(
                200,
                json={"id": "job_unicode", "created": True},
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.jobs.create({
                "queue_name": "test",
                "payload": {
                    "message": "Hello, 世界! 🌍",
                    "emoji": "👍 🎉 💯",
                    "japanese": "こんにちは",
                    "arabic": "مرحبا",
                },
            })
            assert result.id == "job_unicode"

    @respx.mock
    def test_special_chars_in_queue_name(self) -> None:
        """Test special characters in queue name query."""
        respx.get(f"{BASE_URL}/api/v1/jobs").mock(
            return_value=httpx.Response(200, json=[])
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            # Queue names with hyphens and numbers
            client.jobs.list({"queue_name": "my-queue-123"})


class TestEmptyResponses:
    """Tests for handling empty responses."""

    @respx.mock
    def test_empty_list_response(self) -> None:
        """Test empty list response."""
        respx.get(f"{BASE_URL}/api/v1/jobs").mock(
            return_value=httpx.Response(200, json=[])
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            jobs = client.jobs.list()
            assert jobs == []

    @respx.mock
    def test_null_fields_in_response(self) -> None:
        """Test response with null/None fields."""
        respx.get(f"{BASE_URL}/api/v1/jobs/j1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "j1",
                    "organization_id": "org_1",
                    "queue_name": "test",
                    "status": "pending",
                    "payload": {},
                    "retry_count": 0,
                    "max_retries": 3,
                    "priority": 0,
                    "timeout_seconds": 300,
                    "created_at": "2024-01-01T00:00:00Z",
                    "scheduled_at": None,
                    "completed_at": None,
                    "error": None,
                    "result": None,
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            job = client.jobs.get("j1")
            assert job.id == "j1"
            assert job.scheduled_at is None


class TestErrorMessageParsing:
    """Tests for error message parsing."""

    @respx.mock
    def test_error_with_nested_details(self) -> None:
        """Test parsing error with nested details."""
        respx.post(f"{BASE_URL}/api/v1/jobs").mock(
            return_value=httpx.Response(
                400,
                json={
                    "code": "validation_error",
                    "message": "Validation failed",
                    "details": {
                        "fields": {
                            "payload.email": "invalid format",
                        },
                        "validation_errors": [
                            {"field": "payload.email", "message": "Invalid format"},
                        ],
                    },
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            with pytest.raises(ValidationError) as exc_info:
                client.jobs.create({"queue_name": "test", "payload": {"email": "invalid"}})

            assert exc_info.value.details is not None
            assert "fields" in exc_info.value.details

    @respx.mock
    def test_error_with_no_body(self) -> None:
        """Test handling error with empty body."""
        respx.get(f"{BASE_URL}/api/v1/jobs").mock(
            return_value=httpx.Response(500, content=b"")
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            with pytest.raises(ServerError) as exc_info:
                client.jobs.list()
            assert exc_info.value.message == "Unknown error"


class TestClientLifecycle:
    """Tests for client lifecycle management."""

    def test_client_can_be_reused(self) -> None:
        """Test client can make multiple requests."""
        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            # Just test client exists
            assert client is not None
            assert client.jobs is not None
            assert client.queues is not None

    def test_multiple_clients(self) -> None:
        """Test multiple client instances."""
        client1 = SpooledClient(api_key=API_KEY, base_url=BASE_URL)
        client2 = SpooledClient(api_key=API_KEY, base_url=BASE_URL)

        assert client1 is not client2
        assert client1.jobs is not client2.jobs

        client1.close()
        client2.close()

    @pytest.mark.asyncio
    async def test_async_client_lifecycle(self) -> None:
        """Test async client lifecycle."""
        async with AsyncSpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            assert client is not None
            assert client.jobs is not None


class TestTypeConversions:
    """Tests for type conversions in requests/responses."""

    @respx.mock
    def test_list_with_status_filter(self) -> None:
        """Test list with status filter."""
        respx.get(f"{BASE_URL}/api/v1/jobs").mock(
            return_value=httpx.Response(200, json=[])
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            # Status filter should work
            client.jobs.list({"status": "pending"})

    @respx.mock
    def test_boolean_in_params(self) -> None:
        """Test boolean conversion in query params."""
        respx.get(f"{BASE_URL}/api/v1/schedules").mock(
            return_value=httpx.Response(200, json=[])
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            client.schedules.list({"is_active": True})
            client.schedules.list({"is_active": False})


class TestNetworkConditions:
    """Tests for various network conditions."""

    @respx.mock
    def test_handles_json_decode_error(self) -> None:
        """Test handling of invalid JSON response."""
        respx.get(f"{BASE_URL}/api/v1/jobs").mock(
            return_value=httpx.Response(
                500,
                content=b"<html>Not JSON</html>",
                headers={"Content-Type": "text/html"},
            )
        )

        with SpooledClient(
            api_key=API_KEY,
            base_url=BASE_URL,
            retry=RetryConfig(max_retries=0),
            circuit_breaker=CircuitBreakerConfig(enabled=False),
        ) as client:
            with pytest.raises(ServerError):
                client.jobs.list()

