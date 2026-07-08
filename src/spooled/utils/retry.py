"""
Retry logic with exponential backoff.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from spooled.config import RetryConfig
from spooled.errors import RateLimitError, SpooledError

T = TypeVar("T")


def should_retry(
    error: Exception,
    attempt: int,
    config: RetryConfig,
    idempotent: bool = True,
) -> bool:
    """Determine if a request should be retried based on the error.

    ``idempotent`` indicates whether replaying the request is safe. A rate
    limit (429) is always safe to retry because the server rejected the request
    before processing it. For every other retryable condition (5xx, network,
    timeout) a non-idempotent request is NOT retried, so a write that may have
    already reached the server is never silently duplicated.
    """
    if attempt > config.max_retries:
        return False

    # Always retry rate limit errors — the request was rejected, not processed.
    if isinstance(error, RateLimitError):
        return True

    # Do not replay non-idempotent requests on ambiguous failures.
    if not idempotent:
        return False

    # Retry retryable errors
    if isinstance(error, SpooledError):
        return error.is_retryable()

    # Retry on connection errors (generic exceptions from httpx)
    return True


def calculate_delay(
    attempt: int,
    config: RetryConfig,
    retry_after: int | None = None,
) -> float:
    """Calculate delay with exponential backoff and jitter."""
    # Use retry_after from rate limit response if provided
    if retry_after is not None and retry_after > 0:
        return min(float(retry_after), config.max_delay)

    # Exponential backoff: base_delay * factor^(attempt-1)
    delay = config.base_delay * (config.factor ** (attempt - 1))
    delay = min(delay, config.max_delay)

    # Add jitter (up to 25% of delay)
    if config.jitter:
        jitter_range = delay * 0.25
        delay += random.uniform(0, jitter_range)

    return delay


def with_retry(
    fn: Callable[[], T],
    config: RetryConfig,
    on_retry: Callable[[int, Exception, float], None] | None = None,
    idempotent: bool = True,
) -> T:
    """
    Execute a function with retry logic.

    Args:
        fn: Function to execute
        config: Retry configuration
        on_retry: Optional callback called before each retry with (attempt, error, delay)
        idempotent: Whether the operation is safe to replay (see ``should_retry``)

    Returns:
        The result of the function

    Raises:
        The last exception if all retries are exhausted
    """
    last_error: Exception | None = None

    for attempt in range(1, config.max_retries + 2):
        try:
            return fn()
        except Exception as e:
            last_error = e

            if not should_retry(e, attempt, config, idempotent):
                raise

            # Get retry_after from rate limit error
            retry_after: int | None = None
            if isinstance(e, RateLimitError):
                retry_after = e.retry_after

            delay = calculate_delay(attempt, config, retry_after)

            if on_retry:
                on_retry(attempt, e, delay)

            time.sleep(delay)

    # Should not reach here, but satisfy type checker
    if last_error:
        raise last_error
    raise RuntimeError("Retry loop exited unexpectedly")


async def with_retry_async(
    fn: Callable[[], Awaitable[T]],
    config: RetryConfig,
    on_retry: Callable[[int, Exception, float], None] | None = None,
    idempotent: bool = True,
) -> T:
    """
    Execute an async function with retry logic.

    Args:
        fn: Async function to execute
        config: Retry configuration
        on_retry: Optional callback called before each retry with (attempt, error, delay)
        idempotent: Whether the operation is safe to replay (see ``should_retry``)

    Returns:
        The result of the function

    Raises:
        The last exception if all retries are exhausted
    """
    last_error: Exception | None = None

    for attempt in range(1, config.max_retries + 2):
        try:
            return await fn()
        except Exception as e:
            last_error = e

            if not should_retry(e, attempt, config, idempotent):
                raise

            # Get retry_after from rate limit error
            retry_after: int | None = None
            if isinstance(e, RateLimitError):
                retry_after = e.retry_after

            delay = calculate_delay(attempt, config, retry_after)

            if on_retry:
                on_retry(attempt, e, delay)

            await asyncio.sleep(delay)

    # Should not reach here, but satisfy type checker
    if last_error:
        raise last_error
    raise RuntimeError("Retry loop exited unexpectedly")
