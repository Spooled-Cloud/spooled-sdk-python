#!/usr/bin/env python3
"""
Async usage example for Spooled Python SDK.

Demonstrates using the async client for concurrent operations.
"""

import asyncio
import os

from spooled import AsyncSpooledClient


async def main() -> None:
    """Run async usage example."""
    # Get API key from environment
    api_key = os.environ.get("SPOOLED_API_KEY")
    if not api_key:
        print("Please set SPOOLED_API_KEY environment variable")
        return

    # Create async client
    async with AsyncSpooledClient(api_key=api_key) as client:
        # Concurrent operations
        print("Running concurrent API calls...")

        # Create multiple jobs concurrently
        tasks = [
            client.jobs.create({
                "queue_name": "async-example",
                "payload": {"index": i},
            })
            for i in range(5)
        ]

        results = await asyncio.gather(*tasks)

        print(f"Created {len(results)} jobs:")
        for result in results:
            print(f"  - {result.id} (created: {result.created})")

        # Get all jobs concurrently
        job_ids = [r.id for r in results]
        job_tasks = [client.jobs.get(job_id) for job_id in job_ids]
        jobs = await asyncio.gather(*job_tasks)

        print("\nJob details:")
        for job in jobs:
            print(f"  - {job.id}: {job.status} - {job.payload}")

        # Get stats and list in parallel
        stats, job_list = await asyncio.gather(
            client.jobs.get_stats(),
            client.jobs.list({"queue_name": "async-example", "limit": 10}),
        )

        print(f"\nStats: {stats.pending} pending, {stats.total} total")
        print(f"Listed {len(job_list)} jobs")

        # Cancel all created jobs
        print("\nCancelling jobs...")
        cancel_tasks = [client.jobs.cancel(job_id) for job_id in job_ids]
        await asyncio.gather(*cancel_tasks)
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
