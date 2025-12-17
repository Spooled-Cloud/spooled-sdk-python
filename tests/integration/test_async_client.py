"""Integration tests for AsyncSpooledClient."""

from __future__ import annotations

import asyncio
import os

import pytest

from spooled import AsyncSpooledClient

# Skip integration tests if no API key is set
pytestmark = pytest.mark.skipif(
    not os.environ.get("SPOOLED_API_KEY"),
    reason="SPOOLED_API_KEY not set",
)


class TestAsyncClientIntegration:
    """Integration tests for AsyncSpooledClient."""

    @pytest.mark.asyncio
    async def test_async_health_check(self, async_client: AsyncSpooledClient) -> None:
        """Test async health check."""
        health = await async_client.health.get()
        assert health.status in ["healthy", "degraded", "unhealthy"]

    @pytest.mark.asyncio
    async def test_async_create_and_cancel_job(self, async_client: AsyncSpooledClient) -> None:
        """Test async job creation and cancellation."""
        # Create job
        result = await async_client.jobs.create({
            "queue_name": "test-async",
            "payload": {"test": True},
        })
        assert result.id is not None

        # Cancel job
        await async_client.jobs.cancel(result.id)

        # Verify cancelled
        job = await async_client.jobs.get(result.id)
        assert job.status == "cancelled"

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, async_client: AsyncSpooledClient) -> None:
        """Test concurrent async operations."""
        # Run multiple operations concurrently
        results = await asyncio.gather(
            async_client.health.get(),
            async_client.jobs.get_stats(),
            async_client.queues.list(),
        )

        assert len(results) == 3


