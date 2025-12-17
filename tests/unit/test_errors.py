"""Unit tests for error module."""

from __future__ import annotations

from datetime import datetime

import pytest

from spooled.errors import (
    AuthenticationError,
    AuthorizationError,
    CircuitBreakerOpenError,
    ConflictError,
    JobAbortedError,
    NetworkError,
    NotFoundError,
    PayloadTooLargeError,
    RateLimitError,
    ServerError,
    SpooledError,
    TimeoutError,
    ValidationError,
    create_error_from_response,
    is_spooled_error,
)


class TestSpooledError:
    """Tests for base SpooledError."""

    def test_basic_error(self) -> None:
        """Test basic error creation."""
        error = SpooledError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.status_code == 0
        assert error.code == "unknown_error"
        assert error.details is None
        assert error.request_id is None

    def test_error_with_all_params(self) -> None:
        """Test error with all parameters."""
        error = SpooledError(
            "Custom error",
            status_code=500,
            code="custom_code",
            details={"field": "value"},
            request_id="req_123",
        )
        assert error.message == "Custom error"
        assert error.status_code == 500
        assert error.code == "custom_code"
        assert error.details == {"field": "value"}
        assert error.request_id == "req_123"

    def test_is_retryable_default_false(self) -> None:
        """Test base error is not retryable."""
        error = SpooledError("error")
        assert error.is_retryable() is False

    def test_repr(self) -> None:
        """Test error representation."""
        error = SpooledError("test", code="test_code")
        assert "SpooledError" in repr(error)
        assert "test_code" in repr(error)


class TestAuthenticationError:
    """Tests for AuthenticationError."""

    def test_default_message(self) -> None:
        """Test default error message."""
        error = AuthenticationError()
        assert error.message == "Authentication failed"
        assert error.status_code == 401
        assert error.code == "authentication_error"

    def test_custom_message(self) -> None:
        """Test custom error message."""
        error = AuthenticationError("Invalid API key")
        assert error.message == "Invalid API key"
        assert error.status_code == 401

    def test_not_retryable(self) -> None:
        """Test auth error is not retryable."""
        error = AuthenticationError()
        assert error.is_retryable() is False


class TestAuthorizationError:
    """Tests for AuthorizationError."""

    def test_default_values(self) -> None:
        """Test default error values."""
        error = AuthorizationError()
        assert error.message == "Access denied"
        assert error.status_code == 403
        assert error.code == "authorization_error"

    def test_not_retryable(self) -> None:
        """Test authorization error is not retryable."""
        error = AuthorizationError()
        assert error.is_retryable() is False


class TestNotFoundError:
    """Tests for NotFoundError."""

    def test_default_values(self) -> None:
        """Test default error values."""
        error = NotFoundError()
        assert error.message == "Resource not found"
        assert error.status_code == 404
        assert error.code == "not_found"

    def test_not_retryable(self) -> None:
        """Test not found error is not retryable."""
        error = NotFoundError()
        assert error.is_retryable() is False


class TestConflictError:
    """Tests for ConflictError."""

    def test_default_values(self) -> None:
        """Test default error values."""
        error = ConflictError()
        assert error.message == "Resource conflict"
        assert error.status_code == 409
        assert error.code == "conflict"

    def test_custom_message(self) -> None:
        """Test custom error message."""
        error = ConflictError("Duplicate entry")
        assert error.message == "Duplicate entry"


class TestValidationError:
    """Tests for ValidationError."""

    def test_default_values(self) -> None:
        """Test default error values."""
        error = ValidationError()
        assert error.message == "Validation failed"
        assert error.status_code == 400
        assert error.code == "validation_error"

    def test_with_details(self) -> None:
        """Test validation error with field details."""
        error = ValidationError(
            "Invalid input",
            details={"fields": {"email": "Invalid format"}},
        )
        assert error.details == {"fields": {"email": "Invalid format"}}


class TestPayloadTooLargeError:
    """Tests for PayloadTooLargeError."""

    def test_default_values(self) -> None:
        """Test default error values."""
        error = PayloadTooLargeError()
        assert error.message == "Request payload too large"
        assert error.status_code == 413
        assert error.code == "payload_too_large"


class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_default_values(self) -> None:
        """Test default error values."""
        error = RateLimitError()
        assert error.message == "Rate limit exceeded"
        assert error.status_code == 429
        assert error.code == "rate_limit_exceeded"
        assert error.retry_after == 60

    def test_with_rate_limit_info(self) -> None:
        """Test rate limit error with full info."""
        now = datetime.now()
        error = RateLimitError(
            retry_after=30,
            limit=1000,
            remaining=0,
            reset=now,
        )
        assert error.retry_after == 30
        assert error.limit == 1000
        assert error.remaining == 0
        assert error.reset == now

    def test_is_retryable(self) -> None:
        """Test rate limit error is retryable."""
        error = RateLimitError()
        assert error.is_retryable() is True

    def test_get_retry_after(self) -> None:
        """Test getting retry after value."""
        error = RateLimitError(retry_after=45)
        assert error.get_retry_after() == 45


class TestServerError:
    """Tests for ServerError."""

    def test_default_values(self) -> None:
        """Test default error values."""
        error = ServerError()
        assert error.message == "Server error"
        assert error.status_code == 500
        assert error.code == "server_error"

    def test_custom_status_code(self) -> None:
        """Test server error with custom status code."""
        error = ServerError("Gateway timeout", status_code=504)
        assert error.status_code == 504

    def test_is_retryable(self) -> None:
        """Test server error is retryable."""
        error = ServerError()
        assert error.is_retryable() is True


class TestNetworkError:
    """Tests for NetworkError."""

    def test_default_values(self) -> None:
        """Test default error values."""
        error = NetworkError()
        assert error.message == "Network request failed"
        assert error.status_code == 0
        assert error.code == "network_error"

    def test_with_cause(self) -> None:
        """Test network error with underlying cause."""
        cause = ConnectionError("Connection refused")
        error = NetworkError("Failed to connect", cause=cause)
        assert error.__cause__ is cause

    def test_is_retryable(self) -> None:
        """Test network error is retryable."""
        error = NetworkError()
        assert error.is_retryable() is True


class TestTimeoutError:
    """Tests for TimeoutError."""

    def test_default_values(self) -> None:
        """Test default error values."""
        error = TimeoutError()
        assert error.message == "Request timed out"
        assert error.status_code == 0
        assert error.code == "timeout"
        assert error.timeout_seconds == 0

    def test_with_timeout_value(self) -> None:
        """Test timeout error with duration."""
        error = TimeoutError("Timed out after 30s", timeout_seconds=30.0)
        assert error.timeout_seconds == 30.0

    def test_is_retryable(self) -> None:
        """Test timeout error is retryable."""
        error = TimeoutError()
        assert error.is_retryable() is True


class TestCircuitBreakerOpenError:
    """Tests for CircuitBreakerOpenError."""

    def test_default_values(self) -> None:
        """Test default error values."""
        error = CircuitBreakerOpenError()
        assert error.message == "Circuit breaker is open"
        assert error.code == "circuit_breaker_open"

    def test_not_retryable(self) -> None:
        """Test circuit breaker error is not retryable."""
        error = CircuitBreakerOpenError()
        assert error.is_retryable() is False


class TestJobAbortedError:
    """Tests for JobAbortedError."""

    def test_default_message(self) -> None:
        """Test default error message."""
        error = JobAbortedError()
        assert error.message == "Job was aborted"

    def test_custom_message(self) -> None:
        """Test custom error message."""
        error = JobAbortedError("Worker shutdown")
        assert error.message == "Worker shutdown"


class TestIsSpooledError:
    """Tests for is_spooled_error function."""

    def test_spooled_error(self) -> None:
        """Test detecting Spooled errors."""
        assert is_spooled_error(SpooledError("test")) is True
        assert is_spooled_error(AuthenticationError()) is True
        assert is_spooled_error(ServerError()) is True

    def test_non_spooled_error(self) -> None:
        """Test non-Spooled errors."""
        assert is_spooled_error(ValueError("test")) is False
        assert is_spooled_error(Exception("test")) is False
        assert is_spooled_error(RuntimeError("test")) is False


class TestCreateErrorFromResponse:
    """Tests for create_error_from_response function."""

    def test_400_validation_error(self) -> None:
        """Test 400 creates ValidationError."""
        error = create_error_from_response(
            400,
            {"code": "invalid_input", "message": "Invalid field"},
            "req_123",
        )
        assert isinstance(error, ValidationError)
        assert error.code == "invalid_input"
        assert error.message == "Invalid field"
        assert error.request_id == "req_123"

    def test_401_authentication_error(self) -> None:
        """Test 401 creates AuthenticationError."""
        error = create_error_from_response(401, {"message": "Invalid token"})
        assert isinstance(error, AuthenticationError)
        assert error.message == "Invalid token"

    def test_403_authorization_error(self) -> None:
        """Test 403 creates AuthorizationError."""
        error = create_error_from_response(403, {"message": "Forbidden"})
        assert isinstance(error, AuthorizationError)

    def test_404_not_found_error(self) -> None:
        """Test 404 creates NotFoundError."""
        error = create_error_from_response(404, {"message": "Job not found"})
        assert isinstance(error, NotFoundError)

    def test_409_conflict_error(self) -> None:
        """Test 409 creates ConflictError."""
        error = create_error_from_response(409, {"message": "Duplicate key"})
        assert isinstance(error, ConflictError)

    def test_413_payload_too_large(self) -> None:
        """Test 413 creates PayloadTooLargeError."""
        error = create_error_from_response(413, {"message": "Payload too large"})
        assert isinstance(error, PayloadTooLargeError)

    def test_429_rate_limit_error(self) -> None:
        """Test 429 creates RateLimitError."""
        error = create_error_from_response(429, {"message": "Too many requests"})
        assert isinstance(error, RateLimitError)

    def test_500_server_error(self) -> None:
        """Test 500 creates ServerError."""
        error = create_error_from_response(500, {"message": "Internal error"})
        assert isinstance(error, ServerError)
        assert error.status_code == 500

    def test_502_server_error(self) -> None:
        """Test 502 creates ServerError."""
        error = create_error_from_response(502, {"message": "Bad gateway"})
        assert isinstance(error, ServerError)
        assert error.status_code == 502

    def test_503_server_error(self) -> None:
        """Test 503 creates ServerError."""
        error = create_error_from_response(503, {"message": "Service unavailable"})
        assert isinstance(error, ServerError)
        assert error.status_code == 503

    def test_unknown_status_code(self) -> None:
        """Test unknown status code creates base SpooledError."""
        error = create_error_from_response(418, {"message": "I'm a teapot"})
        assert type(error) is SpooledError
        assert error.status_code == 418

    def test_no_body(self) -> None:
        """Test handling response with no body."""
        error = create_error_from_response(500, None)
        assert error.message == "Unknown error"
        assert error.code == "unknown_error"

    def test_body_with_details(self) -> None:
        """Test response with details field."""
        error = create_error_from_response(
            400,
            {
                "message": "Validation failed",
                "code": "validation_error",
                "details": {"field": "queue_name", "reason": "required"},
            },
        )
        assert error.details == {"field": "queue_name", "reason": "required"}


