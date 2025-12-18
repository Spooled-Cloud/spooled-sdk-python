"""Unit tests for SpooledClient."""

from __future__ import annotations

import httpx
import pytest
import respx

from spooled import SpooledClient, SpooledClientConfig
from spooled.errors import NotFoundError


class TestSpooledClient:
    """Tests for SpooledClient."""

    def test_client_initialization(self) -> None:
        """Test client initialization."""
        client = SpooledClient(api_key="sk_test_xxxxxxxxxxxxxxxxxxxx")
        assert client is not None
        assert client.get_config().api_key == "sk_test_xxxxxxxxxxxxxxxxxxxx"
        client.close()

    def test_client_requires_auth(self) -> None:
        """Test that client requires authentication."""
        with pytest.raises(ValueError, match="Either api_key or access_token"):
            SpooledClient()

    def test_client_context_manager(self) -> None:
        """Test client as context manager."""
        with SpooledClient(api_key="sk_test_xxxxxxxxxxxxxxxxxxxx") as client:
            assert client is not None

    def test_client_with_config_object(self) -> None:
        """Test client with config object."""
        config = SpooledClientConfig(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url="https://custom.api.com",
            timeout=60.0,
        )
        client = SpooledClient(config=config)
        assert client.get_config().base_url == "https://custom.api.com"
        assert client.get_config().timeout == 60.0
        client.close()


class TestJobsResource:
    """Tests for Jobs resource."""

    @respx.mock
    def test_create_job(self) -> None:
        """Test creating a job."""
        respx.post("http://localhost:8080/api/v1/jobs").mock(
            return_value=httpx.Response(
                200,
                json={"id": "job_123", "created": True},
            )
        )

        with SpooledClient(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url="http://localhost:8080",
        ) as client:
            result = client.jobs.create({
                "queue_name": "test-queue",
                "payload": {"test": True},
            })
            assert result.id == "job_123"
            assert result.created is True

    @respx.mock
    def test_get_job(self) -> None:
        """Test getting a job."""
        respx.get("http://localhost:8080/api/v1/jobs/job_123").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "job_123",
                    "organization_id": "org_1",
                    "queue_name": "test-queue",
                    "status": "pending",
                    "payload": {"test": True},
                    "retry_count": 0,
                    "max_retries": 3,
                    "priority": 0,
                    "timeout_seconds": 300,
                    "created_at": "2024-01-01T00:00:00Z",
                },
            )
        )

        with SpooledClient(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url="http://localhost:8080",
        ) as client:
            job = client.jobs.get("job_123")
            assert job.id == "job_123"
            assert job.status == "pending"
            assert job.payload == {"test": True}

    @respx.mock
    def test_get_job_not_found(self) -> None:
        """Test getting a non-existent job."""
        respx.get("http://localhost:8080/api/v1/jobs/nonexistent").mock(
            return_value=httpx.Response(
                404,
                json={
                    "code": "not_found",
                    "message": "Job not found",
                },
            )
        )

        with SpooledClient(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url="http://localhost:8080",
        ) as client, pytest.raises(NotFoundError):
            client.jobs.get("nonexistent")

    @respx.mock
    def test_list_jobs(self) -> None:
        """Test listing jobs."""
        respx.get("http://localhost:8080/api/v1/jobs").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "job_1",
                        "queue_name": "test-queue",
                        "status": "pending",
                        "priority": 0,
                        "retry_count": 0,
                        "created_at": "2024-01-01T00:00:00Z",
                    },
                    {
                        "id": "job_2",
                        "queue_name": "test-queue",
                        "status": "completed",
                        "priority": 5,
                        "retry_count": 0,
                        "created_at": "2024-01-01T00:01:00Z",
                    },
                ],
            )
        )

        with SpooledClient(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url="http://localhost:8080",
        ) as client:
            jobs = client.jobs.list()
            assert len(jobs) == 2
            assert jobs[0].id == "job_1"
            assert jobs[1].status == "completed"

    @respx.mock
    def test_cancel_job(self) -> None:
        """Test cancelling a job."""
        respx.delete("http://localhost:8080/api/v1/jobs/job_123").mock(
            return_value=httpx.Response(204)
        )

        with SpooledClient(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url="http://localhost:8080",
        ) as client:
            # Should not raise
            client.jobs.cancel("job_123")

    @respx.mock
    def test_get_job_stats(self) -> None:
        """Test getting job statistics."""
        respx.get("http://localhost:8080/api/v1/jobs/stats").mock(
            return_value=httpx.Response(
                200,
                json={
                    "pending": 10,
                    "scheduled": 5,
                    "processing": 2,
                    "completed": 100,
                    "failed": 3,
                    "deadletter": 1,
                    "cancelled": 0,
                    "total": 121,
                },
            )
        )

        with SpooledClient(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url="http://localhost:8080",
        ) as client:
            stats = client.jobs.get_stats()
            assert stats.pending == 10
            assert stats.total == 121


class TestQueuesResource:
    """Tests for Queues resource."""

    @respx.mock
    def test_list_queues(self) -> None:
        """Test listing queues."""
        respx.get("http://localhost:8080/api/v1/queues").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "queue_name": "emails",
                        "max_retries": 3,
                        "default_timeout": 300,
                        "enabled": True,
                    },
                ],
            )
        )

        with SpooledClient(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url="http://localhost:8080",
        ) as client:
            queues = client.queues.list()
            assert len(queues) == 1
            assert queues[0].queue_name == "emails"


class TestHealthResource:
    """Tests for Health resource."""

    @respx.mock
    def test_health_check(self) -> None:
        """Test health check."""
        respx.get("http://localhost:8080/health").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "healthy",
                    "database": True,
                    "cache": True,
                },
            )
        )

        with SpooledClient(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url="http://localhost:8080",
        ) as client:
            health = client.health.get()
            assert health.status == "healthy"
            assert health.database is True

    @respx.mock
    def test_liveness_check(self) -> None:
        """Test liveness probe."""
        respx.get("http://localhost:8080/health/live").mock(
            return_value=httpx.Response(200)
        )

        with SpooledClient(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url="http://localhost:8080",
        ) as client:
            is_alive = client.health.liveness()
            assert is_alive is True
