"""
Circuit breaker implementation for resilient API calls.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from enum import Enum
from typing import Any, TypeVar

from spooled.config import CircuitBreakerConfig
from spooled.errors import CircuitBreakerOpenError, SpooledError

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"  # Rejecting requests
    HALF_OPEN = "HALF_OPEN"  # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker implementation.

    Prevents cascading failures by tracking error rates and
    temporarily blocking requests when failure threshold is exceeded.
    """

    def __init__(self, config: CircuitBreakerConfig) -> None:
        self.config = config
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None
        self._lock = threading.Lock()

    def get_state(self) -> CircuitState:
        """Get current circuit breaker state."""
        with self._lock:
            return self._get_state_unlocked()

    def _get_state_unlocked(self) -> CircuitState:
        """Get state without acquiring lock (must be called with lock held)."""
        if self._state == CircuitState.OPEN:
            # Check if timeout has elapsed
            if self._last_failure_time is not None:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.config.timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
        return self._state

    def is_allowed(self) -> bool:
        """Check if requests are allowed."""
        if not self.config.enabled:
            return True

        with self._lock:
            state = self._get_state_unlocked()
            return state != CircuitState.OPEN

    def record_success(self) -> None:
        """Record a successful request."""
        if not self.config.enabled:
            return

        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    def record_failure(self, error: Exception) -> None:
        """Record a failed request."""
        if not self.config.enabled:
            return

        # Only count certain errors as failures
        if isinstance(error, SpooledError) and not error.is_retryable():
            return

        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open state trips the breaker
                self._state = CircuitState.OPEN
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    self._state = CircuitState.OPEN

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None

    def execute(self, fn: Callable[[], T]) -> T:
        """Execute a function with circuit breaker protection."""
        if not self.is_allowed():
            raise CircuitBreakerOpenError(
                f"Circuit breaker is open. Will retry after {self.config.timeout}s"
            )

        try:
            result = fn()
            self.record_success()
            return result
        except Exception as e:
            self.record_failure(e)
            raise

    def get_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics."""
        with self._lock:
            return {
                "state": self._get_state_unlocked().value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure_time": self._last_failure_time,
                "config": {
                    "enabled": self.config.enabled,
                    "failure_threshold": self.config.failure_threshold,
                    "success_threshold": self.config.success_threshold,
                    "timeout": self.config.timeout,
                },
            }


def create_circuit_breaker(config: CircuitBreakerConfig) -> CircuitBreaker:
    """Create a circuit breaker instance."""
    return CircuitBreaker(config)
