"""
Custom exception classes for Spooled SDK.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


class SpooledError(Exception):
    """Base error class for all Spooled SDK errors."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 0,
        code: str = "unknown_error",
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details
        self.request_id = request_id

    def is_retryable(self) -> bool:
        """Check if this error is retryable."""
        return False

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.code}: {self.message})"


class AuthenticationError(SpooledError):
    """401 - Authentication failed."""

    def __init__(
        self,
        message: str = "Authentication failed",
        *,
        code: str = "authentication_error",
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            status_code=401,
            code=code,
            details=details,
            request_id=request_id,
        )


class AuthorizationError(SpooledError):
    """403 - Access denied."""

    def __init__(
        self,
        message: str = "Access denied",
        *,
        code: str = "authorization_error",
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            status_code=403,
            code=code,
            details=details,
            request_id=request_id,
        )


class NotFoundError(SpooledError):
    """404 - Resource not found."""

    def __init__(
        self,
        message: str = "Resource not found",
        *,
        code: str = "not_found",
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            status_code=404,
            code=code,
            details=details,
            request_id=request_id,
        )


class ConflictError(SpooledError):
    """409 - Conflict (e.g., duplicate resource)."""

    def __init__(
        self,
        message: str = "Resource conflict",
        *,
        code: str = "conflict",
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            status_code=409,
            code=code,
            details=details,
            request_id=request_id,
        )


class ValidationError(SpooledError):
    """400 - Validation failed."""

    def __init__(
        self,
        message: str = "Validation failed",
        *,
        code: str = "validation_error",
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            status_code=400,
            code=code,
            details=details,
            request_id=request_id,
        )


class PayloadTooLargeError(SpooledError):
    """413 - Request payload too large."""

    def __init__(
        self,
        message: str = "Request payload too large",
        *,
        code: str = "payload_too_large",
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            status_code=413,
            code=code,
            details=details,
            request_id=request_id,
        )


class RateLimitError(SpooledError):
    """429 - Rate limit exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        code: str = "rate_limit_exceeded",
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
        retry_after: int = 60,
        limit: int | None = None,
        remaining: int | None = None,
        reset: datetime | None = None,
    ) -> None:
        super().__init__(
            message,
            status_code=429,
            code=code,
            details=details,
            request_id=request_id,
        )
        self.retry_after = retry_after
        self.limit = limit
        self.remaining = remaining
        self.reset = reset

    def is_retryable(self) -> bool:
        return True

    def get_retry_after(self) -> int:
        """Get the number of seconds to wait before retrying."""
        return self.retry_after


class ServerError(SpooledError):
    """5xx - Server error."""

    def __init__(
        self,
        message: str = "Server error",
        *,
        status_code: int = 500,
        code: str = "server_error",
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status_code,
            code=code,
            details=details,
            request_id=request_id,
        )

    def is_retryable(self) -> bool:
        return True


class NetworkError(SpooledError):
    """Network request failed (no response)."""

    def __init__(
        self,
        message: str = "Network request failed",
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, status_code=0, code="network_error")
        self.__cause__ = cause

    def is_retryable(self) -> bool:
        return True


class TimeoutError(SpooledError):
    """Request timed out."""

    def __init__(
        self,
        message: str = "Request timed out",
        timeout_seconds: float = 0,
    ) -> None:
        super().__init__(message, status_code=0, code="timeout")
        self.timeout_seconds = timeout_seconds

    def is_retryable(self) -> bool:
        return True


class CircuitBreakerOpenError(SpooledError):
    """Circuit breaker is open."""

    def __init__(
        self,
        message: str = "Circuit breaker is open",
    ) -> None:
        super().__init__(message, status_code=0, code="circuit_breaker_open")

    def is_retryable(self) -> bool:
        return False


class JobAbortedError(Exception):
    """Raised when a job is aborted during processing."""

    def __init__(self, message: str = "Job was aborted") -> None:
        super().__init__(message)
        self.message = message


def is_spooled_error(error: Exception) -> bool:
    """Check if an exception is a Spooled SDK error."""
    return isinstance(error, SpooledError)


def create_error_from_response(
    status_code: int,
    body: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> SpooledError:
    """Create appropriate error from HTTP response."""
    code = body.get("code", "unknown_error") if body else "unknown_error"
    message = body.get("message", "Unknown error") if body else "Unknown error"
    details = body.get("details") if body else None

    error_classes: dict[int, type[SpooledError]] = {
        400: ValidationError,
        401: AuthenticationError,
        403: AuthorizationError,
        404: NotFoundError,
        409: ConflictError,
        413: PayloadTooLargeError,
        429: RateLimitError,
    }

    if status_code in error_classes:
        error_class = error_classes[status_code]
        if error_class == RateLimitError:
            return RateLimitError(
                message,
                code=code,
                details=details,
                request_id=request_id,
            )
        return error_class(
            message,
            code=code,
            details=details,
            request_id=request_id,
        )

    if 500 <= status_code < 600:
        return ServerError(
            message,
            status_code=status_code,
            code=code,
            details=details,
            request_id=request_id,
        )

    return SpooledError(
        message,
        status_code=status_code,
        code=code,
        details=details,
        request_id=request_id,
    )
