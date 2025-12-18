"""Unit tests for resource classes."""

from __future__ import annotations

import httpx
import pytest
import respx

from spooled import SpooledClient

# Test constants
API_KEY = "sk_test_xxxxxxxxxxxxxxxxxxxx"
BASE_URL = "http://localhost:8080"


class TestJobsResourceComplete:
    """Comprehensive tests for Jobs resource."""

    @respx.mock
    def test_create_job_with_all_options(self) -> None:
        """Test creating a job with all options."""
        respx.post(f"{BASE_URL}/api/v1/jobs").mock(
            return_value=httpx.Response(
                200,
                json={"id": "job_123", "created": True},
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.jobs.create({
                "queue_name": "test",
                "payload": {"key": "value"},
                "priority": 10,
                "max_retries": 5,
                "timeout_seconds": 600,
                "idempotency_key": "unique-123",
                "tags": {"env": "test"},
            })
            assert result.id == "job_123"

    @respx.mock
    def test_create_job_idempotent_hit(self) -> None:
        """Test creating a job that already exists (idempotent)."""
        respx.post(f"{BASE_URL}/api/v1/jobs").mock(
            return_value=httpx.Response(
                200,
                json={"id": "job_existing", "created": False},
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.jobs.create({
                "queue_name": "test",
                "payload": {},
                "idempotency_key": "existing-key",
            })
            assert result.id == "job_existing"
            assert result.created is False

    @respx.mock
    def test_list_jobs_with_filters(self) -> None:
        """Test listing jobs with filters."""
        respx.get(f"{BASE_URL}/api/v1/jobs").mock(
            return_value=httpx.Response(200, json=[])
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            jobs = client.jobs.list({
                "queue_name": "emails",
                "status": "pending",
                "limit": 25,
                "offset": 10,
            })
            assert jobs == []

    @respx.mock
    def test_retry_job(self) -> None:
        """Test retrying a job."""
        respx.post(f"{BASE_URL}/api/v1/jobs/job_failed/retry").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "job_failed",
                    "organization_id": "org_1",
                    "queue_name": "test",
                    "status": "pending",
                    "payload": {},
                    "retry_count": 1,
                    "max_retries": 3,
                    "priority": 0,
                    "timeout_seconds": 300,
                    "created_at": "2024-01-01T00:00:00Z",
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            job = client.jobs.retry("job_failed")
            assert job.status == "pending"
            assert job.retry_count == 1

    @respx.mock
    def test_boost_priority(self) -> None:
        """Test boosting job priority."""
        respx.put(f"{BASE_URL}/api/v1/jobs/job_123/priority").mock(
            return_value=httpx.Response(
                200,
                json={"job_id": "job_123", "old_priority": 0, "new_priority": 10},
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.jobs.boost_priority("job_123", 10)
            assert result.new_priority == 10
            assert result.old_priority == 0

    @respx.mock
    def test_batch_status(self) -> None:
        """Test batch status lookup."""
        respx.get(f"{BASE_URL}/api/v1/jobs/status").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": "job_1", "status": "pending", "queue_name": "test"},
                    {"id": "job_2", "status": "completed", "queue_name": "test"},
                ],
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            statuses = client.jobs.batch_status(["job_1", "job_2"])
            assert len(statuses) == 2
            assert statuses[0].status == "pending"
            assert statuses[1].status == "completed"

    def test_batch_status_empty_list(self) -> None:
        """Test batch status with empty list."""
        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            statuses = client.jobs.batch_status([])
            assert statuses == []

    def test_batch_status_too_many(self) -> None:
        """Test batch status rejects > 100 IDs."""
        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            with pytest.raises(ValueError, match="Maximum 100"):
                client.jobs.batch_status([f"job_{i}" for i in range(101)])

    @respx.mock
    def test_bulk_enqueue(self) -> None:
        """Test bulk enqueue."""
        respx.post(f"{BASE_URL}/api/v1/jobs/bulk").mock(
            return_value=httpx.Response(
                200,
                json={
                    "succeeded": [
                        {"index": 0, "job_id": "job_1", "created": True},
                        {"index": 1, "job_id": "job_2", "created": True},
                    ],
                    "failed": [],
                    "total": 2,
                    "success_count": 2,
                    "failure_count": 0,
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.jobs.bulk_enqueue({
                "queue_name": "test",
                "jobs": [
                    {"payload": {"n": 1}},
                    {"payload": {"n": 2}},
                ],
            })
            assert result.success_count == 2
            assert len(result.succeeded) == 2

    @respx.mock
    def test_claim_jobs(self) -> None:
        """Test claiming jobs."""
        respx.post(f"{BASE_URL}/api/v1/jobs/claim").mock(
            return_value=httpx.Response(
                200,
                json={
                    "jobs": [
                        {
                            "id": "job_123",
                            "queue_name": "test",
                            "payload": {"key": "value"},
                            "retry_count": 0,
                            "max_retries": 3,
                            "timeout_seconds": 300,
                        },
                    ],
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.jobs.claim({
                "queue_name": "test",
                "worker_id": "worker_1",
                "limit": 5,
            })
            assert len(result.jobs) == 1
            assert result.jobs[0].id == "job_123"

    @respx.mock
    def test_complete_job(self) -> None:
        """Test completing a job."""
        respx.post(f"{BASE_URL}/api/v1/jobs/job_123/complete").mock(
            return_value=httpx.Response(200, json={"success": True})
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.jobs.complete("job_123", {
                "worker_id": "worker_1",
                "result": {"processed": True},
            })
            assert result.success is True

    @respx.mock
    def test_fail_job(self) -> None:
        """Test failing a job."""
        respx.post(f"{BASE_URL}/api/v1/jobs/job_123/fail").mock(
            return_value=httpx.Response(200, json={"success": True})
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.jobs.fail("job_123", {
                "worker_id": "worker_1",
                "error": "Processing failed",
            })
            assert result.success is True

    @respx.mock
    def test_job_heartbeat(self) -> None:
        """Test job heartbeat."""
        respx.post(f"{BASE_URL}/api/v1/jobs/job_123/heartbeat").mock(
            return_value=httpx.Response(204)
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            # Should not raise
            client.jobs.heartbeat("job_123", {
                "worker_id": "worker_1",
                "lease_duration_secs": 60,
            })


class TestDlqResourceComplete:
    """Tests for DLQ resource."""

    @respx.mock
    def test_list_dlq(self) -> None:
        """Test listing DLQ jobs."""
        respx.get(f"{BASE_URL}/api/v1/jobs/dlq").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "job_dlq_1",
                        "queue_name": "test",
                        "status": "deadletter",
                        "priority": 0,
                        "retry_count": 3,
                        "created_at": "2024-01-01T00:00:00Z",
                    },
                ],
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            jobs = client.jobs.dlq.list()
            assert len(jobs) == 1
            assert jobs[0].status == "deadletter"

    @respx.mock
    def test_retry_dlq(self) -> None:
        """Test retrying DLQ jobs."""
        respx.post(f"{BASE_URL}/api/v1/jobs/dlq/retry").mock(
            return_value=httpx.Response(
                200,
                json={"retried_count": 3, "job_ids": ["j1", "j2", "j3"]},
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.jobs.dlq.retry({"queue_name": "test", "limit": 10})
            assert result.retried_count == 3

    @respx.mock
    def test_purge_dlq(self) -> None:
        """Test purging DLQ."""
        respx.post(f"{BASE_URL}/api/v1/jobs/dlq/purge").mock(
            return_value=httpx.Response(200, json={"purged_count": 5})
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.jobs.dlq.purge({"queue_name": "test"})
            assert result.purged_count == 5


class TestQueuesResourceComplete:
    """Comprehensive tests for Queues resource."""

    @respx.mock
    def test_list_queues(self) -> None:
        """Test listing queues."""
        respx.get(f"{BASE_URL}/api/v1/queues").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"queue_name": "emails", "max_retries": 3, "default_timeout": 300, "enabled": True},
                    {"queue_name": "tasks", "max_retries": 5, "default_timeout": 600, "enabled": False},
                ],
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            queues = client.queues.list()
            assert len(queues) == 2
            assert queues[0].queue_name == "emails"
            assert queues[1].enabled is False

    @respx.mock
    def test_update_queue_config(self) -> None:
        """Test updating queue config."""
        respx.put(f"{BASE_URL}/api/v1/queues/test/config").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "q_1",
                    "organization_id": "org_1",
                    "queue_name": "test",
                    "max_retries": 5,
                    "default_timeout": 600,
                    "enabled": True,
                    "settings": {},
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            queue = client.queues.update_config("test", {
                "max_retries": 5,
                "default_timeout": 600,
            })
            assert queue.max_retries == 5

    @respx.mock
    def test_get_queue_stats(self) -> None:
        """Test getting queue stats."""
        respx.get(f"{BASE_URL}/api/v1/queues/test/stats").mock(
            return_value=httpx.Response(
                200,
                json={
                    "queue_name": "test",
                    "pending_jobs": 10,
                    "processing_jobs": 2,
                    "completed_jobs_24h": 100,
                    "failed_jobs_24h": 5,
                    "avg_processing_time_ms": 1500.5,
                    "active_workers": 3,
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            stats = client.queues.get_stats("test")
            assert stats.pending_jobs == 10
            assert stats.avg_processing_time_ms == 1500.5

    @respx.mock
    def test_pause_queue(self) -> None:
        """Test pausing a queue."""
        respx.post(f"{BASE_URL}/api/v1/queues/test/pause").mock(
            return_value=httpx.Response(
                200,
                json={
                    "queue_name": "test",
                    "paused": True,
                    "paused_at": "2024-01-01T00:00:00Z",
                    "reason": "maintenance",
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.queues.pause("test", reason="maintenance")
            assert result.paused is True
            assert result.reason == "maintenance"

    @respx.mock
    def test_resume_queue(self) -> None:
        """Test resuming a queue."""
        respx.post(f"{BASE_URL}/api/v1/queues/test/resume").mock(
            return_value=httpx.Response(
                200,
                json={
                    "queue_name": "test",
                    "resumed": True,
                    "paused_duration_secs": 3600,
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.queues.resume("test")
            assert result.resumed is True
            assert result.paused_duration_secs == 3600

    @respx.mock
    def test_delete_queue(self) -> None:
        """Test deleting a queue."""
        respx.delete(f"{BASE_URL}/api/v1/queues/test").mock(
            return_value=httpx.Response(204)
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            client.queues.delete("test")  # Should not raise


class TestWorkersResourceComplete:
    """Comprehensive tests for Workers resource."""

    @respx.mock
    def test_register_worker(self) -> None:
        """Test registering a worker."""
        respx.post(f"{BASE_URL}/api/v1/workers/register").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "worker_123",
                    "queue_name": "test",
                    "lease_duration_secs": 30,
                    "heartbeat_interval_secs": 10,
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.workers.register({
                "queue_name": "test",
                "hostname": "worker-1.local",
                "max_concurrency": 10,
            })
            assert result.id == "worker_123"
            assert result.heartbeat_interval_secs == 10

    @respx.mock
    def test_worker_heartbeat(self) -> None:
        """Test worker heartbeat."""
        respx.post(f"{BASE_URL}/api/v1/workers/worker_123/heartbeat").mock(
            return_value=httpx.Response(204)
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            client.workers.heartbeat("worker_123", {
                "current_jobs": 5,
                "status": "healthy",
            })

    @respx.mock
    def test_deregister_worker(self) -> None:
        """Test deregistering a worker."""
        respx.post(f"{BASE_URL}/api/v1/workers/worker_123/deregister").mock(
            return_value=httpx.Response(204)
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            client.workers.deregister("worker_123")


class TestSchedulesResourceComplete:
    """Comprehensive tests for Schedules resource."""

    @respx.mock
    def test_create_schedule(self) -> None:
        """Test creating a schedule."""
        respx.post(f"{BASE_URL}/api/v1/schedules").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "sch_123",
                    "name": "Daily Job",
                    "cron_expression": "0 9 * * *",
                    "next_run_at": "2024-01-02T09:00:00Z",
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.schedules.create({
                "name": "Daily Job",
                "cron_expression": "0 9 * * *",
                "timezone": "UTC",
                "queue_name": "tasks",
                "payload_template": {"action": "run"},
            })
            assert result.id == "sch_123"

    @respx.mock
    def test_trigger_schedule(self) -> None:
        """Test manually triggering a schedule."""
        respx.post(f"{BASE_URL}/api/v1/schedules/sch_123/trigger").mock(
            return_value=httpx.Response(
                200,
                json={"job_id": "job_triggered", "triggered_at": "2025-01-01T00:00:00Z"},
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.schedules.trigger("sch_123")
            assert result.job_id == "job_triggered"


class TestWebhooksResourceComplete:
    """Comprehensive tests for Webhooks resource."""

    @respx.mock
    def test_create_webhook(self) -> None:
        """Test creating a webhook."""
        respx.post(f"{BASE_URL}/api/v1/outgoing-webhooks").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "wh_123",
                    "organization_id": "org_1",
                    "name": "Notifications",
                    "url": "https://example.com/webhook",
                    "events": ["job.completed"],
                    "enabled": True,
                    "failure_count": 0,
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            webhook = client.webhooks.create({
                "name": "Notifications",
                "url": "https://example.com/webhook",
                "events": ["job.completed"],
            })
            assert webhook.id == "wh_123"

    @respx.mock
    def test_test_webhook(self) -> None:
        """Test testing a webhook."""
        respx.post(f"{BASE_URL}/api/v1/outgoing-webhooks/wh_123/test").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "status_code": 200,
                    "response_time_ms": 150,
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.webhooks.test("wh_123")
            assert result.success is True
            assert result.status_code == 200


class TestAuthResourceComplete:
    """Comprehensive tests for Auth resource."""

    @respx.mock
    def test_login(self) -> None:
        """Test login."""
        respx.post(f"{BASE_URL}/api/v1/auth/login").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "eyJ...",
                    "refresh_token": "eyJ...",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "refresh_expires_in": 86400,
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.auth.login({"api_key": API_KEY})
            assert result.token_type == "Bearer"
            assert result.expires_in == 3600

    @respx.mock
    def test_refresh_token(self) -> None:
        """Test refreshing token."""
        respx.post(f"{BASE_URL}/api/v1/auth/refresh").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "eyJ_new...",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.auth.refresh({"refresh_token": "eyJ..."})
            assert result.access_token == "eyJ_new..."

    @respx.mock
    def test_get_me(self) -> None:
        """Test getting current user info."""
        respx.get(f"{BASE_URL}/api/v1/auth/me").mock(
            return_value=httpx.Response(
                200,
                json={
                    "organization_id": "org_1",
                    "api_key_id": "key_1",
                    "queues": ["emails", "tasks"],
                    "issued_at": "2024-01-01T00:00:00Z",
                    "expires_at": "2024-01-01T01:00:00Z",
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.auth.me()
            assert result.organization_id == "org_1"
            assert "emails" in result.queues
