"""Integration tests for Jobs resource."""

from __future__ import annotations

import os

import pytest

from spooled import SpooledClient

# Skip integration tests if no API key is set
pytestmark = pytest.mark.skipif(
    not os.environ.get("SPOOLED_API_KEY"),
    reason="SPOOLED_API_KEY not set",
)


class TestJobsIntegration:
    """Integration tests for Jobs resource."""

    def test_create_and_get_job(self, client: SpooledClient) -> None:
        """Test creating and retrieving a job."""
        # Create job
        result = client.jobs.create({
            "queue_name": "test-integration",
            "payload": {"test": True, "timestamp": "2024-01-01"},
        })
        assert result.id is not None
        assert result.created is True

        # Get job
        job = client.jobs.get(result.id)
        assert job.status == "pending"
        assert job.payload == {"test": True, "timestamp": "2024-01-01"}

        # Cancel job
        client.jobs.cancel(result.id)

        # Verify cancelled
        job = client.jobs.get(result.id)
        assert job.status == "cancelled"

    def test_list_jobs(self, client: SpooledClient) -> None:
        """Test listing jobs."""
        jobs = client.jobs.list({"limit": 10})
        assert isinstance(jobs, list)

    def test_get_stats(self, client: SpooledClient) -> None:
        """Test getting job statistics."""
        stats = client.jobs.get_stats()
        assert stats.total >= 0
        assert stats.pending >= 0

    def test_bulk_enqueue(self, client: SpooledClient) -> None:
        """Test bulk enqueueing jobs."""
        result = client.jobs.bulk_enqueue({
            "queue_name": "test-bulk",
            "jobs": [
                {"payload": {"index": 1}},
                {"payload": {"index": 2}},
                {"payload": {"index": 3}},
            ],
        })
        assert result.total == 3
        assert result.success_count == 3
        assert result.failure_count == 0

        # Cancel all created jobs
        for succeeded in result.succeeded:
            if succeeded.job_id:
                client.jobs.cancel(succeeded.job_id)
