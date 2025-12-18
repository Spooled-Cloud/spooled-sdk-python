"""Unit tests for async HTTP client module."""

from __future__ import annotations

import httpx
import pytest
import respx

from spooled.config import (
    CircuitBreakerConfig,
    RetryConfig,
    SpooledClientConfig,
    resolve_config,
)
from spooled.errors import NotFoundError, ServerError
from spooled.utils.async_http import AsyncHttpClient, create_async_http_client
from spooled.utils.circuit_breaker import create_circuit_breaker


class TestAsyncHttpClientBasics:
    """Tests for AsyncHttpClient basic functionality."""

    BASE_URL = "http://localhost:8080"

    @pytest.fixture
    def http_client(self) -> AsyncHttpClient:
        """Create an async HTTP client for tests."""
        config = SpooledClientConfig(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url=self.BASE_URL,
            retry=RetryConfig(max_retries=0),
            circuit_breaker=CircuitBreakerConfig(enabled=False),
        )
        resolved = resolve_config(config)
        breaker = create_circuit_breaker(resolved.circuit_breaker)
        return AsyncHttpClient(resolved, breaker)

    def test_build_url(self, http_client: AsyncHttpClient) -> None:
        """Test URL building."""
        url = http_client._build_url("/jobs", None)
        assert url == f"{self.BASE_URL}/api/v1/jobs"

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Test async context manager."""
        config = SpooledClientConfig(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url=self.BASE_URL,
        )
        resolved = resolve_config(config)
        breaker = create_circuit_breaker(resolved.circuit_breaker)

        async with AsyncHttpClient(resolved, breaker) as client:
            assert client is not None


class TestAsyncHttpClientRequests:
    """Tests for AsyncHttpClient request methods."""

    BASE_URL = "http://localhost:8080"

    @pytest.fixture
    def http_client(self) -> AsyncHttpClient:
        """Create an async HTTP client for tests."""
        config = SpooledClientConfig(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url=self.BASE_URL,
            retry=RetryConfig(max_retries=0),
            circuit_breaker=CircuitBreakerConfig(enabled=False),
        )
        resolved = resolve_config(config)
        breaker = create_circuit_breaker(resolved.circuit_breaker)
        return AsyncHttpClient(resolved, breaker)

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_request(self, http_client: AsyncHttpClient) -> None:
        """Test async GET request."""
        respx.get(f"{self.BASE_URL}/api/v1/jobs/job_123").mock(
            return_value=httpx.Response(
                200,
                json={"id": "job_123", "status": "pending"},
            )
        )

        result = await http_client.get("/jobs/job_123")
        assert result["id"] == "job_123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_post_request(self, http_client: AsyncHttpClient) -> None:
        """Test async POST request."""
        respx.post(f"{self.BASE_URL}/api/v1/jobs").mock(
            return_value=httpx.Response(
                200,
                json={"id": "job_new", "created": True},
            )
        )

        result = await http_client.post("/jobs", {"queue_name": "test"})
        assert result["created"] is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_put_request(self, http_client: AsyncHttpClient) -> None:
        """Test async PUT request."""
        respx.put(f"{self.BASE_URL}/api/v1/queues/test/config").mock(
            return_value=httpx.Response(
                200,
                json={"queue_name": "test", "max_retries": 5},
            )
        )

        result = await http_client.put("/queues/test/config", {"max_retries": 5})
        assert result["max_retries"] == 5

    @pytest.mark.asyncio
    @respx.mock
    async def test_delete_request(self, http_client: AsyncHttpClient) -> None:
        """Test async DELETE request."""
        respx.delete(f"{self.BASE_URL}/api/v1/jobs/job_123").mock(
            return_value=httpx.Response(204)
        )

        result = await http_client.delete("/jobs/job_123")
        assert result is None


class TestAsyncHttpClientErrors:
    """Tests for AsyncHttpClient error handling."""

    BASE_URL = "http://localhost:8080"

    @pytest.fixture
    def http_client(self) -> AsyncHttpClient:
        """Create an async HTTP client for tests."""
        config = SpooledClientConfig(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url=self.BASE_URL,
            retry=RetryConfig(max_retries=0),
            circuit_breaker=CircuitBreakerConfig(enabled=False),
        )
        resolved = resolve_config(config)
        breaker = create_circuit_breaker(resolved.circuit_breaker)
        return AsyncHttpClient(resolved, breaker)

    @pytest.mark.asyncio
    @respx.mock
    async def test_404_not_found_error(self, http_client: AsyncHttpClient) -> None:
        """Test async 404 raises NotFoundError."""
        respx.get(f"{self.BASE_URL}/api/v1/jobs/nonexistent").mock(
            return_value=httpx.Response(
                404,
                json={"message": "Not found"},
            )
        )

        with pytest.raises(NotFoundError):
            await http_client.get("/jobs/nonexistent")

    @pytest.mark.asyncio
    @respx.mock
    async def test_500_server_error(self, http_client: AsyncHttpClient) -> None:
        """Test async 500 raises ServerError."""
        respx.get(f"{self.BASE_URL}/api/v1/jobs").mock(
            return_value=httpx.Response(
                500,
                json={"message": "Server error"},
            )
        )

        with pytest.raises(ServerError):
            await http_client.get("/jobs")


class TestCreateAsyncHttpClient:
    """Tests for create_async_http_client factory."""

    def test_creates_client(self) -> None:
        """Test factory creates async HTTP client."""
        config = SpooledClientConfig(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url="http://localhost:8080",
        )
        resolved = resolve_config(config)
        breaker = create_circuit_breaker(resolved.circuit_breaker)
        client = create_async_http_client(resolved, breaker)
        assert isinstance(client, AsyncHttpClient)
