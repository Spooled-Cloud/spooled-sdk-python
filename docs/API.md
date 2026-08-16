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
```

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
jobs = client.jobs.list({
    "queue_name": "my-queue",
    "status": "pending",
    "tag": "billing",  # Optional: filter by a single tag
    "limit": 50,
    "offset": 0,
})
```

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
print(result.priority, result.previous_priority)
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
    print(s.id, s.status)
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
# List DLQ jobs
dlq_jobs = client.jobs.dlq.list({"queue_name": "my-queue"})

# Retry DLQ jobs
result = client.jobs.dlq.retry({"queue_name": "my-queue", "limit": 10})

# Purge DLQ
result = client.jobs.dlq.purge({"queue_name": "my-queue"})
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

### Cancel Workflow

```python
client.workflows.cancel("wf_xxx")
```

## Webhooks

### Create Outgoing Webhook

```python
webhook = client.webhooks.create({
    "name": "Job Notifications",
    "url": "https://myapp.com/webhooks/spooled",
    "events": ["job.completed", "job.failed"],
    "secret": "whsec_...",  # Optional: signs deliveries with X-Spooled-Signature
})
```

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
print(result.status)
```

## Error Handling

```python
from spooled.errors import (
    SpooledError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
    RateLimitError,
    ServerError,
    NetworkError,
    TimeoutError,
)

try:
    job = client.jobs.get("nonexistent")
except NotFoundError:
    print("Not found")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after}s")
except NetworkError:
    print("Network error")
except SpooledError as e:
    print(f"Error: {e.code} - {e.message}")
```
