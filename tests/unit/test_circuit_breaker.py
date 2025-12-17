"""Unit tests for circuit breaker module."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from spooled.config import CircuitBreakerConfig
from spooled.errors import CircuitBreakerOpenError, ServerError, ValidationError
from spooled.utils.circuit_breaker import CircuitBreaker, CircuitState, create_circuit_breaker


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    @pytest.fixture
    def config(self) -> CircuitBreakerConfig:
        """Create a circuit breaker config for tests."""
        return CircuitBreakerConfig(
            enabled=True,
            failure_threshold=3,
            success_threshold=2,
            timeout=1.0,  # 1 second for tests
        )

    @pytest.fixture
    def breaker(self, config: CircuitBreakerConfig) -> CircuitBreaker:
        """Create a circuit breaker for tests."""
        return CircuitBreaker(config)

    def test_initial_state_is_closed(self, breaker: CircuitBreaker) -> None:
        """Test circuit starts closed."""
        assert breaker.get_state() == CircuitState.CLOSED
        assert breaker.is_allowed() is True

    def test_disabled_breaker_always_allows(self) -> None:
        """Test disabled circuit breaker always allows."""
        config = CircuitBreakerConfig(enabled=False)
        breaker = CircuitBreaker(config)

        # Record many failures
        for _ in range(10):
            breaker.record_failure(ServerError())

        assert breaker.is_allowed() is True

    def test_opens_after_failure_threshold(self, breaker: CircuitBreaker) -> None:
        """Test circuit opens after failure threshold."""
        # Record failures up to threshold
        for _ in range(3):
            breaker.record_failure(ServerError())

        assert breaker.get_state() == CircuitState.OPEN
        assert breaker.is_allowed() is False

    def test_success_resets_failure_count(self, breaker: CircuitBreaker) -> None:
        """Test success resets failure count."""
        # Record some failures
        breaker.record_failure(ServerError())
        breaker.record_failure(ServerError())

        # Success should reset
        breaker.record_success()

        # Two more failures shouldn't open (count was reset)
        breaker.record_failure(ServerError())
        breaker.record_failure(ServerError())
        assert breaker.get_state() == CircuitState.CLOSED

        # Third failure now opens it
        breaker.record_failure(ServerError())
        assert breaker.get_state() == CircuitState.OPEN

    def test_non_retryable_errors_not_counted(self, breaker: CircuitBreaker) -> None:
        """Test non-retryable errors don't count as failures."""
        # Validation errors are not retryable
        for _ in range(10):
            breaker.record_failure(ValidationError())

        assert breaker.get_state() == CircuitState.CLOSED

    def test_half_open_after_timeout(self, breaker: CircuitBreaker) -> None:
        """Test circuit becomes half-open after timeout."""
        # Open the circuit
        for _ in range(3):
            breaker.record_failure(ServerError())
        assert breaker.get_state() == CircuitState.OPEN

        # Wait for timeout
        time.sleep(1.1)

        # Should be half-open now
        assert breaker.get_state() == CircuitState.HALF_OPEN
        assert breaker.is_allowed() is True

    def test_half_open_to_closed_on_success(self, config: CircuitBreakerConfig) -> None:
        """Test half-open closes after success threshold."""
        breaker = CircuitBreaker(config)

        # Open the circuit
        for _ in range(3):
            breaker.record_failure(ServerError())

        # Wait for timeout
        time.sleep(1.1)
        assert breaker.get_state() == CircuitState.HALF_OPEN

        # Record successes up to threshold
        breaker.record_success()
        assert breaker.get_state() == CircuitState.HALF_OPEN
        breaker.record_success()

        # Should be closed now
        assert breaker.get_state() == CircuitState.CLOSED

    def test_half_open_to_open_on_failure(self, breaker: CircuitBreaker) -> None:
        """Test half-open opens again on failure."""
        # Open the circuit
        for _ in range(3):
            breaker.record_failure(ServerError())

        # Wait for timeout
        time.sleep(1.1)
        assert breaker.get_state() == CircuitState.HALF_OPEN

        # Any failure in half-open trips it again
        breaker.record_failure(ServerError())
        assert breaker.get_state() == CircuitState.OPEN

    def test_reset(self, breaker: CircuitBreaker) -> None:
        """Test manual reset."""
        # Open the circuit
        for _ in range(3):
            breaker.record_failure(ServerError())
        assert breaker.get_state() == CircuitState.OPEN

        # Reset
        breaker.reset()
        assert breaker.get_state() == CircuitState.CLOSED
        assert breaker.is_allowed() is True

    def test_get_stats(self, breaker: CircuitBreaker) -> None:
        """Test getting statistics."""
        breaker.record_failure(ServerError())
        breaker.record_failure(ServerError())
        breaker.record_success()

        stats = breaker.get_stats()
        assert stats["state"] == "CLOSED"
        assert stats["failure_count"] == 0  # Reset by success
        assert stats["config"]["enabled"] is True
        assert stats["config"]["failure_threshold"] == 3


class TestCircuitBreakerExecute:
    """Tests for circuit breaker execute method."""

    @pytest.fixture
    def breaker(self) -> CircuitBreaker:
        """Create a circuit breaker for tests."""
        config = CircuitBreakerConfig(
            enabled=True,
            failure_threshold=2,
            success_threshold=1,
            timeout=1.0,
        )
        return CircuitBreaker(config)

    def test_execute_success(self, breaker: CircuitBreaker) -> None:
        """Test successful execution."""
        result = breaker.execute(lambda: "success")
        assert result == "success"

    def test_execute_records_success(self, breaker: CircuitBreaker) -> None:
        """Test execute records success."""
        # Record a failure first
        breaker.record_failure(ServerError())

        # Execute success
        breaker.execute(lambda: "ok")

        # Failure count should be reset
        stats = breaker.get_stats()
        assert stats["failure_count"] == 0

    def test_execute_records_failure(self, breaker: CircuitBreaker) -> None:
        """Test execute records failure."""

        def failing_fn():
            raise ServerError()

        with pytest.raises(ServerError):
            breaker.execute(failing_fn)

        stats = breaker.get_stats()
        assert stats["failure_count"] == 1

    def test_execute_raises_when_open(self, breaker: CircuitBreaker) -> None:
        """Test execute raises when circuit is open."""
        # Open the circuit
        for _ in range(2):
            breaker.record_failure(ServerError())

        with pytest.raises(CircuitBreakerOpenError):
            breaker.execute(lambda: "ok")

    def test_execute_allows_half_open_request(self, breaker: CircuitBreaker) -> None:
        """Test execute allows request in half-open state."""
        # Open the circuit
        for _ in range(2):
            breaker.record_failure(ServerError())

        # Wait for timeout
        time.sleep(1.1)

        # Should allow one request
        result = breaker.execute(lambda: "recovered")
        assert result == "recovered"


class TestCreateCircuitBreaker:
    """Tests for create_circuit_breaker factory."""

    def test_creates_breaker(self) -> None:
        """Test factory creates circuit breaker."""
        config = CircuitBreakerConfig()
        breaker = create_circuit_breaker(config)
        assert isinstance(breaker, CircuitBreaker)
        assert breaker.config == config


