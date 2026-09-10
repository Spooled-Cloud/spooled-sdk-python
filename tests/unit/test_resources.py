"""Unit tests for resource classes."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from spooled import SpooledClient

# Test constants
API_KEY = "sp_test_xxxxxxxxxxxxxxxxxxxx"
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
            result = client.jobs.create(
                {
                    "queue_name": "test",
                    "payload": {"key": "value"},
                    "priority": 10,
                    "max_retries": 5,
                    "timeout_seconds": 600,
                    "idempotency_key": "unique-123",
                    "tags": {"env": "test"},
                }
            )
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
            result = client.jobs.create(
                {
                    "queue_name": "test",
                    "payload": {},
                    "idempotency_key": "existing-key",
                }
            )
            assert result.id == "job_existing"
            assert result.created is False

    @respx.mock
    def test_list_jobs_with_filters(self) -> None:
        """Test listing jobs with filters."""
        respx.get(f"{BASE_URL}/api/v1/jobs").mock(return_value=httpx.Response(200, json=[]))

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            jobs = client.jobs.list(
                {
                    "queue_name": "emails",
                    "status": "pending",
                    "limit": 25,
                    "offset": 10,
                }
            )
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
                    {
                        "id": "job_1",
                        "status": "pending",
                        "queue_name": "test",
                        "retry_count": 0,
                        "created_at": "2024-01-01T00:00:00Z",
                    },
                    {
                        "id": "job_2",
                        "status": "completed",
                        "queue_name": "test",
                        "retry_count": 3,
                        "created_at": "2024-01-01T00:00:00Z",
                        "completed_at": "2024-01-01T00:01:00Z",
                    },
                ],
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            statuses = client.jobs.batch_status(["job_1", "job_2"])
            assert len(statuses) == 2
            assert statuses[0].status == "pending"
            assert statuses[0].retry_count == 0
            assert statuses[1].status == "completed"
            assert statuses[1].retry_count == 3
            assert statuses[1].completed_at is not None

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
            result = client.jobs.bulk_enqueue(
                {
                    "queue_name": "test",
                    "jobs": [
                        {"payload": {"n": 1}},
                        {"payload": {"n": 2}},
                    ],
                }
            )
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
            result = client.jobs.claim(
                {
                    "queue_name": "test",
                    "worker_id": "worker_1",
                    "limit": 5,
                }
            )
            assert len(result.jobs) == 1
            assert result.jobs[0].id == "job_123"

    @respx.mock
    def test_complete_job(self) -> None:
        """Test completing a job."""
        respx.post(f"{BASE_URL}/api/v1/jobs/job_123/complete").mock(
            return_value=httpx.Response(200, json={"success": True})
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.jobs.complete(
                "job_123",
                {
                    "worker_id": "worker_1",
                    "result": {"processed": True},
                },
            )
            assert result.success is True

    @respx.mock
    def test_fail_job(self) -> None:
        """Test failing a job."""
        respx.post(f"{BASE_URL}/api/v1/jobs/job_123/fail").mock(
            return_value=httpx.Response(200, json={"success": True})
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.jobs.fail(
                "job_123",
                {
                    "worker_id": "worker_1",
                    "error": "Processing failed",
                },
            )
            assert result.success is True

    @respx.mock
    def test_job_heartbeat(self) -> None:
        """Test job heartbeat."""
        respx.post(f"{BASE_URL}/api/v1/jobs/job_123/heartbeat").mock(
            return_value=httpx.Response(204)
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            # Should not raise
            client.jobs.heartbeat(
                "job_123",
                {
                    "worker_id": "worker_1",
                    "lease_duration_secs": 60,
                },
            )


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
        route = respx.post(f"{BASE_URL}/api/v1/jobs/dlq/purge").mock(
            return_value=httpx.Response(200, json={"purged_count": 5})
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.jobs.dlq.purge({"queue_name": "test"})
            assert result.purged_count == 5
        body = json.loads(route.calls.last.request.content)
        assert body["confirm"] is True
        assert body["queue_name"] == "test"
        assert "older_than_days" not in body
        assert "job_ids" not in body

    @respx.mock
    def test_purge_dlq_maps_older_than_days_to_older_than(self) -> None:
        """Backend PurgeDlqRequest.older_than is a datetime, not a day count."""
        route = respx.post(f"{BASE_URL}/api/v1/jobs/dlq/purge").mock(
            return_value=httpx.Response(200, json={"purged_count": 1})
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            client.jobs.dlq.purge({"queue_name": "test", "older_than_days": 7})
        body = json.loads(route.calls.last.request.content)
        assert "older_than_days" not in body
        assert "older_than" in body
        assert body["confirm"] is True


class TestQueuesResourceComplete:
    """Comprehensive tests for Queues resource."""

    @respx.mock
    def test_list_queues(self) -> None:
        """Test listing queues."""
        respx.get(f"{BASE_URL}/api/v1/queues").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "queue_name": "emails",
                        "max_retries": 3,
                        "default_timeout": 300,
                        "enabled": True,
                    },
                    {
                        "queue_name": "tasks",
                        "max_retries": 5,
                        "default_timeout": 600,
                        "enabled": False,
                    },
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
            queue = client.queues.update_config(
                "test",
                {
                    "max_retries": 5,
                    "default_timeout": 600,
                },
            )
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
        route = respx.delete(f"{BASE_URL}/api/v1/queues/test").mock(
            return_value=httpx.Response(204)
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            client.queues.delete("test")  # Should not raise
        assert route.calls.last.request.url.params.get("delete_jobs") is None

    @respx.mock
    def test_delete_queue_sends_delete_jobs_query(self) -> None:
        """DELETE /queues/{name}?delete_jobs=true deletes jobs; omit 409s if busy."""
        captured: dict[str, str | None] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["delete_jobs"] = request.url.params.get("delete_jobs")
            return httpx.Response(204)

        respx.delete(f"{BASE_URL}/api/v1/queues/test").mock(side_effect=handler)

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            client.queues.delete("test", delete_jobs=True)
        assert captured.get("delete_jobs") == "true"


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
            result = client.workers.register(
                {
                    "queue_name": "test",
                    "hostname": "worker-1.local",
                    "max_concurrency": 10,
                }
            )
            assert result.id == "worker_123"
            assert result.heartbeat_interval_secs == 10

    @respx.mock
    def test_register_worker_with_stable_id(self) -> None:
        """Test a stable worker_id is forwarded and omitted when unset."""
        sent: list[dict[str, object]] = []

        def record(request: httpx.Request) -> httpx.Response:
            sent.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "id": "worker-1",
                    "queue_name": "test",
                    "lease_duration_secs": 30,
                    "heartbeat_interval_secs": 10,
                },
            )

        respx.post(f"{BASE_URL}/api/v1/workers/register").mock(side_effect=record)

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            client.workers.register(
                {"queue_name": "test", "hostname": "h", "worker_id": "worker-1"}
            )
            client.workers.register({"queue_name": "test", "hostname": "h"})

        assert sent[0]["worker_id"] == "worker-1"
        assert "worker_id" not in sent[1]

    @respx.mock
    def test_worker_heartbeat(self) -> None:
        """Test worker heartbeat."""
        respx.post(f"{BASE_URL}/api/v1/workers/worker_123/heartbeat").mock(
            return_value=httpx.Response(204)
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            client.workers.heartbeat(
                "worker_123",
                {
                    "current_jobs": 5,
                    "status": "healthy",
                },
            )

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
            result = client.schedules.create(
                {
                    "name": "Daily Job",
                    "cron_expression": "0 9 * * *",
                    "timezone": "UTC",
                    "queue_name": "tasks",
                    "payload_template": {"action": "run"},
                }
            )
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
            webhook = client.webhooks.create(
                {
                    "name": "Notifications",
                    "url": "https://example.com/webhook",
                    "events": ["job.completed"],
                }
            )
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

    @respx.mock
    def test_retry_delivery_posts_retry_id_not_deliveries_retry(self) -> None:
        """POST /outgoing-webhooks/{id}/retry/{delivery_id}, body is success/message."""
        route = respx.post(f"{BASE_URL}/api/v1/outgoing-webhooks/wh_123/retry/del_1").mock(
            return_value=httpx.Response(
                200,
                json={"success": True, "message": "Delivery retried successfully"},
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.webhooks.retry_delivery("wh_123", "del_1")

        assert route.called
        assert result.success is True
        assert "retried" in result.message

    @respx.mock
    def test_update_webhook_secret_states(self) -> None:
        """Test omit keeps the secret while explicit None clears it."""
        sent: list[dict[str, object]] = []

        def record(request: httpx.Request) -> httpx.Response:
            sent.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "id": "wh_123",
                    "organization_id": "org_1",
                    "name": "Notifications",
                    "url": "https://example.com/webhook",
                    "events": ["job.completed"],
                    "enabled": False,
                    "failure_count": 20,
                    "last_status": "auto_disabled",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                },
            )

        respx.put(f"{BASE_URL}/api/v1/outgoing-webhooks/wh_123").mock(side_effect=record)

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            webhook = client.webhooks.update("wh_123", {"name": "Renamed"})
            assert webhook.last_status == "auto_disabled"

            client.webhooks.update("wh_123", {"secret": None})
            client.webhooks.update("wh_123", {"secret": "whsec_new"})

        assert sent[0] == {"name": "Renamed"}
        assert sent[1] == {"secret": None}
        assert sent[2] == {"secret": "whsec_new"}


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

    @respx.mock
    def test_check_email_hits_check_email_not_email_check(self) -> None:
        """Backend route is GET /auth/check-email; /auth/email/check does not exist."""
        respx.get(f"{BASE_URL}/api/v1/auth/check-email").mock(
            return_value=httpx.Response(
                200,
                json={
                    "available": True,
                    "exists": False,
                    "signup_enabled": True,
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.auth.check_email("new@example.com")
            assert result.exists is False
            assert result.available is True
            assert result.signup_enabled is True

    @respx.mock
    def test_start_email_login_maps_email_sent_to(self) -> None:
        """POST /auth/email/start returns email_sent_to, not email_to."""
        respx.post(f"{BASE_URL}/api/v1/auth/email/start").mock(
            return_value=httpx.Response(
                200,
                json={
                    "message": "Login code sent to your email",
                    "email_sent_to": "n***@example.com",
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.auth.start_email_login("new@example.com")
            assert result.message == "Login code sent to your email"
            assert result.email_sent_to == "n***@example.com"

    @respx.mock
    def test_logout_sends_refresh_token(self) -> None:
        """Without refresh_token in the body, /auth/refresh still mints a pair."""
        route = respx.post(f"{BASE_URL}/api/v1/auth/logout").mock(return_value=httpx.Response(204))

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL, refresh_token="rt_1") as client:
            client.auth.logout()

        assert route.called
        body = json.loads(route.calls.last.request.content)
        assert body == {"refresh_token": "rt_1"}

    @respx.mock
    def test_logout_prefers_explicit_refresh_token(self) -> None:
        route = respx.post(f"{BASE_URL}/api/v1/auth/logout").mock(return_value=httpx.Response(204))

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL, refresh_token="rt_stored") as client:
            client.auth.logout("rt_explicit")

        body = json.loads(route.calls.last.request.content)
        assert body == {"refresh_token": "rt_explicit"}


class TestOrganizationsResource:
    """Organization routes must match the backend contract."""

    @respx.mock
    def test_check_slug_maps_suggestion_not_slug(self) -> None:
        """GET /organizations/check-slug returns suggestion/valid/error, not slug."""
        respx.get(f"{BASE_URL}/api/v1/organizations/check-slug").mock(
            return_value=httpx.Response(
                200,
                json={
                    "available": False,
                    "valid": True,
                    "suggestion": "acme-2",
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.organizations.check_slug("acme")
            assert result.available is False
            assert result.valid is True
            assert result.suggestion == "acme-2"
            assert result.error is None
            assert not hasattr(result, "slug")


class TestWorkflowsResource:
    """GET /workflows/{id} is WorkflowDetailResponse, not the list summary."""

    @respx.mock
    def test_create_keeps_status(self) -> None:
        """POST /workflows returns status along with workflow_id and job_ids."""
        respx.post(f"{BASE_URL}/api/v1/workflows").mock(
            return_value=httpx.Response(
                201,
                json={
                    "workflow_id": "wf_1",
                    "job_ids": [{"key": "extract", "job_id": "job_1"}],
                    "status": "pending",
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            created = client.workflows.create(
                {
                    "name": "ETL",
                    "jobs": [
                        {
                            "key": "extract",
                            "queue_name": "etl",
                            "payload": {"step": 1},
                        }
                    ],
                }
            )
        assert created.workflow_id == "wf_1"
        assert created.status == "pending"
        assert created.job_ids[0].job_id == "job_1"

    @respx.mock
    def test_get_maps_progress_counts(self) -> None:
        respx.get(f"{BASE_URL}/api/v1/workflows/wf_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "wf_1",
                    "name": "ETL",
                    "status": "running",
                    "created_at": "2024-01-01T00:00:00Z",
                    "jobs": [
                        {"id": "job_1", "queue": "etl", "status": "completed"},
                        {"id": "job_2", "queue": "etl", "status": "pending"},
                    ],
                    "progress": {
                        "total": 2,
                        "completed": 1,
                        "failed": 0,
                        "pending": 1,
                        "processing": 0,
                    },
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            got = client.workflows.get("wf_1")
            assert got.total_jobs == 2
            assert got.completed_jobs == 1
            assert got.failed_jobs == 0
            assert got.progress_percent == 50.0


class TestWorkflowJobsResource:
    """Workflow jobs must use GET /workflows/{id}; /jobs subpaths do not exist."""

    @respx.mock
    def test_list_jobs_from_workflow_detail(self) -> None:
        respx.get(f"{BASE_URL}/api/v1/workflows/wf_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "wf_1",
                    "name": "ETL",
                    "status": "running",
                    "created_at": "2024-01-01T00:00:00Z",
                    "jobs": [
                        {
                            "id": "job_1",
                            "organization_id": "org_1",
                            "queue": "etl",
                            "payload": {"step": "extract"},
                            "status": "completed",
                            "priority": 0,
                            "attempt": 1,
                            "max_retries": 3,
                            "timeout_ms": 30000,
                            "created_at": "2024-01-01T00:00:00Z",
                            "workflow_id": "wf_1",
                            "result": [1, 2, 3],
                            "metadata": {"tag": "urgent"},
                        },
                        {
                            "id": "job_2",
                            "organization_id": "org_1",
                            "queue": "etl",
                            "payload": {"step": "transform"},
                            "status": "pending",
                            "priority": 0,
                            "attempt": 0,
                            "max_retries": 3,
                            "timeout_ms": 60000,
                            "created_at": "2024-01-01T00:00:00Z",
                            "workflow_id": "wf_1",
                        },
                    ],
                    "dependencies": [
                        {
                            "parent_job_id": "job_1",
                            "child_job_id": "job_2",
                            "dependency_type": "all",
                        }
                    ],
                    "progress": {
                        "total": 2,
                        "completed": 1,
                        "failed": 0,
                        "pending": 1,
                        "processing": 0,
                    },
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            jobs = client.workflows.jobs.list("wf_1")
            assert len(jobs) == 2
            assert jobs[0].queue_name == "etl"
            assert jobs[0].timeout_seconds == 30
            assert jobs[0].result == [1, 2, 3]
            assert jobs[0].metadata == {"tag": "urgent"}
            assert jobs[1].depends_on == ["job_1"]
            one = client.workflows.jobs.get("wf_1", "job_2")
            assert one.id == "job_2"

    @respx.mock
    def test_list_jobs_keeps_non_object_payload(self) -> None:
        respx.get(f"{BASE_URL}/api/v1/workflows/wf_1").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "wf_1",
                    "name": "ETL",
                    "status": "running",
                    "created_at": "2024-01-01T00:00:00Z",
                    "jobs": [
                        {
                            "id": "job_1",
                            "queue": "etl",
                            "payload": "plain-string",
                            "status": "completed",
                            "priority": 0,
                            "attempt": 1,
                            "max_retries": 3,
                            "created_at": "2024-01-01T00:00:00Z",
                            "workflow_id": "wf_1",
                        }
                    ],
                    "dependencies": [],
                    "progress": {
                        "total": 1,
                        "completed": 1,
                        "failed": 0,
                        "pending": 0,
                        "processing": 0,
                    },
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            jobs = client.workflows.jobs.list("wf_1")
            assert len(jobs) == 1
            assert jobs[0].payload == "plain-string"

    @respx.mock
    def test_add_dependencies_sends_depends_on(self) -> None:
        def _handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content.decode())
            assert body["depends_on"] == ["job_1"]
            assert body["dependency_mode"] == "all"
            assert "dependency_job_ids" not in body
            return httpx.Response(
                200,
                json={"dependencies_added": 1, "dependencies_met": False},
            )

        respx.post(f"{BASE_URL}/api/v1/jobs/job_2/dependencies").mock(side_effect=_handler)

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.workflows.jobs.add_dependencies(
                "job_2", {"dependency_job_ids": ["job_1"]}
            )
            assert result.added_count == 1
            assert result.dependencies_met is False

    @respx.mock
    def test_get_dependencies_maps_backend_shape(self) -> None:
        respx.get(f"{BASE_URL}/api/v1/jobs/job_2/dependencies").mock(
            return_value=httpx.Response(
                200,
                json={
                    "job_id": "job_2",
                    "dependencies": [
                        {
                            "job_id": "job_1",
                            "queue_name": "etl",
                            "status": "completed",
                        }
                    ],
                    "dependents": [
                        {
                            "job_id": "job_3",
                            "queue_name": "etl",
                            "status": "pending",
                        }
                    ],
                    "dependencies_met": True,
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            got = client.workflows.jobs.get_dependencies("job_2")
            assert got.job_id == "job_2"
            assert got.dependencies_met is True
            assert got.dependencies[0].queue_name == "etl"
            assert got.dependencies[0].completed is True
            assert got.dependents[0].completed is False


class TestAdminResource:
    @respx.mock
    def test_delete_organization_sends_hard_delete_query(self) -> None:
        captured: dict[str, str | None] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["hard_delete"] = request.url.params.get("hard_delete")
            captured["hard"] = request.url.params.get("hard")
            return httpx.Response(204)

        respx.delete(f"{BASE_URL}/api/v1/admin/organizations/org_1").mock(side_effect=handler)

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL, admin_key="adminkey") as client:
            client.admin.delete_organization("org_1", hard=True)

        assert captured.get("hard_delete") == "true"
        assert captured.get("hard") is None

    @respx.mock
    def test_list_organizations_reads_wrapped_payload(self) -> None:
        respx.get(f"{BASE_URL}/api/v1/admin/organizations").mock(
            return_value=httpx.Response(
                200,
                json={
                    "organizations": [
                        {
                            "id": "org_1",
                            "name": "Acme",
                            "slug": "acme",
                            "plan_tier": "pro",
                            "created_at": "2024-01-01T00:00:00Z",
                            "updated_at": "2024-01-02T00:00:00Z",
                            "usage": {"jobs_today": 1, "active_jobs": 0},
                        }
                    ],
                    "total": 1,
                    "limit": 50,
                    "offset": 0,
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL, admin_key="adminkey") as client:
            got = client.admin.list_organizations()

        assert len(got) == 1
        assert got[0].id == "org_1"
        assert got[0].plan_tier == "pro"

    @respx.mock
    def test_create_organization_reads_wrapped_payload(self) -> None:
        respx.post(f"{BASE_URL}/api/v1/admin/organizations").mock(
            return_value=httpx.Response(
                201,
                json={
                    "organization": {
                        "id": "org_1",
                        "name": "Acme",
                        "slug": "acme",
                        "plan_tier": "pro",
                        "settings": {},
                        "created_at": "2024-01-01T00:00:00Z",
                        "updated_at": "2024-01-01T00:00:00Z",
                    },
                    "api_key": {
                        "id": "key_1",
                        "key": "sp_live_abc123",
                        "name": "Default API Key",
                        "created_at": "2024-01-01T00:00:00Z",
                    },
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL, admin_key="adminkey") as client:
            got = client.admin.create_organization(
                {"name": "Acme", "slug": "acme", "plan_tier": "pro"}
            )

        assert got.organization.id == "org_1"
        assert got.organization.plan_tier == "pro"
        assert got.api_key.key == "sp_live_abc123"

    @respx.mock
    def test_get_stats_reads_nested_platform_payload(self) -> None:
        respx.get(f"{BASE_URL}/api/v1/admin/stats").mock(
            return_value=httpx.Response(
                200,
                json={
                    "organizations": {
                        "total": 4,
                        "by_plan": [{"plan": "free", "count": 3}],
                        "created_today": 1,
                        "created_this_week": 2,
                    },
                    "jobs": {
                        "total_active": 5,
                        "pending": 2,
                        "processing": 1,
                        "completed_24h": 10,
                        "failed_24h": 0,
                    },
                    "workers": {"total": 3, "healthy": 2, "degraded": 1},
                    "system": {"api_version": "0.1.111", "uptime_seconds": 9},
                },
            )
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL, admin_key="adminkey") as client:
            got = client.admin.get_stats()

        assert got.organizations.total == 4
        assert got.jobs.pending == 2
        assert got.workers.healthy == 2
        assert got.system.api_version == "0.1.111"


class TestIngestResource:
    """POST /webhooks/{org_id}/custom returns {job_id, queue_name, status}."""

    @respx.mock
    def test_custom_maps_job_id_from_webhook_response(self) -> None:
        route = respx.post(f"{BASE_URL}/api/v1/webhooks/org_1/custom").mock(
            return_value=httpx.Response(
                200,
                json={
                    "job_id": "job_1",
                    "queue_name": "events",
                    "status": "pending",
                },
            ),
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.ingest.custom(
                "org_1",
                {"queue_name": "events", "payload": {"ok": True}},
                webhook_token="whk_test",
            )

        assert result.job_id == "job_1"
        assert result.queue_name == "events"
        assert result.status == "pending"
        assert route.called
        assert route.calls.last.request.headers["X-Webhook-Token"] == "whk_test"

    @respx.mock
    def test_custom_accepts_empty_200(self) -> None:
        respx.post(f"{BASE_URL}/api/v1/webhooks/org_1/custom").mock(
            return_value=httpx.Response(200, content=b""),
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.ingest.custom(
                "org_1",
                {"queue_name": "events", "payload": {"ok": True}},
            )

        assert result.job_id is None
        assert result.status is None

    @respx.mock
    def test_custom_accepts_non_object_json_payload(self) -> None:
        route = respx.post(f"{BASE_URL}/api/v1/webhooks/org_1/custom").mock(
            return_value=httpx.Response(
                200,
                json={"job_id": "job_1", "queue_name": "events", "status": "pending"},
            ),
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.ingest.custom(
                "org_1",
                {"queue_name": "events", "payload": "plain-string"},
            )

        assert result.job_id == "job_1"
        assert json.loads(route.calls.last.request.content.decode())["payload"] == "plain-string"
