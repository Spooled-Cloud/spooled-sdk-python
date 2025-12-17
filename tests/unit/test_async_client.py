"""Unit tests for AsyncSpooledClient."""

from __future__ import annotations

import httpx
import pytest
import respx

from spooled import AsyncSpooledClient


class TestAsyncSpooledClient:
    """Tests for AsyncSpooledClient."""

    @pytest.mark.asyncio
    async def test_client_initialization(self) -> None:
        """Test async client initialization."""
        async with AsyncSpooledClient(api_key="sk_test_xxxxxxxxxxxxxxxxxxxx") as client:
            assert client is not None
            assert client.get_config().api_key == "sk_test_xxxxxxxxxxxxxxxxxxxx"

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_job(self) -> None:
        """Test creating a job asynchronously."""
        respx.post("http://localhost:8080/api/v1/jobs").mock(
            return_value=httpx.Response(
                200,
                json={"id": "job_123", "created": True},
            )
        )

        async with AsyncSpooledClient(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url="http://localhost:8080",
        ) as client:
            result = await client.jobs.create({
                "queue_name": "test-queue",
                "payload": {"test": True},
            })
            assert result.id == "job_123"
            assert result.created is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_job(self) -> None:
        """Test getting a job asynchronously."""
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

        async with AsyncSpooledClient(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url="http://localhost:8080",
        ) as client:
            job = await client.jobs.get("job_123")
            assert job.id == "job_123"
            assert job.status == "pending"

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_queues(self) -> None:
        """Test listing queues asynchronously."""
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

        async with AsyncSpooledClient(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url="http://localhost:8080",
        ) as client:
            queues = await client.queues.list()
            assert len(queues) == 1
            assert queues[0].queue_name == "emails"


