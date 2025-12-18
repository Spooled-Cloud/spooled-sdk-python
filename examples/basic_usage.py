#!/usr/bin/env python3
"""
Basic usage example for Spooled Python SDK.

Demonstrates creating jobs, checking status, and listing jobs.
"""

import os

from spooled import SpooledClient


def main() -> None:
    """Run basic usage example."""
    # Get API key from environment
    api_key = os.environ.get("SPOOLED_API_KEY")
    if not api_key:
        print("Please set SPOOLED_API_KEY environment variable")
        return

    # Create client
    with SpooledClient(api_key=api_key) as client:
        # Check health
        print("Checking API health...")
        health = client.health.get()
        print(f"  Status: {health.status}")
        print(f"  Database: {health.database}")

        # Create a job
        print("\nCreating a job...")
        result = client.jobs.create({
            "queue_name": "example-queue",
            "payload": {
                "to": "user@example.com",
                "subject": "Hello from Spooled!",
                "body": "This is a test email.",
            },
            "priority": 5,
            "max_retries": 3,
        })
        print(f"  Job ID: {result.id}")
        print(f"  Created: {result.created}")

        # Get job details
        print("\nGetting job details...")
        job = client.jobs.get(result.id)
        print(f"  Status: {job.status}")
        print(f"  Queue: {job.queue_name}")
        print(f"  Priority: {job.priority}")
        print(f"  Payload: {job.payload}")

        # List jobs
        print("\nListing recent jobs...")
        jobs = client.jobs.list({"limit": 5})
        for j in jobs:
            print(f"  - {j.id}: {j.status} (priority: {j.priority})")

        # Get job statistics
        print("\nJob statistics...")
        stats = client.jobs.get_stats()
        print(f"  Pending: {stats.pending}")
        print(f"  Processing: {stats.processing}")
        print(f"  Completed: {stats.completed}")
        print(f"  Failed: {stats.failed}")
        print(f"  Total: {stats.total}")

        # Cancel the job (for cleanup)
        print(f"\nCancelling job {result.id}...")
        client.jobs.cancel(result.id)
        print("  Done!")


if __name__ == "__main__":
    main()
