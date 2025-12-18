#!/usr/bin/env python3
"""
Schedule (Cron) example for Spooled Python SDK.

Demonstrates creating and managing scheduled jobs.
"""

import os

from spooled import SpooledClient


def main() -> None:
    """Run schedule example."""
    # Get API key from environment
    api_key = os.environ.get("SPOOLED_API_KEY")
    if not api_key:
        print("Please set SPOOLED_API_KEY environment variable")
        return

    # Create client
    with SpooledClient(api_key=api_key) as client:
        # Create a schedule
        print("Creating schedules...")

        # Daily report at 9 AM
        daily = client.schedules.create({
            "name": "Daily Report",
            "description": "Generate daily sales report",
            "cron_expression": "0 9 * * *",
            "timezone": "America/New_York",
            "queue_name": "reports",
            "payload_template": {
                "report_type": "daily",
                "format": "pdf",
                "recipients": ["sales@example.com"],
            },
            "priority": 5,
            "max_retries": 3,
            "timeout_seconds": 300,
            "tags": {"type": "report", "frequency": "daily"},
        })
        print(f"  Created: {daily.name} ({daily.id})")
        print(f"  Next run: {daily.next_run_at}")

        # Hourly metrics collection
        hourly = client.schedules.create({
            "name": "Hourly Metrics",
            "description": "Collect system metrics",
            "cron_expression": "0 * * * *",  # Every hour
            "timezone": "UTC",
            "queue_name": "metrics",
            "payload_template": {
                "action": "collect",
                "targets": ["cpu", "memory", "disk"],
            },
        })
        print(f"  Created: {hourly.name} ({hourly.id})")
        print(f"  Next run: {hourly.next_run_at}")

        # List all schedules
        print("\nListing all schedules...")
        schedules = client.schedules.list()
        for s in schedules:
            status = "active" if s.is_active else "paused"
            print(f"  - {s.name}: {s.cron_expression} ({status})")

        # Pause a schedule
        print(f"\nPausing schedule {hourly.id}...")
        paused = client.schedules.pause(hourly.id)
        print(f"  Paused: {paused.name}")

        # Resume the schedule
        print(f"\nResuming schedule {hourly.id}...")
        resumed = client.schedules.resume(hourly.id)
        print(f"  Resumed: {resumed.name}")

        # Trigger a schedule manually
        print(f"\nTriggering schedule {daily.id} manually...")
        triggered = client.schedules.trigger(daily.id)
        print(f"  Created job: {triggered.job_id}")

        # Get schedule history
        print(f"\nSchedule history for {daily.id}...")
        history = client.schedules.get_history(daily.id, limit=5)
        for run in history:
            print(f"  - {run.started_at}: {run.status} (job: {run.job_id})")

        # Clean up: delete the schedules
        print("\nCleaning up...")
        client.schedules.delete(daily.id)
        client.schedules.delete(hourly.id)
        print("  Schedules deleted")

        # Cancel the manually triggered job
        client.jobs.cancel(triggered.job_id)
        print("  Triggered job cancelled")

        print("\nDone!")


if __name__ == "__main__":
    main()



