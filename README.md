# Spooled Python SDK

Official Python SDK for [Spooled Cloud](https://spooled.cloud) — a modern, scalable job queue and task scheduler.

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

client = SpooledClient(api_key="sk_live_...")

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

client = SpooledClient(api_key="sk_live_...")
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

worker.start()  # Blocking
```

## Real-world examples (beginner friendly)

If you want 5 copy/paste “real life” setups (Stripe → jobs, GitHub Actions → jobs, cron schedules, CSV import, website signup), see:

- `https://github.com/spooled-cloud/spooled-backend/blob/main/docs/guides/real-world-examples.md`

### Async Client

```python
import asyncio
from spooled import AsyncSpooledClient

async def main():
    async with AsyncSpooledClient(api_key="sk_live_...") as client:
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

client = SpooledClient(api_key="sk_live_...")

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

client = SpooledClient(api_key="sk_live_...")

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

# Connect to Spooled Cloud gRPC (TLS required for Cloudflare Tunnel)
client = SpooledGrpcClient(
    address="grpc.spooled.cloud:443", 
    api_key="sk_live_...",
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

### When to use gRPC?

- **High Throughput**: 3x faster than HTTP API for enqueue/dequeue operations.
- **Streaming**: Supports real-time job streaming.
- **Efficiency**: Uses persistent HTTP/2 connections with keepalives.

## Real-time Events (SSE/WebSocket)

Listen for real-time updates:

```python
from spooled import SpooledClient

client = SpooledClient(api_key="sk_live_...")

# Subscribe to job updates
for event in client.realtime.subscribe("jobs:updates"):
    print(f"Event: {event.type} - {event.data}")
```

## Configuration

```python
from spooled import SpooledClient, SpooledClientConfig, RetryConfig

# Full configuration
config = SpooledClientConfig(
    api_key="sk_live_...",
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
)

client = SpooledClient(api_key="sk_live_...")

try:
    job = client.jobs.get("nonexistent")
except NotFoundError:
    print("Job not found")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after}s")
except SpooledError as e:
    print(f"API error: {e.code} - {e.message}")
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
| `client.webhooks` | Outgoing webhook management |
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

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SPOOLED_API_KEY` | API key for authentication |
| `SPOOLED_BASE_URL` | API base URL (default: https://api.spooled.cloud) |

## Requirements

- Python 3.10+
- `httpx>=0.25.0`
- `pydantic>=2.0.0`

## License

Apache 2.0
