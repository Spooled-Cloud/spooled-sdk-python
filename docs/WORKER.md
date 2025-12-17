# Worker Guide

Guide for processing jobs using the Spooled Worker runtime.

## Basic Usage

```python
from spooled import SpooledClient
from spooled.worker import SpooledWorker

# Create client
client = SpooledClient(api_key="sk_live_...")

# Create worker
worker = SpooledWorker(
    client,
    queue_name="my-queue",
    concurrency=10,
)

# Register job handler
@worker.process
def handle_job(ctx):
    print(f"Processing: {ctx.job_id}")
    
    # Your job logic here
    result = do_work(ctx.payload)
    
    return {"success": True, "result": result}

# Start worker (blocking)
worker.start()
```

## Worker Options

```python
worker = SpooledWorker(
    client,
    queue_name="my-queue",
    concurrency=10,           # Max concurrent jobs
    poll_interval=1.0,        # Seconds between polls
    lease_duration=30,        # Job lease in seconds
    heartbeat_fraction=0.5,   # Heartbeat at 50% of lease
    shutdown_timeout=30.0,    # Graceful shutdown timeout
    hostname="worker-1",      # Custom hostname
    worker_type="python",     # Worker type identifier
    version="1.0.0",          # Worker version
    metadata={"env": "prod"}, # Custom metadata
)
```

## Job Context

The job handler receives a context object:

```python
@worker.process
def handle_job(ctx):
    # Job information
    ctx.job_id          # Job ID
    ctx.queue_name      # Queue name
    ctx.payload         # Job payload (dict)
    ctx.retry_count     # Current retry count
    ctx.max_retries     # Maximum retries allowed
    
    # Abort signal (threading.Event)
    if ctx.signal.is_set():
        print("Job was aborted!")
        return None
    
    # Logging
    ctx.log("info", "Processing started", {"key": "value"})
    
    # Progress (for future use)
    ctx.progress(50, "Halfway done")
    
    return {"result": "done"}
```

## Event Handlers

Register handlers for worker events:

```python
@worker.on("started")
def on_started(event):
    print(f"Worker {event.worker_id} started on {event.queue_name}")

@worker.on("stopped")
def on_stopped(event):
    print(f"Worker stopped: {event.reason}")

@worker.on("error")
def on_error(event):
    print(f"Worker error: {event.error}")

@worker.on("job:claimed")
def on_claimed(event):
    print(f"Job {event.job_id} claimed")

@worker.on("job:started")
def on_started(event):
    print(f"Job {event.job_id} started")

@worker.on("job:completed")
def on_completed(event):
    print(f"Job {event.job_id} completed: {event.result}")

@worker.on("job:failed")
def on_failed(event):
    print(f"Job {event.job_id} failed: {event.error}")
    print(f"Will retry: {event.will_retry}")
```

## Graceful Shutdown

```python
import signal
import sys

def shutdown(signum, frame):
    print("Shutting down...")
    worker.stop()  # Waits for active jobs to complete
    client.close()
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

worker.start()
```

## Error Handling

Exceptions in job handlers are automatically caught and reported:

```python
@worker.process
def handle_job(ctx):
    if ctx.payload.get("should_fail"):
        raise ValueError("Intentional failure")
    
    return {"success": True}
```

The job will be marked as failed and retried if retries remain.

## Async Worker

```python
import asyncio
from spooled import AsyncSpooledClient
from spooled.worker import AsyncSpooledWorker

async def main():
    async with AsyncSpooledClient(api_key="sk_live_...") as client:
        worker = AsyncSpooledWorker(
            client,
            queue_name="my-queue",
            concurrency=10,
        )

        @worker.process
        async def handle_job(ctx):
            # Async job processing
            await asyncio.sleep(1)
            return {"success": True}

        await worker.start()

asyncio.run(main())
```

## Best Practices

1. **Set appropriate timeouts** — Match `lease_duration` to your job's expected runtime
2. **Check abort signal** — For long-running jobs, periodically check `ctx.signal.is_set()`
3. **Handle graceful shutdown** — Always call `worker.stop()` on SIGTERM/SIGINT
4. **Use idempotent handlers** — Jobs may be retried, so handle duplicates gracefully
5. **Return meaningful results** — Include relevant data in the return value for debugging
