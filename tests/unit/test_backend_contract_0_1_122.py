"""Backend 0.1.122 contract: webhook events/formats, job filters and history,
worker counters, the inbound webhook log, X-Has-More and X-RateLimit-*.

The JSON bodies below have the shape the backend serializes (chrono timestamps,
``serde_json`` nulls), so they parse exactly as production responses do.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import respx
from pydantic import ValidationError as PydanticValidationError

from spooled import AsyncSpooledClient, SpooledClient
from spooled.errors import RateLimitError, create_error_from_response
from spooled.types.common import Page, RateLimitInfo, parse_has_more
from spooled.types.jobs import BatchJobStatus, Job, JobSummary, ListJobsParams
from spooled.types.organizations import Organization, UsageInfo
from spooled.types.webhooks import (
    CreateOutgoingWebhookParams,
    OutgoingWebhook,
    OutgoingWebhookDelivery,
    UpdateOutgoingWebhookParams,
)
from spooled.types.workers import Worker, WorkerSummary
from spooled.types.workflows import WorkflowResponse

API_KEY = "sp_test_xxxxxxxxxxxxxxxxxxxx"
BASE_URL = "http://localhost:8080"

WAVE8_EVENTS = ["job.deadlettered", "job.retried", "workflow.completed", "workflow.failed"]


def webhook_json(**overrides: object) -> dict[str, object]:
    """An OutgoingWebhookSummary as the backend serializes it."""
    body: dict[str, object] = {
        "id": "2b0c4a52-8d0e-4a4b-9f0b-7f0c2f1d9a10",
        "organization_id": "b5c0447d-a063-4e37-bb85-c7d3784bf0ae",
        "name": "alerts",
        "url": "https://example.com/hook",
        "events": WAVE8_EVENTS,
        "format": "slack",
        "enabled": True,
        "failure_count": 0,
        "last_triggered_at": None,
        "last_status": None,
        "created_at": "2026-10-12T04:10:11.482913Z",
        "updated_at": "2026-10-12T04:10:11.482913Z",
    }
    body.update(overrides)
    return body


def query_of(request: httpx.Request) -> dict[str, list[str]]:
    return parse_qs(urlsplit(str(request.url)).query)


# ─────────────────────────────────────────────────────────────────────────────
# Webhooks: new events, format, tolerant reads
# ─────────────────────────────────────────────────────────────────────────────


class TestWebhookEventsAndFormat:
    @respx.mock
    def test_list_get_update_parse_wave8_events(self) -> None:
        """A webhook with a wave-8 event used to make list/get/update raise."""
        respx.get(f"{BASE_URL}/api/v1/outgoing-webhooks").mock(
            return_value=httpx.Response(200, json=[webhook_json()])
        )
        respx.get(f"{BASE_URL}/api/v1/outgoing-webhooks/wh_1").mock(
            return_value=httpx.Response(200, json=webhook_json())
        )
        respx.put(f"{BASE_URL}/api/v1/outgoing-webhooks/wh_1").mock(
            return_value=httpx.Response(200, json=webhook_json(enabled=False))
        )

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            (listed,) = client.webhooks.list()
            assert listed.events == WAVE8_EVENTS
            assert listed.format == "slack"
            assert client.webhooks.get("wh_1").events == WAVE8_EVENTS
            assert client.webhooks.update("wh_1", {"enabled": False}).enabled is False

    def test_unknown_event_format_and_status_still_parse(self) -> None:
        """A value a newer server adds must not break reads."""
        webhook = OutgoingWebhook.model_validate(
            webhook_json(
                events=["job.created", "queue.purged"],
                format="mattermost",
                last_status="throttled",
            )
        )
        assert webhook.events == ["job.created", "queue.purged"]
        assert webhook.format == "mattermost"
        assert webhook.last_status == "throttled"

    def test_format_defaults_to_json_for_older_servers(self) -> None:
        body = webhook_json(events=["job.completed"])
        del body["format"]
        assert OutgoingWebhook.model_validate(body).format == "json"

    def test_delivery_with_unknown_status_parses(self) -> None:
        delivery = OutgoingWebhookDelivery.model_validate(
            {
                "id": "d1",
                "webhook_id": "wh_1",
                "event": "job.retried",
                "payload": {"id": "evt", "event": "job.retried", "data": {}},
                "status": "skipped",
                "status_code": None,
                "response_body": None,
                "error": None,
                "attempts": 0,
                "created_at": "2026-10-12T04:10:11Z",
                "delivered_at": None,
            }
        )
        assert delivery.status == "skipped"

    @respx.mock
    def test_create_sends_new_events_and_format(self) -> None:
        bodies: list[dict[str, object]] = []

        def record(request: httpx.Request) -> httpx.Response:
            bodies.append(json.loads(request.content))
            return httpx.Response(201, json=webhook_json())

        respx.post(f"{BASE_URL}/api/v1/outgoing-webhooks").mock(side_effect=record)
        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            created = client.webhooks.create(
                {
                    "name": "alerts",
                    "url": "https://example.com/hook",
                    "events": WAVE8_EVENTS,
                    "format": "slack",
                }
            )
            client.webhooks.create(
                {"name": "plain", "url": "https://example.com/hook", "events": ["job.failed"]}
            )
        assert created.format == "slack"
        assert bodies[0]["events"] == WAVE8_EVENTS
        assert bodies[0]["format"] == "slack"
        # Omitted format is not sent: the server applies its default (json).
        assert "format" not in bodies[1]

    def test_update_sends_format_only_when_set(self) -> None:
        assert UpdateOutgoingWebhookParams(format="teams").to_payload() == {"format": "teams"}
        assert UpdateOutgoingWebhookParams(events=["workflow.failed"]).to_payload() == {
            "events": ["workflow.failed"]
        }
        assert "format" not in UpdateOutgoingWebhookParams(name="x").to_payload()

    def test_params_reject_unknown_format(self) -> None:
        with pytest.raises(PydanticValidationError):
            CreateOutgoingWebhookParams(
                name="a",
                url="https://example.com/hook",
                events=["job.failed"],
                format="xml",  # type: ignore[arg-type]
            )


# ─────────────────────────────────────────────────────────────────────────────
# Inbound webhook log
# ─────────────────────────────────────────────────────────────────────────────


INBOUND_ROWS = [
    {
        "id": "in_2",
        "provider": "custom",
        "event_type": "order.paid",
        "matched_queue": "orders",
        "job_id": "job_2",
        "status": "duplicate",
        "created_at": "2026-10-12T04:12:00Z",
    },
    {
        "id": "in_1",
        "provider": "custom",
        "event_type": "order.paid",
        "matched_queue": "orders",
        "job_id": None,
        "status": None,
        "created_at": "2026-10-01T00:00:00Z",
    },
]


class TestInboundDeliveries:
    @respx.mock
    def test_lists_with_filters(self) -> None:
        route = respx.get(f"{BASE_URL}/api/v1/webhooks/deliveries").mock(
            return_value=httpx.Response(200, json=INBOUND_ROWS)
        )
        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            rows = client.webhooks.list_inbound_deliveries(
                {
                    "status": "duplicate",
                    "since": datetime(2026, 10, 1, 12, 0, 0),
                    "queue_name": "orders",
                    "limit": 10,
                    "offset": 20,
                }
            )
            unfiltered = client.webhooks.list_inbound_deliveries()

        assert [row.id for row in rows] == ["in_2", "in_1"]
        assert rows[0].status == "duplicate"
        assert rows[0].job_id == "job_2"
        assert rows[1].job_id is None and rows[1].status is None
        assert len(unfiltered) == 2
        query = query_of(route.calls[0].request)
        assert query == {
            "status": ["duplicate"],
            "since": ["2026-10-01T12:00:00+00:00"],
            "queue_name": ["orders"],
            "limit": ["10"],
            "offset": ["20"],
        }
        assert query_of(route.calls[1].request) == {}

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_lists(self) -> None:
        respx.get(f"{BASE_URL}/api/v1/webhooks/deliveries").mock(
            return_value=httpx.Response(200, json=INBOUND_ROWS)
        )
        async with AsyncSpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            rows = await client.webhooks.list_inbound_deliveries({"status": "created"})
        assert rows[0].matched_queue == "orders"


# ─────────────────────────────────────────────────────────────────────────────
# Job list filters, X-Has-More, history
# ─────────────────────────────────────────────────────────────────────────────


def summary_json(job_id: str, status: str = "completed") -> dict[str, object]:
    return {
        "id": job_id,
        "queue_name": "emails",
        "status": status,
        "priority": 0,
        "attempt": 0,
        "max_retries": 3,
        "job_type": "send",
        "last_error": None,
        "created_at": "2026-10-12T04:00:00Z",
        "scheduled_at": None,
        "started_at": None,
        "completed_at": None,
    }


class TestJobListFilters:
    def test_status_forms(self) -> None:
        assert ListJobsParams(status="pending").to_query()["status"] == "pending"
        assert (
            ListJobsParams(status=["completed", "deadletter"]).to_query()["status"]
            == "completed,deadletter"
        )
        assert (
            ListJobsParams.model_validate({"status": "failed, deadletter"}).to_query()["status"]
            == "failed,deadletter"
        )
        assert "status" not in ListJobsParams(status=[]).to_query()
        with pytest.raises(PydanticValidationError):
            ListJobsParams.model_validate({"status": "pending,bogus"})

    def test_times_are_rfc3339(self) -> None:
        after = datetime(2026, 10, 11, 8, 0, 0)
        before = datetime(2026, 10, 12, 8, 0, 0, tzinfo=timezone(timedelta(hours=2)))
        query = ListJobsParams(created_after=after, created_before=before).to_query()
        assert query["created_after"] == "2026-10-11T08:00:00+00:00"
        assert query["created_before"] == "2026-10-12T08:00:00+02:00"
        parsed = ListJobsParams.model_validate({"created_after": "2026-10-11T08:00:00Z"})
        assert parsed.to_query()["created_after"] == "2026-10-11T08:00:00+00:00"

    @respx.mock
    def test_list_sends_filters_and_reads_has_more(self) -> None:
        route = respx.get(f"{BASE_URL}/api/v1/jobs").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json=[summary_json("j1"), summary_json("j2")],
                    headers={"X-Has-More": "true"},
                ),
                httpx.Response(200, json=[summary_json("j3")], headers={"x-has-more": "false"}),
                httpx.Response(200, json=[]),
            ]
        )
        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            first = client.jobs.list(
                {
                    "status": ["completed", "deadletter"],
                    "q": "send",
                    "job_type": "send",
                    "created_after": datetime(2026, 10, 11, tzinfo=timezone.utc),
                    "limit": 2,
                }
            )
            last = client.jobs.list({"offset": 2, "limit": 2})
            old_server = client.jobs.list()

        assert isinstance(first, Page) and isinstance(first, list)
        assert [job.id for job in first] == ["j1", "j2"]
        assert first.has_more is True
        assert last.has_more is False
        assert old_server == [] and old_server.has_more is None
        query = query_of(route.calls[0].request)
        assert query["status"] == ["completed,deadletter"]
        assert query["q"] == ["send"]
        assert query["job_type"] == ["send"]
        assert query["created_after"] == ["2026-10-11T00:00:00+00:00"]
        assert query["limit"] == ["2"]

    @respx.mock
    def test_dlq_list_filters_and_has_more(self) -> None:
        route = respx.get(f"{BASE_URL}/api/v1/jobs/dlq").mock(
            return_value=httpx.Response(
                200, json=[summary_json("d1", "deadletter")], headers={"X-Has-More": "true"}
            )
        )
        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            page = client.jobs.dlq.list({"queue_name": "emails", "job_type": "send", "q": "d"})
        assert page.has_more is True
        assert page[0].status == "deadletter"
        query = query_of(route.calls[0].request)
        assert query["job_type"] == ["send"]
        assert query["q"] == ["d"]

    @respx.mock
    def test_history(self) -> None:
        route = respx.get(f"{BASE_URL}/api/v1/jobs/job_1/history").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "h2",
                        "job_id": "job_1",
                        "event_type": "completed",
                        "worker_id": "worker-a",
                        "details": {"result_size": 12},
                        "created_at": "2026-10-12T04:00:02Z",
                    },
                    {
                        "id": "h1",
                        "job_id": "job_1",
                        "event_type": "created",
                        "worker_id": None,
                        "details": None,
                        "created_at": "2026-10-12T04:00:00Z",
                    },
                ],
                headers={"X-Has-More": "false"},
            )
        )
        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            events = client.jobs.history("job_1", {"order_dir": "desc", "limit": 2})
            client.jobs.history("job_1")

        assert [event.event_type for event in events] == ["completed", "created"]
        assert events[0].worker_id == "worker-a"
        assert events[0].details == {"result_size": 12}
        assert events[1].worker_id is None
        assert events.has_more is False
        assert query_of(route.calls[0].request) == {"order_dir": ["desc"], "limit": ["2"]}
        assert query_of(route.calls[1].request) == {}

    def test_history_params_validate(self) -> None:
        from spooled.types.jobs import JobHistoryParams

        with pytest.raises(PydanticValidationError):
            JobHistoryParams(order_dir="newest")  # type: ignore[arg-type]
        with pytest.raises(PydanticValidationError):
            JobHistoryParams(limit=501)

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_list_and_history(self) -> None:
        respx.get(f"{BASE_URL}/api/v1/jobs").mock(
            return_value=httpx.Response(
                200, json=[summary_json("j1")], headers={"X-Has-More": "true"}
            )
        )
        respx.get(f"{BASE_URL}/api/v1/jobs/dlq").mock(
            return_value=httpx.Response(200, json=[], headers={"X-Has-More": "false"})
        )
        respx.get(f"{BASE_URL}/api/v1/jobs/j1/history").mock(
            return_value=httpx.Response(200, json=[], headers={"X-Has-More": "false"})
        )
        async with AsyncSpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            page = await client.jobs.list({"status": "completed,failed"})
            dlq = await client.jobs.dlq.list()
            history = await client.jobs.history("j1")
        assert page.has_more is True
        assert dlq.has_more is False
        assert history == [] and history.has_more is False


# ─────────────────────────────────────────────────────────────────────────────
# Worker counters
# ─────────────────────────────────────────────────────────────────────────────


class TestWorkerCounters:
    @respx.mock
    def test_list_and_get_carry_counters(self) -> None:
        summary = {
            "id": "w1",
            "queue_name": "emails",
            "hostname": "host-1",
            "status": "healthy",
            "current_jobs": 0,
            "max_concurrency": 5,
            "last_heartbeat": "2026-10-12T04:00:00Z",
            "jobs_processed": 4,
            "jobs_failed": 1,
        }
        detail = {
            "id": "w1",
            "organization_id": "org_1",
            "queue_name": "emails",
            "queue_names": ["emails"],
            "hostname": "host-1",
            "worker_type": "python",
            "max_concurrent_jobs": 5,
            "current_job_count": 0,
            "status": "healthy",
            "last_heartbeat": "2026-10-12T04:00:00Z",
            "metadata": {},
            "version": "1.4.0",
            "created_at": "2026-10-12T03:00:00Z",
            "jobs_processed": 4,
            "jobs_failed": 1,
        }
        respx.get(f"{BASE_URL}/api/v1/workers").mock(
            return_value=httpx.Response(200, json=[summary])
        )
        respx.get(f"{BASE_URL}/api/v1/workers/w1").mock(
            return_value=httpx.Response(200, json=detail)
        )
        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            (listed,) = client.workers.list()
            got = client.workers.get("w1")
        assert (listed.jobs_processed, listed.jobs_failed) == (4, 1)
        assert (got.jobs_processed, got.jobs_failed) == (4, 1)

    def test_counters_absent_on_older_servers(self) -> None:
        worker = WorkerSummary.model_validate(
            {
                "id": "w1",
                "queue_name": "q",
                "hostname": "h",
                "status": "healthy",
                "current_jobs": 0,
                "max_concurrency": 1,
                "last_heartbeat": "2026-10-12T04:00:00Z",
            }
        )
        assert worker.jobs_processed is None and worker.jobs_failed is None


# ─────────────────────────────────────────────────────────────────────────────
# New enum values from the server never fail a response model
# ─────────────────────────────────────────────────────────────────────────────


class TestUnknownEnumValues:
    def test_job_statuses(self) -> None:
        job = Job.model_validate(
            {
                "id": "j",
                "organization_id": "o",
                "queue_name": "q",
                "status": "paused",
                "payload": {},
                "retry_count": 0,
                "max_retries": 3,
                "created_at": "2026-10-12T04:00:00Z",
                "priority": 0,
                "timeout_seconds": 300,
            }
        )
        assert job.status == "paused"
        assert JobSummary.model_validate(summary_json("j", "paused")).status == "paused"
        batch = BatchJobStatus.model_validate(
            {
                "id": "j",
                "status": "paused",
                "queue_name": "q",
                "retry_count": 0,
                "created_at": "2026-10-12T04:00:00Z",
                "completed_at": None,
            }
        )
        assert batch.status == "paused"

    def test_worker_status(self) -> None:
        worker = Worker.model_validate(
            {
                "id": "w",
                "queue_name": "q",
                "hostname": "h",
                "status": "quarantined",
                "last_heartbeat": "2026-10-12T04:00:00Z",
            }
        )
        assert worker.status == "quarantined"

    def test_plan_tier(self) -> None:
        org = Organization.model_validate(
            {
                "id": "o",
                "name": "n",
                "slug": "s",
                "plan_tier": "team",
                "created_at": "2026-10-12T04:00:00Z",
                "updated_at": "2026-10-12T04:00:00Z",
            }
        )
        assert org.plan_tier == "team"
        usage = UsageInfo.model_validate(
            {
                "plan": "team",
                "plan_display_name": "Team",
                "limits": {
                    "tier": "team",
                    "display_name": "Team",
                    "max_jobs_per_day": None,
                    "max_active_jobs": None,
                    "max_queues": None,
                    "max_workers": None,
                    "max_api_keys": None,
                    "max_schedules": None,
                    "max_workflows": None,
                    "max_webhooks": None,
                    "max_payload_size_bytes": 1,
                    "rate_limit_requests_per_second": 1,
                    "rate_limit_burst": 1,
                    "job_retention_days": 1,
                    "history_retention_days": 1,
                },
                "usage": {
                    name: {"current": 0, "limit": None, "percentage": None, "is_disabled": False}
                    for name in (
                        "jobs_today",
                        "active_jobs",
                        "queues",
                        "workers",
                        "api_keys",
                        "schedules",
                        "workflows",
                        "webhooks",
                    )
                },
                "warnings": [],
            }
        )
        assert usage.plan == "team"

    def test_workflow_status(self) -> None:
        workflow = WorkflowResponse.model_validate(
            {
                "id": "wf",
                "name": "n",
                "status": "paused",
                "created_at": "2026-10-12T04:00:00Z",
            }
        )
        assert workflow.status == "paused"


# ─────────────────────────────────────────────────────────────────────────────
# X-RateLimit-* on every response
# ─────────────────────────────────────────────────────────────────────────────


RATE_HEADERS = {
    "X-RateLimit-Limit": "200",
    "X-RateLimit-Remaining": "199",
    "X-RateLimit-Reset": "1791788683",
    "X-RateLimit-Scope": "organization",
}


class TestRateLimitInfo:
    def test_parse(self) -> None:
        info = RateLimitInfo.from_headers(httpx.Headers(RATE_HEADERS))
        assert info is not None
        assert (info.limit, info.remaining, info.scope) == (200, 199, "organization")
        assert info.reset_epoch == 1791788683
        assert info.reset == datetime.fromtimestamp(1791788683, tz=timezone.utc)
        assert RateLimitInfo.from_headers(httpx.Headers({"Content-Type": "x"})) is None

    def test_has_more_parse(self) -> None:
        assert parse_has_more({"x-has-more": "TRUE"}) is True
        assert parse_has_more({"X-Has-More": "false"}) is False
        assert parse_has_more({"X-Has-More": "maybe"}) is None
        assert parse_has_more({}) is None

    @respx.mock
    def test_client_tracks_latest_success_response(self) -> None:
        respx.get(f"{BASE_URL}/api/v1/jobs/stats").mock(
            side_effect=[
                httpx.Response(
                    200,
                    json={
                        "pending": 0,
                        "scheduled": 0,
                        "processing": 0,
                        "completed": 0,
                        "failed": 0,
                        "deadletter": 0,
                        "cancelled": 0,
                        "total": 0,
                    },
                    headers=RATE_HEADERS,
                ),
                httpx.Response(
                    200,
                    json={
                        "pending": 0,
                        "scheduled": 0,
                        "processing": 0,
                        "completed": 0,
                        "failed": 0,
                        "deadletter": 0,
                        "cancelled": 0,
                        "total": 0,
                    },
                    headers={**RATE_HEADERS, "X-RateLimit-Remaining": "198"},
                ),
            ]
        )
        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            assert client.rate_limit is None
            client.jobs.get_stats()
            assert client.rate_limit is not None
            assert client.rate_limit.remaining == 199
            client.jobs.get_stats()
            assert client.rate_limit.remaining == 198
            assert client.rate_limit.scope == "organization"

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_client_tracks_rate_limit(self) -> None:
        respx.get(f"{BASE_URL}/api/v1/jobs/j1/history").mock(
            return_value=httpx.Response(200, json=[], headers=RATE_HEADERS)
        )
        async with AsyncSpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            await client.jobs.history("j1")
            assert client.rate_limit is not None
            assert client.rate_limit.limit == 200

    def test_rate_limit_error_carries_scope(self) -> None:
        error = create_error_from_response(
            429,
            {"error": "rate_limited", "code": "RATE_LIMIT_EXCEEDED", "message": "slow down"},
            "req-1",
            httpx.Headers({**RATE_HEADERS, "Retry-After": "1", "X-RateLimit-Remaining": "0"}),
        )
        assert isinstance(error, RateLimitError)
        assert error.scope == "organization"
        assert error.remaining == 0
        assert error.reset == datetime.fromtimestamp(1791788683, tz=timezone.utc)


class TestMetricsToken:
    @respx.mock
    def test_metrics_token_replaces_api_key(self) -> None:
        """/metrics takes the server's metrics token, not an API key."""
        route = respx.get(f"{BASE_URL}/metrics").mock(
            return_value=httpx.Response(200, text="# HELP up\nup 1\n")
        )
        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            assert client.metrics.get(token="metrics-secret").startswith("# HELP")
            client.metrics.get()
        assert route.calls[0].request.headers["Authorization"] == "Bearer metrics-secret"
        assert route.calls[1].request.headers["Authorization"] == f"Bearer {API_KEY}"
