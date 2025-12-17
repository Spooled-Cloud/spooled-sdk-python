"""Pytest fixtures and configuration."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
import respx

from spooled import AsyncSpooledClient, SpooledClient
from spooled.config import CircuitBreakerConfig, RetryConfig

# Test API key
TEST_API_KEY = "sk_test_xxxxxxxxxxxxxxxxxxxx"
TEST_BASE_URL = "http://localhost:8080"


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use the default event loop policy."""
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture
def api_key() -> str:
    """Get API key from environment or use test key."""
    return os.environ.get("SPOOLED_API_KEY", TEST_API_KEY)


@pytest.fixture
def base_url() -> str:
    """Get base URL from environment or use localhost."""
    return os.environ.get("SPOOLED_BASE_URL", TEST_BASE_URL)


@pytest.fixture
def client(api_key: str, base_url: str) -> Generator[SpooledClient, None, None]:
    """Create a SpooledClient for testing."""
    with SpooledClient(api_key=api_key, base_url=base_url) as client:
        yield client


@pytest_asyncio.fixture
async def async_client(api_key: str, base_url: str) -> AsyncGenerator[AsyncSpooledClient, None]:
    """Create an AsyncSpooledClient for testing."""
    async with AsyncSpooledClient(api_key=api_key, base_url=base_url) as client:
        yield client


@pytest.fixture
def mock_api() -> Generator[respx.MockRouter, None, None]:
    """Create a mock API router."""
    with respx.mock(base_url=TEST_BASE_URL) as router:
        yield router


@pytest.fixture
def mocked_client(mock_api: respx.MockRouter) -> Generator[SpooledClient, None, None]:
    """Create a SpooledClient with mocked API."""
    with SpooledClient(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
        yield client


@pytest.fixture
def fast_retry_config() -> RetryConfig:
    """Create a fast retry config for tests."""
    return RetryConfig(
        max_retries=2,
        base_delay=0.01,  # 10ms
        max_delay=0.1,    # 100ms
        jitter=False,
    )


@pytest.fixture
def disabled_circuit_breaker() -> CircuitBreakerConfig:
    """Create a disabled circuit breaker config for tests."""
    return CircuitBreakerConfig(enabled=False)


@pytest.fixture
def fast_circuit_breaker() -> CircuitBreakerConfig:
    """Create a fast circuit breaker config for tests."""
    return CircuitBreakerConfig(
        enabled=True,
        failure_threshold=2,
        success_threshold=1,
        timeout=0.1,  # 100ms
    )

