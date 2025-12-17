#!/usr/bin/env python3
"""
Workflow example for Spooled Python SDK.

Demonstrates creating workflows with job dependencies.
"""

import os

from spooled import SpooledClient


def main() -> None:
    """Run workflow example."""
    # Get API key from environment
    api_key = os.environ.get("SPOOLED_API_KEY")
    if not api_key:
        print("Please set SPOOLED_API_KEY environment variable")
        return

    # Create client
    with SpooledClient(api_key=api_key) as client:
        # Create a workflow with dependencies
        print("Creating order processing workflow...")

        workflow = client.workflows.create({
            "name": "Order Processing",
            "description": "Process an order through validation, payment, fulfillment, and notification",
            "jobs": [
                {
                    "key": "validate",
                    "queue_name": "orders",
                    "payload": {"action": "validate", "order_id": "12345"},
                },
                {
                    "key": "charge",
                    "queue_name": "payments",
                    "payload": {"action": "charge", "order_id": "12345", "amount": 99.99},
                    "depends_on": ["validate"],
                },
                {
                    "key": "fulfill",
                    "queue_name": "fulfillment",
                    "payload": {"action": "ship", "order_id": "12345"},
                    "depends_on": ["charge"],
                },
                {
                    "key": "notify",
                    "queue_name": "notifications",
                    "payload": {"action": "email", "order_id": "12345", "template": "order_complete"},
                    "depends_on": ["fulfill"],
                },
            ],
        })

        print(f"Created workflow: {workflow.workflow_id}")
        print("\nJob mappings:")
        for mapping in workflow.job_ids:
            print(f"  {mapping.key} -> {mapping.job_id}")

        # Get workflow status
        print("\nGetting workflow status...")
        status = client.workflows.get(workflow.workflow_id)
        print(f"  Name: {status.name}")
        print(f"  Status: {status.status}")
        print(f"  Progress: {status.progress_percent}%")
        print(f"  Jobs: {status.completed_jobs}/{status.total_jobs}")

        # List workflows
        print("\nListing workflows...")
        workflows = client.workflows.list({"limit": 5})
        for wf in workflows:
            print(f"  - {wf.id}: {wf.name} ({wf.status})")

        # Cancel the workflow (for cleanup)
        print(f"\nCancelling workflow {workflow.workflow_id}...")
        client.workflows.cancel(workflow.workflow_id)
        print("Done!")


if __name__ == "__main__":
    main()


