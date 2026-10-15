# Spooled Python SDK

Official Python SDK for [Spooled Cloud](https://spooled.cloud) — a modern, scalable job queue and task scheduler.

[**Live Demo (SpriteForge)**](https://example.spooled.cloud) • [Documentation](https://spooled.cloud/docs)

## Features

- **Full API Coverage** — Access all Spooled API endpoints
- **Type Safety** — Full type hints and Pydantic models
- **Sync & Async** — Both synchronous and asynchronous clients
- **Worker Runtime** — Process jobs with a decorator-based API
- **Real-time Events** — WebSocket and SSE support
- **gRPC Support** — High-performance gRPC client (optional)
- **Resilience** — Retry logic with exponential backoff and circuit breaker
- **Production Ready** — Comprehensive error handling and logging

## Installation

```bash
pip install spooled
```

### Optional Extras

```bash
# For real-time events (WebSocket/SSE)
pip install spooled[realtime]

# For gRPC support
pip install spooled[grpc]

# All features
pip install spooled[all]
```

## Quick Start

### Create a Job

```python
from spooled import SpooledClient

client = SpooledClient(api_key="sp_live_...")

# Create a job
result = client.jobs.create({
    "queue_name": "emails",
    "payload": {
        "to": "user@example.com",
        "subject": "Welcome!",
        "template": "welcome_email",
    },
    "priority": 5,
})

print(f"Job created: {result.id}")

# Get job details
job = client.jobs.get(result.id)
print(f"Status: {job.status}")

client.close()
```

### Process Jobs with a Worker

```python
from spooled import SpooledClient
from spooled.worker import SpooledWorker

client = SpooledClient(api_key="sp_live_...")
worker = SpooledWorker(client, queue_name="emails", concurrency=10)

@worker.process
def handle_job(ctx):
    """Process an email job."""
    print(f"Processing job {ctx.job_id}")
    
    # Access payload
    to = ctx.payload["to"]
    subject = ctx.payload["subject"]
    
    # Send the email (your logic here)
    send_email(to, subject)
    
    # Return result
    return {"sent": True}

@worker.on("job:completed")
def on_completed(event):
    print(f"Job {event.job_id} completed!")

worker.start()  # Blocking; returns after worker.stop() has drained running jobs
```

`worker.stop()` (call it from a SIGTERM/SIGINT handler) stops claiming jobs, lets running
handlers finish for up to `shutdown_timeout` seconds and still acks their results, then
deregisters. A handler is only signalled (`ctx.signal`) and failed once it outlives that
timeout or the job's own `timeout_seconds`. See [docs/WORKER.md](docs/WORKER.md).

If you drive the worker endpoints yourself (`client.jobs.claim/complete/fail/heartbeat`),
send the `lease_id` from the claimed job on every `complete`, `fail` and `heartbeat`: the API
requires it (422 without it) and applies the call only to the lease you hold. `SpooledWorker`
does this for you.

### List Jobs, History and Paging

```python
from datetime import datetime, timezone

page = client.jobs.list({
    "status": ["failed", "deadletter"],   # one status, a list, or "failed,deadletter"
    "q": "invoice",                       # id prefix, queue name or payload.job_type
    "job_type": "send_invoice",           # exact payload.job_type
    "created_after": datetime(2026, 10, 1, tzinfo=timezone.utc),
    "limit": 50,
})
for job in page:
    print(job.id, job.status)
if page.has_more:                         # from the X-Has-More response header
    next_page = client.jobs.list({"status": ["failed", "deadletter"], "offset": 50})

for event in client.jobs.history(job.id):  # oldest first; {"order_dir": "desc"} for newest
    print(event.created_at, event.event_type, event.worker_id)
```

`jobs.list()`, `jobs.dlq.list()` and `jobs.history()` return a normal `list` with a
`has_more` attribute (`None` when the server sends no `X-Has-More`).

## Real-world examples (beginner friendly)

If you want 5 copy/paste “real life” setups (Stripe → jobs, GitHub Actions → jobs, cron schedules, CSV import, website signup), see:

- `https://github.com/spooled-cloud/spooled-backend/blob/main/docs/guides/real-world-examples.md`

### Async Client

```python
import asyncio
from spooled import AsyncSpooledClient

async def main():
    async with AsyncSpooledClient(api_key="sp_live_...") as client:
        # Create multiple jobs concurrently
        tasks = [
            client.jobs.create({"queue_name": "tasks", "payload": {"n": i}})
            for i in range(10)
        ]
        results = await asyncio.gather(*tasks)
        print(f"Created {len(results)} jobs")

asyncio.run(main())
```

### Workflows (Job Dependencies)

```python
from spooled import SpooledClient

client = SpooledClient(api_key="sp_live_...")

# Create a workflow with dependencies
workflow = client.workflows.create({
    "name": "Order Processing",
    "jobs": [
        {
            "key": "validate",
            "queue_name": "orders",
            "payload": {"action": "validate"},
        },
        {
            "key": "charge",
            "queue_name": "payments",
            "payload": {"action": "charge"},
            "depends_on": ["validate"],
        },
        {
            "key": "ship",
            "queue_name": "fulfillment",
            "payload": {"action": "ship"},
            "depends_on": ["charge"],
        },
    ],
})

print(f"Workflow created: {workflow.workflow_id}")
```

### Schedules (Cron Jobs)

```python
from spooled import SpooledClient

client = SpooledClient(api_key="sp_live_...")

# Create a scheduled job
schedule = client.schedules.create({
    "name": "Daily Report",
    "cron_expression": "0 9 * * *",  # 9 AM daily
    "timezone": "America/New_York",
    "queue_name": "reports",
    "payload_template": {"report_type": "daily"},
})

print(f"Schedule created: {schedule.id}")
print(f"Next run: {schedule.next_run_at}")
```

## gRPC Support (High Performance)

The SDK includes a high-performance gRPC client for high-throughput worker scenarios.

```python
from spooled.grpc import SpooledGrpcClient

# Connect to Spooled Cloud gRPC (TLS required for Cloudflare Tunnel).
# `SpooledClient(api_key=...).grpc` does this for you and honours `grpc_address=`.
client = SpooledGrpcClient(
    address="grpc.spooled.cloud:443", 
    api_key="sp_live_...",
    use_tls=True  # Required for production (Cloudflare Tunnel needs HTTPS for HTTP/2)
)

# Enqueue a job
response = client.queue.enqueue(
    queue_name="high-throughput",
    payload={"data": "value"}
)
print(f"Job enqueued: {response.job_id}")

# Get queue stats
stats = client.queue.get_queue_stats("high-throughput")
print(f"Pending jobs: {stats.pending}")

client.close()
```

Leases and streams (server behaviour):

- `queue.dequeue(...)` hands out up to `batch_size` jobs, each with a lease of
  `lease_duration_secs` (5-3600 s; when it is omitted or `0` the server default applies, 300 s on
  Spooled Cloud). A job that can run longer than its lease needs a longer lease, or
  `queue.renew_lease(job_id, worker_id, extension_secs, lease_id=...)` before it expires.
- `queue.stream_jobs(...)` delivers **one job at a time per stream**: the next job arrives only after
  the previous one on that stream is completed, failed or released. Settle every job, and open one
  stream per job slot to run jobs in parallel (at most 100 open streams per organization).
- `queue.complete`, `queue.fail` and `queue.renew_lease` need the dequeued job's `lease_id`
  (`INVALID_ARGUMENT` without it). `queue.fail(..., retry=False, lease_id=...)` dead-letters the
  job now; the default (`retry=True`) retries it until `max_retries` is used up.
- `workers.register(queue_name, hostname, worker_id="pod-7")` takes an optional stable
  `worker_id`: registering the same id again after a restart updates that worker instead of
  adding one.

Payloads over gRPC are `google.protobuf.Struct`, which has two limits that REST does not:

- `payload` and `result` must be JSON **objects**. A job created over REST with a string,
  number or array payload arrives over gRPC as an empty dict.
- Struct numbers are doubles, so integers of 2^53 (9 007 199 254 740 992) and above lose
  precision over gRPC. REST keeps them exact; send large ids as strings, or use REST.

### When to use gRPC?

- **High Throughput**: Persistent HTTP/2 and Protobuf can reduce overhead; benchmark your workload and network path.
- **Streaming**: Supports real-time job streaming.
- **Efficiency**: Uses persistent HTTP/2 connections with keepalives.

## Real-time Events (SSE/WebSocket)

Listen for real-time updates:

```python
from spooled import SpooledClient
from spooled.realtime.unified import SubscriptionFilter

client = SpooledClient(api_key="sp_live_...")

# Subscribe to job updates for a queue, then iterate events
realtime = client.realtime(type="websocket")
realtime.connect()
realtime.subscribe(SubscriptionFilter(queue="my-queue"))

for event in realtime.events():
    print(f"Event: {event.type} - {event.data}")
```

## Configuration

```python
from spooled import SpooledClient, SpooledClientConfig, RetryConfig

# Full configuration
config = SpooledClientConfig(
    api_key="sp_live_...",
    base_url="https://api.spooled.cloud",
    timeout=30.0,
    retry=RetryConfig(
        max_retries=3,
        base_delay=1.0,
        max_delay=30.0,
    ),
    debug=True,
)

client = SpooledClient(config=config)
```

## Error Handling

```python
from spooled import SpooledClient
from spooled.errors import (
    SpooledError,
    NotFoundError,
    ValidationError,
    RateLimitError,
    QuotaExceededError,
)

client = SpooledClient(api_key="sp_live_...")

try:
    job = client.jobs.get("nonexistent")
except NotFoundError:
    print("Job not found")
except RateLimitError as e:
    # 429 covers both request-rate limiting and plan-quota errors. A rate-limited 429
    # carries Retry-After; e.limit, e.remaining, e.reset (aware UTC datetime) and e.scope
    # come from the X-RateLimit-* headers. The plan limit is per organization in
    # requests/second, an API key's own rate_limit is requests/minute.
    # A plan quota is a QuotaExceededError (code "QUOTA_EXCEEDED", with
    # resource/current/limit/plan): it is never retried, because it will not clear in seconds.
    if isinstance(e, QuotaExceededError):
        print(f"Plan quota exceeded: {e.message} ({e.current}/{e.limit} on {e.plan})")
    else:
        print(f"Rate limited. Retry after {e.retry_after}s")
except SpooledError as e:
    print(f"API error: {e.code} - {e.message}")
```

The API sends `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` (Unix
seconds) and `X-RateLimit-Scope` on **every** response. The latest values are on
`client.rate_limit` (a `RateLimitInfo`, `None` before the first response):

```python
client.jobs.get_stats()
info = client.rate_limit
print(info.remaining, "of", info.limit, "left until", info.reset, f"({info.scope})")
```

## API Reference

### Client Resources

| Resource | Description |
|----------|-------------|
| `client.jobs` | Job CRUD, claim, complete, fail, DLQ |
| `client.queues` | Queue config, stats, pause/resume |
| `client.workers` | Worker registration, heartbeat |
| `client.schedules` | Cron job scheduling |
| `client.workflows` | Multi-job workflows with dependencies |
| `client.webhooks` | Outgoing webhooks (events, `json`/`slack`/`discord`/`teams` format), deliveries, inbound webhook log |
| `client.ingest` | Inbound custom webhooks (`POST /webhooks/{org_id}/custom`) |
| `client.api_keys` | API key management |
| `client.organizations` | Organization settings, usage |
| `client.billing` | Billing status, portal |
| `client.auth` | Authentication, token management |
| `client.health` | Health checks |
| `client.admin` | Admin operations (requires admin_key) |

### Worker Events

| Event | Description |
|-------|-------------|
| `started` | Worker started processing |
| `stopped` | Worker stopped |
| `error` | Worker error occurred |
| `job:claimed` | Job claimed from queue |
| `job:started` | Job handler started |
| `job:completed` | Job completed successfully |
| `job:failed` | Job failed |
| `job:lease_lost` | Job lease lost; the worker stops and does not ack the job |

## Environment Variables

The SDK does **not** read environment variables: pass the API key (and a non-default base
URL) to `SpooledClient` yourself. The examples and the integration tests in this repository
use these names by convention:

| Variable | Used for |
|----------|----------|
| `SPOOLED_API_KEY` | `SpooledClient(api_key=os.environ["SPOOLED_API_KEY"])` |
| `SPOOLED_BASE_URL` | `base_url=` (the SDK default is `https://api.spooled.cloud`) |

## Requirements

- Python 3.10+
- Core: `httpx>=0.25.0`, `pydantic>=2.0.0`
- gRPC extra: `grpcio>=1.80.0`, `grpcio-tools>=1.80.0`, `protobuf>=6.33.5`
- Realtime extra: `websockets>=12.0`, `sseclient-py>=1.8.0`

The package version is defined in `pyproject.toml`. At runtime, `spooled.__version__`, the default REST `User-Agent`, worker options, and REST/gRPC worker registration read installed package metadata; source-only imports fall back to `1.5.0`.

Release maintainers should follow the [publishing checklist](docs/PUBLISHING.md) before creating a tag or publishing to PyPI.

## License

Apache 2.0
