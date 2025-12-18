"""Unit tests for HTTP client module."""

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
from spooled.errors import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from spooled.utils.circuit_breaker import create_circuit_breaker
from spooled.utils.http import HttpClient


class TestHttpClientBasics:
    """Tests for HttpClient basic functionality."""

    @pytest.fixture
    def http_client(self) -> HttpClient:
        """Create an HTTP client for tests."""
        config = SpooledClientConfig(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url="http://localhost:8080",
        )
        resolved = resolve_config(config)
        breaker = create_circuit_breaker(resolved.circuit_breaker)
        return HttpClient(resolved, breaker)

    def test_build_url_with_api_prefix(self, http_client: HttpClient) -> None:
        """Test URL building includes API prefix."""
        url = http_client._build_url("/jobs", None)
        assert url == "http://localhost:8080/api/v1/jobs"

    def test_build_url_skip_api_prefix(self, http_client: HttpClient) -> None:
        """Test URL building can skip API prefix."""
        url = http_client._build_url("/health", None, skip_api_prefix=True)
        assert url == "http://localhost:8080/health"

    def test_build_url_with_existing_api_prefix(self, http_client: HttpClient) -> None:
        """Test URL building handles existing API prefix."""
        url = http_client._build_url("/api/v1/jobs", None)
        assert url == "http://localhost:8080/api/v1/jobs"

    def test_build_url_with_query_params(self, http_client: HttpClient) -> None:
        """Test URL building with query params."""
        url = http_client._build_url("/jobs", {"status": "pending", "limit": 10})
        assert "status=pending" in url
        assert "limit=10" in url

    def test_build_headers_with_auth(self, http_client: HttpClient) -> None:
        """Test headers include auth token."""
        headers = http_client._build_headers()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")

    def test_build_headers_with_custom(self, http_client: HttpClient) -> None:
        """Test headers include custom headers."""
        headers = http_client._build_headers({"X-Custom": "value"})
        assert headers["X-Custom"] == "value"

    def test_set_auth_token(self, http_client: HttpClient) -> None:
        """Test setting auth token."""
        http_client.set_auth_token("new_token")
        headers = http_client._build_headers()
        assert headers["Authorization"] == "Bearer new_token"

    def test_context_manager(self) -> None:
        """Test HTTP client as context manager."""
        config = SpooledClientConfig(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url="http://localhost:8080",
        )
        resolved = resolve_config(config)
        breaker = create_circuit_breaker(resolved.circuit_breaker)

        with HttpClient(resolved, breaker) as client:
            assert client is not None


class TestHttpClientRequests:
    """Tests for HttpClient request methods."""

    BASE_URL = "http://localhost:8080"

    @pytest.fixture
    def http_client(self) -> HttpClient:
        """Create an HTTP client for tests."""
        config = SpooledClientConfig(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url=self.BASE_URL,
            retry=RetryConfig(max_retries=0),  # Disable retries for unit tests
            circuit_breaker=CircuitBreakerConfig(enabled=False),
        )
        resolved = resolve_config(config)
        breaker = create_circuit_breaker(resolved.circuit_breaker)
        return HttpClient(resolved, breaker)

    @respx.mock
    def test_get_request(self, http_client: HttpClient) -> None:
        """Test GET request."""
        respx.get(f"{self.BASE_URL}/api/v1/jobs/job_123").mock(
            return_value=httpx.Response(
                200,
                json={"id": "job_123", "status": "pending"},
            )
        )

        result = http_client.get("/jobs/job_123")
        assert result["id"] == "job_123"

    @respx.mock
    def test_post_request(self, http_client: HttpClient) -> None:
        """Test POST request."""
        respx.post(f"{self.BASE_URL}/api/v1/jobs").mock(
            return_value=httpx.Response(
                200,
                json={"id": "job_new", "created": True},
            )
        )

        result = http_client.post("/jobs", {"queue_name": "test", "payload": {}})
        assert result["created"] is True

    @respx.mock
    def test_put_request(self, http_client: HttpClient) -> None:
        """Test PUT request."""
        respx.put(f"{self.BASE_URL}/api/v1/jobs/job_123/priority").mock(
            return_value=httpx.Response(
                200,
                json={"priority": 10},
            )
        )

        result = http_client.put("/jobs/job_123/priority", {"priority": 10})
        assert result["priority"] == 10

    @respx.mock
    def test_patch_request(self, http_client: HttpClient) -> None:
        """Test PATCH request."""
        respx.patch(f"{self.BASE_URL}/api/v1/orgs/org_1").mock(
            return_value=httpx.Response(
                200,
                json={"name": "Updated Org"},
            )
        )

        result = http_client.patch("/orgs/org_1", {"name": "Updated Org"})
        assert result["name"] == "Updated Org"

    @respx.mock
    def test_delete_request(self, http_client: HttpClient) -> None:
        """Test DELETE request."""
        respx.delete(f"{self.BASE_URL}/api/v1/jobs/job_123").mock(
            return_value=httpx.Response(204)
        )

        result = http_client.delete("/jobs/job_123")
        assert result is None

    @respx.mock
    def test_handles_204_no_content(self, http_client: HttpClient) -> None:
        """Test handling 204 No Content response."""
        respx.post(f"{self.BASE_URL}/api/v1/workers/w_1/heartbeat").mock(
            return_value=httpx.Response(204)
        )

        result = http_client.post("/workers/w_1/heartbeat", {})
        assert result is None


class TestHttpClientErrors:
    """Tests for HttpClient error handling."""

    BASE_URL = "http://localhost:8080"

    @pytest.fixture
    def http_client(self) -> HttpClient:
        """Create an HTTP client for tests."""
        config = SpooledClientConfig(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url=self.BASE_URL,
            retry=RetryConfig(max_retries=0),
            circuit_breaker=CircuitBreakerConfig(enabled=False),
        )
        resolved = resolve_config(config)
        breaker = create_circuit_breaker(resolved.circuit_breaker)
        return HttpClient(resolved, breaker)

    @respx.mock
    def test_400_validation_error(self, http_client: HttpClient) -> None:
        """Test 400 raises ValidationError."""
        respx.post(f"{self.BASE_URL}/api/v1/jobs").mock(
            return_value=httpx.Response(
                400,
                json={"code": "invalid_input", "message": "queue_name required"},
            )
        )

        with pytest.raises(ValidationError) as exc_info:
            http_client.post("/jobs", {})
        assert exc_info.value.code == "invalid_input"

    @respx.mock
    def test_401_authentication_error(self, http_client: HttpClient) -> None:
        """Test 401 raises AuthenticationError."""
        respx.get(f"{self.BASE_URL}/api/v1/jobs").mock(
            return_value=httpx.Response(
                401,
                json={"code": "invalid_token", "message": "Token expired"},
            )
        )

        with pytest.raises(AuthenticationError):
            http_client.get("/jobs")

    @respx.mock
    def test_404_not_found_error(self, http_client: HttpClient) -> None:
        """Test 404 raises NotFoundError."""
        respx.get(f"{self.BASE_URL}/api/v1/jobs/nonexistent").mock(
            return_value=httpx.Response(
                404,
                json={"code": "not_found", "message": "Job not found"},
            )
        )

        with pytest.raises(NotFoundError):
            http_client.get("/jobs/nonexistent")

    @respx.mock
    def test_429_rate_limit_error(self, http_client: HttpClient) -> None:
        """Test 429 raises RateLimitError."""
        respx.post(f"{self.BASE_URL}/api/v1/jobs").mock(
            return_value=httpx.Response(
                429,
                json={"code": "rate_limited", "message": "Too many requests"},
            )
        )

        with pytest.raises(RateLimitError):
            http_client.post("/jobs", {})

    @respx.mock
    def test_500_server_error(self, http_client: HttpClient) -> None:
        """Test 500 raises ServerError."""
        respx.get(f"{self.BASE_URL}/api/v1/jobs").mock(
            return_value=httpx.Response(
                500,
                json={"code": "internal_error", "message": "Internal server error"},
            )
        )

        with pytest.raises(ServerError):
            http_client.get("/jobs")

    @respx.mock
    def test_502_server_error(self, http_client: HttpClient) -> None:
        """Test 502 raises ServerError."""
        respx.get(f"{self.BASE_URL}/api/v1/jobs").mock(
            return_value=httpx.Response(502, json={"message": "Bad gateway"})
        )

        with pytest.raises(ServerError):
            http_client.get("/jobs")

    @respx.mock
    def test_error_with_request_id(self, http_client: HttpClient) -> None:
        """Test error includes request ID."""
        respx.get(f"{self.BASE_URL}/api/v1/jobs").mock(
            return_value=httpx.Response(
                500,
                json={"message": "Error"},
                headers={"X-Request-Id": "req_123456"},
            )
        )

        with pytest.raises(ServerError) as exc_info:
            http_client.get("/jobs")
        assert exc_info.value.request_id == "req_123456"

    @respx.mock
    def test_error_without_json_body(self, http_client: HttpClient) -> None:
        """Test handling error without JSON body."""
        respx.get(f"{self.BASE_URL}/api/v1/jobs").mock(
            return_value=httpx.Response(
                500,
                content=b"Internal Server Error",
            )
        )

        with pytest.raises(ServerError) as exc_info:
            http_client.get("/jobs")
        assert exc_info.value.message == "Unknown error"


class TestHttpClientNonJsonResponse:
    """Tests for HttpClient with non-JSON responses."""

    BASE_URL = "http://localhost:8080"

    @pytest.fixture
    def http_client(self) -> HttpClient:
        """Create an HTTP client for tests."""
        config = SpooledClientConfig(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url=self.BASE_URL,
            retry=RetryConfig(max_retries=0),
            circuit_breaker=CircuitBreakerConfig(enabled=False),
        )
        resolved = resolve_config(config)
        breaker = create_circuit_breaker(resolved.circuit_breaker)
        return HttpClient(resolved, breaker)

    @respx.mock
    def test_text_response(self, http_client: HttpClient) -> None:
        """Test handling text/plain response."""
        respx.get(f"{self.BASE_URL}/metrics").mock(
            return_value=httpx.Response(
                200,
                content=b"# HELP spooled_jobs_total\nspooled_jobs_total 100",
                headers={"Content-Type": "text/plain"},
            )
        )

        result = http_client.get("/metrics", skip_api_prefix=True)
        assert "spooled_jobs_total" in result



