"""Unit tests for retry module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from spooled.config import RetryConfig
from spooled.errors import NetworkError, RateLimitError, ServerError, ValidationError
from spooled.utils.retry import calculate_delay, should_retry, with_retry


class TestShouldRetry:
    """Tests for should_retry function."""

    @pytest.fixture
    def config(self) -> RetryConfig:
        """Create a retry config for tests."""
        return RetryConfig(max_retries=3)

    def test_no_retry_when_max_attempts_exceeded(self, config: RetryConfig) -> None:
        """Test no retry when max attempts exceeded."""
        error = ServerError()
        assert should_retry(error, 4, config) is False
        assert should_retry(error, 5, config) is False

    def test_retry_on_rate_limit(self, config: RetryConfig) -> None:
        """Test always retry on rate limit error."""
        error = RateLimitError()
        assert should_retry(error, 1, config) is True
        assert should_retry(error, 2, config) is True
        assert should_retry(error, 3, config) is True

    def test_retry_on_server_error(self, config: RetryConfig) -> None:
        """Test retry on server error (retryable)."""
        error = ServerError()
        assert should_retry(error, 1, config) is True

    def test_retry_on_network_error(self, config: RetryConfig) -> None:
        """Test retry on network error (retryable)."""
        error = NetworkError()
        assert should_retry(error, 1, config) is True

    def test_no_retry_on_validation_error(self, config: RetryConfig) -> None:
        """Test no retry on validation error (not retryable)."""
        error = ValidationError()
        assert should_retry(error, 1, config) is False

    def test_retry_on_generic_exception(self, config: RetryConfig) -> None:
        """Test retry on generic exception."""
        error = Exception("Something went wrong")
        assert should_retry(error, 1, config) is True

    def test_no_retry_with_zero_retries(self) -> None:
        """Test no retry when max_retries is 0."""
        config = RetryConfig(max_retries=0)
        error = ServerError()
        assert should_retry(error, 1, config) is False


class TestCalculateDelay:
    """Tests for calculate_delay function."""

    @pytest.fixture
    def config(self) -> RetryConfig:
        """Create a retry config for tests."""
        return RetryConfig(
            base_delay=1.0,
            max_delay=30.0,
            factor=2.0,
            jitter=False,
        )

    def test_first_attempt_delay(self, config: RetryConfig) -> None:
        """Test delay for first attempt."""
        delay = calculate_delay(1, config)
        assert delay == 1.0  # base_delay * factor^0

    def test_exponential_backoff(self, config: RetryConfig) -> None:
        """Test exponential backoff."""
        assert calculate_delay(1, config) == 1.0   # 1 * 2^0 = 1
        assert calculate_delay(2, config) == 2.0   # 1 * 2^1 = 2
        assert calculate_delay(3, config) == 4.0   # 1 * 2^2 = 4
        assert calculate_delay(4, config) == 8.0   # 1 * 2^3 = 8

    def test_max_delay_cap(self, config: RetryConfig) -> None:
        """Test delay is capped at max_delay."""
        delay = calculate_delay(10, config)  # Would be 512 without cap
        assert delay == 30.0  # Capped at max_delay

    def test_retry_after_override(self, config: RetryConfig) -> None:
        """Test retry_after from rate limit overrides calculation."""
        delay = calculate_delay(1, config, retry_after=45)
        assert delay == 30.0  # Capped at max_delay

        delay = calculate_delay(1, config, retry_after=10)
        assert delay == 10.0  # Uses retry_after

    def test_jitter_adds_randomness(self) -> None:
        """Test jitter adds randomness to delay."""
        config = RetryConfig(
            base_delay=1.0,
            max_delay=30.0,
            factor=2.0,
            jitter=True,
        )

        # With jitter, delay should be between base and base + 25%
        delays = [calculate_delay(1, config) for _ in range(100)]
        assert all(1.0 <= d <= 1.25 for d in delays)
        # Should have some variation
        assert len(set(delays)) > 1


class TestWithRetry:
    """Tests for with_retry function."""

    @pytest.fixture
    def config(self) -> RetryConfig:
        """Create a retry config for tests."""
        return RetryConfig(
            max_retries=3,
            base_delay=0.01,  # Fast for tests
            max_delay=0.1,
            factor=2.0,
            jitter=False,
        )

    def test_success_no_retry(self, config: RetryConfig) -> None:
        """Test successful function doesn't retry."""
        fn = MagicMock(return_value="success")

        result = with_retry(fn, config)

        assert result == "success"
        assert fn.call_count == 1

    def test_retry_on_failure(self, config: RetryConfig) -> None:
        """Test retry on retryable error."""
        fn = MagicMock(side_effect=[ServerError(), ServerError(), "success"])

        result = with_retry(fn, config)

        assert result == "success"
        assert fn.call_count == 3

    def test_exhaust_retries(self, config: RetryConfig) -> None:
        """Test exhausting all retries."""
        fn = MagicMock(side_effect=ServerError())

        with pytest.raises(ServerError):
            with_retry(fn, config)

        # Initial + 3 retries = 4 calls
        assert fn.call_count == 4

    def test_no_retry_on_non_retryable(self, config: RetryConfig) -> None:
        """Test no retry on non-retryable error."""
        fn = MagicMock(side_effect=ValidationError())

        with pytest.raises(ValidationError):
            with_retry(fn, config)

        assert fn.call_count == 1

    def test_on_retry_callback(self, config: RetryConfig) -> None:
        """Test on_retry callback is called."""
        fn = MagicMock(side_effect=[ServerError(), "success"])
        on_retry = MagicMock()

        result = with_retry(fn, config, on_retry=on_retry)

        assert result == "success"
        assert on_retry.call_count == 1
        # Check callback arguments
        call_args = on_retry.call_args
        assert call_args[0][0] == 1  # attempt
        assert isinstance(call_args[0][1], ServerError)  # error
        assert call_args[0][2] > 0  # delay

    def test_rate_limit_retry_after(self, config: RetryConfig) -> None:
        """Test rate limit retry_after is used."""
        error = RateLimitError(retry_after=5)
        fn = MagicMock(side_effect=[error, "success"])
        delays = []

        def on_retry(attempt: int, err: Exception, delay: float) -> None:
            delays.append(delay)

        with patch("spooled.utils.retry.time.sleep"):
            result = with_retry(fn, config, on_retry=on_retry)

        assert result == "success"
        # Should use max_delay (0.1) since retry_after (5) exceeds it
        assert delays[0] == 0.1

    def test_preserves_return_type(self, config: RetryConfig) -> None:
        """Test return type is preserved."""
        fn = MagicMock(return_value={"key": "value"})
        result = with_retry(fn, config)
        assert result == {"key": "value"}

        fn = MagicMock(return_value=None)
        result = with_retry(fn, config)
        assert result is None

        fn = MagicMock(return_value=[1, 2, 3])
        result = with_retry(fn, config)
        assert result == [1, 2, 3]
