# API Reference

Complete API reference for the Spooled Python SDK.

## Client Initialization

### SpooledClient (Sync)

```python
from spooled import SpooledClient

# Simple initialization
client = SpooledClient(api_key="sp_live_...")

# With options
client = SpooledClient(
    api_key="sp_live_...",
    base_url="https://api.spooled.cloud",
    timeout=30.0,
    debug=True,
)

# As context manager
with SpooledClient(api_key="sp_live_...") as client:
    # use client
    pass

# gRPC and WebSocket endpoints are separate from base_url. Defaults:
# grpc_address="grpc.spooled.cloud:443"; ws_url is derived from base_url.
client = SpooledClient(
    api_key="sp_live_...",
    grpc_address="grpc.my-company.internal:50051",  # self-hosted gRPC
)

# with_options() derives a client that keeps ALL of this configuration
# (headers, retry, circuit breaker, user agent, timeouts, URLs) and overrides
# only what you pass.
quiet = client.with_options(timeout=5, retry={"max_retries": 0})
```

`client.grpc` dials `grpc_address` (TLS unless the host is local). `client.realtime()`
exchanges the API key for a JWT used **only** by the realtime transport; REST calls
keep authenticating with the API key.

### AsyncSpooledClient (Async)

```python
from spooled import AsyncSpooledClient

# As async context manager
async with AsyncSpooledClient(api_key="sp_live_...") as client:
    result = await client.jobs.create({...})
```

## Jobs

### Create Job

```python
result = client.jobs.create({
    "queue_name": "my-queue",
    "payload": {"key": "value"},
    "priority": 5,
    "max_retries": 3,
    "timeout_seconds": 300,
    "scheduled_at": "2024-01-01T00:00:00Z",  # Optional
    "idempotency_key": "unique-key",  # Optional
    "tags": {"env": "prod"},  # Optional
})
print(result.id, result.created)
```

### Get Job

```python
job = client.jobs.get("job_xxx")
print(job.id, job.status, job.payload)
```

### List Jobs

```python
from datetime import datetime, timezone

jobs = client.jobs.list({
    "queue_name": "my-queue",
    "status": ["pending", "failed"],  # One status, a list, or "pending,failed"
    "tag": "billing",                 # Optional: filter by a single tag
    "q": "inv",                       # Optional: id prefix, queue name or payload.job_type
    "job_type": "send_invoice",       # Optional: exact payload.job_type
    "created_after": datetime(2026, 10, 1, tzinfo=timezone.utc),  # Optional, inclusive
    "created_before": datetime(2026, 10, 2, tzinfo=timezone.utc),  # Optional, exclusive
    "limit": 50,
    "offset": 0,
})
print(len(jobs), jobs.has_more)
```

The result is a `Page`: a plain `list` of `JobSummary` with a `has_more` attribute read
from the `X-Has-More` response header (`True` when another page follows, `None` if the
server did not send it). Page through everything with `offset`:

```python
offset = 0
while True:
    page = client.jobs.list({"status": "failed", "limit": 100, "offset": offset})
    handle(page)
    if not page.has_more:
        break
    offset += len(page)
```

Times are sent as RFC 3339; a naive `datetime` is taken as UTC. An invalid filter value
(unknown status, unparseable time, `created_after >= created_before`) is a 400
`ValidationError` from the API, or a pydantic error before the request for values the
SDK can check itself.

### Job History

```python
events = client.jobs.history("job_xxx")                      # oldest first
latest = client.jobs.history("job_xxx", {"order_dir": "desc", "limit": 20})
for event in events:
    print(event.created_at, event.event_type, event.worker_id, event.details)
print(events.has_more)
```

Each `JobHistoryEvent` has `id`, `job_id`, `event_type` (free-form: `created`,
`claimed`, `completed`, `failed`, ...), `worker_id`, `details` (any JSON) and
`created_at`. `limit` is 1-500 (default 100).

### Worker Endpoints (claim, complete, fail, heartbeat)

```python
claimed = client.jobs.claim({"queue_name": "my-queue", "worker_id": "worker-1", "limit": 1})
for job in claimed.jobs:
    client.jobs.heartbeat(job.id, {"worker_id": "worker-1", "lease_id": job.lease_id})
    client.jobs.complete(job.id, {"worker_id": "worker-1", "lease_id": job.lease_id, "result": {}})
```

`lease_id` is required on `complete`, `fail` and `heartbeat` (the API answers 422
without it) and fences the call to the lease you hold. `SpooledWorker` handles this.

### Cancel Job

```python
client.jobs.cancel("job_xxx")
```

### Retry Job

```python
job = client.jobs.retry("job_xxx")
```

### Boost Priority

```python
result = client.jobs.boost_priority("job_xxx", priority=10)
print(result.old_priority, result.new_priority)
```

### Get Statistics

```python
stats = client.jobs.get_stats()
print(stats.pending, stats.processing, stats.completed)
```

### Batch Status

```python
statuses = client.jobs.batch_status(["job_1", "job_2", "job_3"])
for s in statuses:
    print(s.id, s.status, s.retry_count)
```

### Bulk Enqueue

```python
result = client.jobs.bulk_enqueue({
    "queue_name": "my-queue",
    "jobs": [
        {"payload": {"n": 1}},
        {"payload": {"n": 2}},
    ],
})
print(result.success_count, result.failure_count)
```

### DLQ Operations

```python
# List DLQ jobs (same q/job_type/created_after/created_before/tag filters as
# jobs.list, no status; the result has has_more too)
dlq_jobs = client.jobs.dlq.list({"queue_name": "my-queue"})

# Retry DLQ jobs
result = client.jobs.dlq.retry({"queue_name": "my-queue", "limit": 10})

# Purge DLQ. `confirm` has no default: without a filter a purge deletes up to
# 10 000 dead-lettered jobs of the whole organization, so it must be explicit.
result = client.jobs.dlq.purge({"queue_name": "my-queue", "older_than_days": 7, "confirm": True})
```

## Queues

### List Queues

```python
queues = client.queues.list()
for q in queues:
    print(q.queue_name, q.enabled)
```

### Get Queue

```python
queue = client.queues.get("my-queue")
```

### Update Queue Config

```python
queue = client.queues.update_config("my-queue", {
    "max_retries": 5,
    "default_timeout": 600,
})
```

`max_retries` and `default_timeout` are the defaults for new jobs of the queue. A `rate_limit` field is
accepted and stored, but it is **not enforced**: workers are not throttled by it, so do not rely on it.
Job retries use a fixed delay of `2^n` seconds capped at 60 s; there is no per-queue backoff setting.

### Get Queue Stats

```python
stats = client.queues.get_stats("my-queue")
print(stats.pending_jobs, stats.processing_jobs)
```

### Pause/Resume Queue

```python
client.queues.pause("my-queue", reason="maintenance")
client.queues.resume("my-queue")
```

## Schedules

### Create Schedule

```python
schedule = client.schedules.create({
    "name": "Daily Report",
    "cron_expression": "0 9 * * *",
    "timezone": "UTC",
    "queue_name": "reports",
    "payload_template": {"type": "daily"},
})
```

### List Schedules

```python
schedules = client.schedules.list({"is_active": True})
```

### Update Schedule

```python
schedule = client.schedules.update("sch_xxx", {
    "cron_expression": "0 10 * * *",
})
```

### Pause/Resume Schedule

```python
client.schedules.pause("sch_xxx")
client.schedules.resume("sch_xxx")
```

### Trigger Manually

```python
result = client.schedules.trigger("sch_xxx")
print(result.job_id)
```

## Workflows

### Create Workflow

```python
workflow = client.workflows.create({
    "name": "Data Pipeline",
    "jobs": [
        {"key": "extract", "queue_name": "etl", "payload": {"step": "extract"}},
        {"key": "transform", "queue_name": "etl", "payload": {"step": "transform"}, "depends_on": ["extract"]},
        {"key": "load", "queue_name": "etl", "payload": {"step": "load"}, "depends_on": ["transform"]},
    ],
})
```

### Get Workflow Status

```python
status = client.workflows.get("wf_xxx")
print(status.progress_percent, status.completed_jobs)
```

`client.workflows.jobs.list()` / `.get_status()` return each job's `job_id` and
`status`. Their `key` is `None`: the API does not store job keys, so keep the
`key -> job_id` mapping from `create()` (`workflow.job_ids`) if you need it.

### Cancel Workflow

```python
client.workflows.cancel("wf_xxx")
```

## Workers

```python
for worker in client.workers.list():
    print(worker.id, worker.status, worker.jobs_processed, worker.jobs_failed)
```

`jobs_processed` counts jobs the worker completed and `jobs_failed` the failures it
reported (each retry scheduled or dead-letter it caused); both are `None` on servers that
do not send them. `workers.get(id)` carries them too.

## Webhooks

### Create Outgoing Webhook

```python
webhook = client.webhooks.create({
    "name": "Job Notifications",
    "url": "https://myapp.com/webhooks/spooled",
    "events": ["job.completed", "job.failed", "job.deadlettered"],
    "secret": "whsec_...",  # Optional: signs deliveries with X-Spooled-Signature
})

# Post straight into a chat channel: the URL is the service's incoming-webhook URL
slack = client.webhooks.create({
    "name": "Ops channel",
    "url": "https://hooks.slack.com/services/...",
    "events": ["job.deadlettered", "workflow.failed"],
    "format": "slack",  # json (default), slack, discord or teams
})
```

Events: `job.created`, `job.started`, `job.completed`, `job.failed`, `job.cancelled`,
`job.deadlettered`, `job.retried`, `queue.paused`, `queue.resumed`,
`worker.registered`, `worker.deregistered`, `schedule.triggered`,
`workflow.completed`, `workflow.failed`. Webhook objects read `events` and `format` as
plain strings too, so a webhook with an event or format added by a newer server still
parses; `update(..., {"format": "teams"})` changes the format, leaving it out keeps it.

### Update Outgoing Webhook

Fields you leave out keep their current values. `secret` is the one to handle carefully, because it has three states and one of them is destructive:

```python
# Keep the current secret - omit the field entirely
client.webhooks.update("wh_xxx", {"name": "Renamed"})

# Replace the secret
client.webhooks.update("wh_xxx", {"secret": "whsec_new"})

# Clear the secret - deliveries then go out UNSIGNED, with no
# X-Spooled-Signature header for your endpoint to verify
client.webhooks.update("wh_xxx", {"secret": None})
```

Do not build the update body by dumping a whole webhook object and sending every field back: an unchanged `secret` serialised as an explicit `None` wipes a live secret. Pass only the fields you mean to change.

### Auto-Disable

After 20 consecutive failed deliveries the backend disables the webhook itself — `enabled` becomes `False` and `last_status` becomes `"auto_disabled"`. It receives no further events until you turn it back on:

```python
webhook = client.webhooks.get("wh_xxx")
if webhook.last_status == "auto_disabled":
    client.webhooks.update("wh_xxx", {"enabled": True})
```

Re-enabling is charged against the plan webhook cap, so it raises `RateLimitError` with code `QUOTA_EXCEEDED` if the organization is already at its limit.

`failure_count` counts failed *deliveries*, not individual retry attempts, so it is roughly 5x smaller than an attempt-based count for the same failures. Any successful delivery resets it to 0, including a successful manual retry.

### Test Webhook

```python
result = client.webhooks.test("wh_xxx")
print(result.success, result.status_code)
```

### Get Deliveries

```python
deliveries = client.webhooks.get_deliveries("wh_xxx")
```

Deliveries are dispatched under a process-wide concurrency cap, so under heavy load they queue rather than all firing at once, and delivery order is not guaranteed.

Delivery history is retained, not archived. The per-organization retention sweep deletes rows older than your plan's window — 1 day on free, 7 on starter, 30 on pro, 90 on enterprise — and only the newest 100 deliveries per webhook are readable through the API in any case. Copy anything you need for long-term auditing into your own store.

### Retry Delivery

```python
result = client.webhooks.retry_delivery("wh_xxx", "whd_xxx")
print(result.success, result.message)
```

### Inbound Webhook Log

Requests accepted by `POST /webhooks/{org_id}/custom` (see `client.ingest.custom`),
newest first and without their payloads. Needs an unrestricted API key.

```python
from datetime import datetime, timedelta, timezone

for entry in client.webhooks.list_inbound_deliveries({
    "status": "duplicate",                 # Optional: created or duplicate
    "since": datetime.now(timezone.utc) - timedelta(days=1),
    "queue_name": "orders",                # Optional
    "limit": 50,                           # 1-100
}):
    print(entry.created_at, entry.event_type, entry.matched_queue, entry.job_id, entry.status)
```

`job_id` and `status` are `None` for entries recorded before the server started storing them.

## Rate Limits

The API sends `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` (Unix
seconds) and `X-RateLimit-Scope` on every response. `client.rate_limit` holds the latest
values as a `RateLimitInfo` (`limit`, `remaining`, `reset` as an aware UTC `datetime`,
`reset_epoch`, `scope`), or `None` before the first response. A 429 raises
`RateLimitError` with the same fields plus `retry_after` from `Retry-After`, and is
retried automatically after that delay.

## Error Handling

```python
from spooled.errors import (
    SpooledError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
    QuotaExceededError,
    RateLimitError,
    ServerError,
    NetworkError,
    TimeoutError,
)

try:
    job = client.jobs.get("nonexistent")
except NotFoundError:
    print("Not found")
except QuotaExceededError as e:
    # 429 QUOTA_EXCEEDED: a plan limit. Not retried, will not clear in seconds.
    print(f"Plan limit {e.resource}: {e.current}/{e.limit} on {e.plan}; upgrade to {e.upgrade_to}")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after}s")
except ValidationError as e:
    # 400 (field rule) and 422 (missing/mistyped field); e.details is often a list
    print(e.status_code, e.details)
except NetworkError:
    print("Network error")
except SpooledError as e:
    print(f"Error: {e.code} - {e.message}")
```

`QuotaExceededError` subclasses `RateLimitError`, so existing `except RateLimitError`
handlers still catch it. Complete/fail/heartbeat acks are retried on network errors,
timeouts, 5xx and 408; other POSTs (such as `jobs.create`) are only retried on a rate
limit, or when they carry an idempotency key.

## Unsupported operations

`client.organizations.clear_webhook_token()` (sync and async) is deprecated: the API
always rejects clearing the webhook token, so the method raises
`UnsupportedOperationError` (a `SpooledError`) without a network call. Use
`regenerate_webhook_token()` to rotate it.
