#!/usr/bin/env python3
"""
Production test runner for scripts/test_local.py.

Safe defaults:
- Uses Spooled Cloud endpoints (REST and grpc.spooled.cloud:443)
- Skips stress/load tests unless --full is provided (to avoid noisy prod runs)
- test_local.py skips steps with side effects outside the test organization
  (creating an organization, login email, billing portal) unless ALLOW_UNSAFE=1

Use a dedicated test organization's key: the run creates and deletes jobs,
queues, workers, schedules, workflows, webhooks and an API key in it, and
rotates its inbound webhook token.

Usage:
  API_KEY=sp_live_... python scripts/test_production.py

Options:
  --full     Run stress/load tests too (NOT recommended for prod)
  --verbose  Enable verbose output in test_local.py

Overrides (optional):
  BASE_URL=https://api.spooled.cloud
  GRPC_ADDRESS=grpc.spooled.cloud:443
  SKIP_STRESS=0|1
"""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
    argv = set(sys.argv[1:])
    is_full = "--full" in argv
    is_verbose = "--verbose" in argv

    api_key = os.environ.get("API_KEY")
    if not api_key:
        print("❌ API_KEY is required")
        print("   Example: API_KEY=sp_live_... python scripts/test_production.py")
        sys.exit(1)

    base_url = os.environ.get("BASE_URL", "https://api.spooled.cloud")
    grpc_address = os.environ.get("GRPC_ADDRESS", "grpc.spooled.cloud:443")

    # Default to skipping stress tests in production (can be overridden or --full)
    skip_stress = "0" if is_full else os.environ.get("SKIP_STRESS", "1")

    # Build environment
    env = os.environ.copy()
    env.update(
        {
            "API_KEY": api_key,
            "BASE_URL": base_url,
            "GRPC_ADDRESS": grpc_address,
            "SKIP_STRESS": skip_stress,
            # Emoji output through a Windows pipe.
            "PYTHONIOENCODING": "utf-8",
            "VERBOSE": "1" if is_verbose else os.environ.get("VERBOSE", "0"),
        }
    )

    # Determine script path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    test_local_path = os.path.join(script_dir, "test_local.py")

    # Run test_local.py
    result = subprocess.run(
        [sys.executable, test_local_path],
        env=env,
        cwd=os.path.dirname(script_dir),  # Project root
    )

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
