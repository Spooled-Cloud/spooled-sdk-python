#!/usr/bin/env python3
"""
Worker example for Spooled Python SDK.

Demonstrates processing jobs from a queue.
"""

import os
import signal
import sys
import time

from spooled import SpooledClient
from spooled.worker import SpooledWorker


def main() -> None:
    """Run worker example."""
    # Get API key from environment
    api_key = os.environ.get("SPOOLED_API_KEY")
    if not api_key:
        print("Please set SPOOLED_API_KEY environment variable")
        return

    # Create client
    client = SpooledClient(api_key=api_key)

    # Create worker
    worker = SpooledWorker(
        client,
        queue_name="example-queue",
        concurrency=5,
        poll_interval=1.0,
        lease_duration=30,
    )

    # Register job handler
    @worker.process
    def handle_job(ctx):
        """Process a job."""
        print(f"Processing job {ctx.job_id}")
        print(f"  Queue: {ctx.queue_name}")
        print(f"  Payload: {ctx.payload}")
        print(f"  Retry: {ctx.retry_count}/{ctx.max_retries}")

        # Check for abort signal
        if ctx.signal.is_set():
            print("  Job aborted!")
            return None

        # Log progress
        ctx.log("info", "Starting email processing")

        # Simulate work
        time.sleep(2)

        # Check abort again
        if ctx.signal.is_set():
            print("  Job aborted!")
            return None

        ctx.log("info", "Email sent successfully")

        # Return result
        return {"sent": True, "timestamp": time.time()}

    # Register event handlers
    @worker.on("started")
    def on_started(event):
        print(f"\n✓ Worker started: {event.worker_id}")
        print(f"  Queue: {event.queue_name}")

    @worker.on("stopped")
    def on_stopped(event):
        print(f"\n✓ Worker stopped: {event.reason}")

    @worker.on("job:completed")
    def on_job_completed(event):
        print(f"\n✓ Job {event.job_id} completed")
        print(f"  Result: {event.result}")

    @worker.on("job:failed")
    def on_job_failed(event):
        print(f"\n✗ Job {event.job_id} failed")
        print(f"  Error: {event.error}")
        print(f"  Will retry: {event.will_retry}")

    # Set up graceful shutdown
    def shutdown(signum, frame):
        print("\nShutting down...")
        worker.stop()
        client.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # Start worker
    print("Starting worker... (Press Ctrl+C to stop)")
    worker.start()


if __name__ == "__main__":
    main()



