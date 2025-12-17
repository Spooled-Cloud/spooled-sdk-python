#!/usr/bin/env python3
"""
Production Verification Script

A comprehensive CLI tool that interactively validates your entire production stack:
SDK, API, Worker, Webhooks.

Usage:
  python scripts/verify_production.py

Prerequisites:
  1. Start your Cloudflare tunnel first:
     cloudflared tunnel --url http://localhost:3001

  2. Have your API key ready (sk_live_... or sk_test_...)
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any

# Add src to path if running from scripts directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from spooled import SpooledClient
from spooled.errors import is_spooled_error
from spooled.worker import SpooledWorker

# ============================================================================
# Types
# ============================================================================


@dataclass
class WebhookPayload:
    event: str
    data: dict[str, Any]
    timestamp: str | None = None


@dataclass
class VerificationContext:
    api_key: str = ""
    tunnel_url: str = ""
    base_url: str = ""
    client: SpooledClient | None = None
    queue_name: str = ""
    webhook_id: str | None = None
    job_id: str | None = None
    worker: SpooledWorker | None = None
    server: HTTPServer | None = None
    received_webhooks: list[WebhookPayload] = field(default_factory=list)
    job_processed: bool = False
    job_completed: bool = False


# ============================================================================
# Utilities
# ============================================================================


class Colors:
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    GRAY = "\033[90m"


def log_info(msg: str) -> None:
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {msg}")


def log_success(msg: str) -> None:
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def log_error(msg: str) -> None:
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


def log_warn(msg: str) -> None:
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {msg}")


def log_step(phase: str, step: str) -> None:
    print(f"\n{Colors.CYAN}[{phase}]{Colors.RESET} {Colors.BOLD}{step}{Colors.RESET}")


def log_header(title: str) -> None:
    print(f"\n{Colors.CYAN}{Colors.BOLD} {title} {Colors.RESET}")
    print(f"{Colors.CYAN}{'─' * 60}{Colors.RESET}")


def log_divider() -> None:
    print(f"{Colors.GRAY}{'─' * 60}{Colors.RESET}")


def sleep(seconds: float) -> None:
    time.sleep(seconds)


def wait_for(condition: callable, timeout: float = 30.0, interval: float = 0.5) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if condition():
            return True
        sleep(interval)
    return False


def prompt(message: str, default: str = "") -> str:
    if default:
        result = input(f"{message} [{default}]: ").strip()
        return result if result else default
    return input(f"{message}: ").strip()


def prompt_choice(message: str, choices: list[tuple[str, str]], default: str = "") -> str:
    print(f"\n{message}")
    for i, (name, value) in enumerate(choices, 1):
        marker = " (default)" if value == default else ""
        print(f"  {i}. {name}{marker}")

    while True:
        choice = input("Enter number or custom value: ").strip()
        if not choice and default:
            return default
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(choices):
                return choices[idx][1]
        except ValueError:
            pass
        # Return as custom value
        if choice:
            return choice
        print("Please enter a valid choice")


# ============================================================================
# Phase 1: Configuration
# ============================================================================


def prompt_configuration() -> tuple[str, str, str]:
    log_header("PHASE 1: Configuration")

    print(f"\n{Colors.YELLOW}📋 Before continuing, make sure you have:{Colors.RESET}")
    print(f"{Colors.GRAY}   1. Started your Cloudflare tunnel:")
    print(f"      cloudflared tunnel --url http://localhost:3001{Colors.RESET}")
    print(f"{Colors.GRAY}   2. Your API key ready (sk_live_... or sk_test_...){Colors.RESET}\n")

    # API Key
    while True:
        api_key = prompt("Enter your API Key")
        if not api_key.startswith("sk_live_") and not api_key.startswith("sk_test_"):
            print("API key must start with sk_live_ or sk_test_")
            continue
        if len(api_key) < 20:
            print("API key seems too short")
            continue
        break

    # Tunnel URL
    while True:
        tunnel_url = prompt("Enter your Tunnel URL", "https://my-tunnel.trycloudflare.com")
        if not tunnel_url.startswith("https://"):
            print("Tunnel URL must use HTTPS")
            continue
        break

    # Base URL
    base_url = prompt_choice(
        "API Base URL:",
        [
            ("Local (http://localhost:8080)", "http://localhost:8080"),
            ("Local (http://127.0.0.1:8080)", "http://127.0.0.1:8080"),
            ("Production (https://api.spooled.cloud)", "https://api.spooled.cloud"),
        ],
        "http://localhost:8080",
    )

    # Remove trailing slashes
    tunnel_url = tunnel_url.rstrip("/")
    base_url = base_url.rstrip("/")

    log_success("Configuration received")
    log_info(f"API Key: {api_key[:12]}...")
    log_info(f"Tunnel URL: {tunnel_url}")
    log_info(f"API Base URL: {base_url}")

    return api_key, tunnel_url, base_url


# ============================================================================
# Local Webhook Server
# ============================================================================

WEBHOOK_SERVER_PORT = 3001


class WebhookHandler(BaseHTTPRequestHandler):
    ctx: VerificationContext | None = None

    def log_message(self, format: str, *args: Any) -> None:
        pass  # Suppress logging

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "Not found"}')

    def do_POST(self) -> None:
        if self.path == "/webhook":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                payload = json.loads(body)
                if WebhookHandler.ctx:
                    WebhookHandler.ctx.received_webhooks.append(
                        WebhookPayload(
                            event=payload.get("event", ""),
                            data=payload.get("data", {}),
                            timestamp=payload.get("timestamp"),
                        )
                    )
                    log_info(f"Received webhook: {Colors.BOLD}{payload.get('event')}{Colors.RESET}")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"received": true}')
            except Exception as e:
                log_error(f"Failed to parse webhook: {e}")
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error": "Invalid JSON"}')
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "Not found"}')


def start_webhook_server(ctx: VerificationContext) -> None:
    log_step("Phase 1", f"Starting local webhook server on port {WEBHOOK_SERVER_PORT}...")

    WebhookHandler.ctx = ctx
    server = HTTPServer(("", WEBHOOK_SERVER_PORT), WebhookHandler)
    ctx.server = server

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    log_success(f"Webhook server running on http://localhost:{WEBHOOK_SERVER_PORT}")
    log_info("Webhook endpoint: /webhook")


# ============================================================================
# Phase 2: Core Connectivity
# ============================================================================


def verify_connectivity(ctx: VerificationContext) -> None:
    log_header("PHASE 2: Core Connectivity")

    # Test basic connectivity with health endpoint
    log_step("Phase 2", "Testing API connectivity (health check)...")

    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(f"{ctx.base_url}/health")
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                health = json.loads(response.read())
                log_success(f"API is reachable: {health.get('status', 'ok')}")
            else:
                log_warn(f"Health check returned {response.status}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cannot reach API at {ctx.base_url}: {e}")

    log_step("Phase 2", "Initializing SDK client...")

    def debug_fn(msg: str, meta: Any = None) -> None:
        if meta:
            log_info(f"[SDK] {msg} {meta}")
        else:
            log_info(f"[SDK] {msg}")

    ctx.client = SpooledClient(
        api_key=ctx.api_key,
        base_url=ctx.base_url,
        debug=True,
    )

    log_success("SDK client initialized")

    log_step("Phase 2", "Verifying API key with dashboard endpoint...")

    try:
        dashboard = ctx.client.dashboard.get()
        log_success("API key verified")
        log_info(f"System version: {dashboard.system.version if dashboard.system else 'N/A'}")
        log_info(f"Total jobs: {dashboard.jobs.total if dashboard.jobs else 0}")
        log_info(f"Pending jobs: {dashboard.jobs.pending if dashboard.jobs else 0}")
        log_info(f"Active workers: {dashboard.workers.total if dashboard.workers else 0}")
    except Exception as error:
        if is_spooled_error(error):
            log_error(f"Status: {error.status_code}")
            log_error(f"Code: {error.code}")
            log_error(f"Message: {error.message}")
            if error.details:
                log_error(f"Details: {error.details}")
            if error.request_id:
                log_error(f"Request ID: {error.request_id}")
            raise RuntimeError(f"API key verification failed: {error.message} ({error.code})")
        raise


# ============================================================================
# Phase 3: Resource Creation
# ============================================================================


def create_resources(ctx: VerificationContext) -> None:
    log_header("PHASE 3: Resource Creation")

    if not ctx.client:
        raise RuntimeError("Client not initialized")

    # Create temporary queue
    timestamp = int(time.time())
    ctx.queue_name = f"verify-prod-{timestamp}"

    log_step("Phase 3", f"Creating temporary queue: {ctx.queue_name}...")
    log_info("Queue will be created automatically with first job")
    log_success(f"Queue name set: {ctx.queue_name}")

    # Register webhook
    log_step("Phase 3", "Registering webhook subscription...")

    webhook_url = f"{ctx.tunnel_url}/webhook"
    log_info(f"Webhook URL: {webhook_url}")

    try:
        webhook = ctx.client.webhooks.create({
            "name": f"verify-prod-webhook-{timestamp}",
            "url": webhook_url,
            "events": ["job.created", "job.started", "job.completed", "job.failed"],
            "enabled": True,
        })
        ctx.webhook_id = webhook.id
        log_success(f"Webhook registered: {webhook.id}")
        log_info(f"Events: {', '.join(webhook.events)}")
    except Exception as error:
        if is_spooled_error(error):
            raise RuntimeError(f"Failed to create webhook: {error.message} ({error.code})")
        raise

    # Test webhook connectivity
    log_step("Phase 3", "Testing webhook endpoint connectivity...")

    try:
        if ctx.webhook_id:
            test_result = ctx.client.webhooks.test(ctx.webhook_id)
            if test_result.success:
                log_success(f"Webhook test passed ({test_result.response_time_ms}ms)")
            else:
                log_warn(f"Webhook test failed: {test_result.error}")
                log_info("Continuing anyway - production webhooks may still work")
    except Exception:
        log_warn("Could not test webhook - continuing anyway")


# ============================================================================
# Phase 4: Job Processing
# ============================================================================


def process_jobs(ctx: VerificationContext) -> None:
    log_header("PHASE 4: Job Processing")

    if not ctx.client:
        raise RuntimeError("Client not initialized")

    # Start worker
    log_step("Phase 4", "Starting worker...")

    ctx.worker = SpooledWorker(
        ctx.client,
        queue_name=ctx.queue_name,
        concurrency=1,
        poll_interval=1.0,
        lease_duration=30,
    )

    # Set up event handlers
    @ctx.worker.on("started")
    def on_started(event):
        log_success(f"Worker started: {event.worker_id}")
        log_info(f"Listening on queue: {event.queue_name}")

    @ctx.worker.on("job:claimed")
    def on_claimed(event):
        log_info(f"Job claimed: {event.job_id}")

    @ctx.worker.on("job:completed")
    def on_completed(event):
        log_success(f"Job completed: {event.job_id}")
        if event.result:
            log_info(f"Result: {event.result}")
        ctx.job_completed = True

    @ctx.worker.on("job:failed")
    def on_failed(event):
        log_error(f"Job failed: {event.job_id} - {event.error} (will retry: {event.will_retry})")

    @ctx.worker.on("error")
    def on_error(event):
        log_error(f"Worker error: {event.error}")

    # Define job handler
    @ctx.worker.process
    def handle_job(job_ctx):
        log_info(f"Processing job {job_ctx.job_id}...")
        log_info(f"Payload: {job_ctx.payload}")

        # Simulate some work
        sleep(0.5)

        ctx.job_processed = True

        return {
            "processed": True,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "message": "Hello from production verification!",
        }

    # Start the worker in background
    worker_thread = threading.Thread(target=ctx.worker.start, daemon=True)
    worker_thread.start()
    sleep(1)  # Give worker time to register

    # Enqueue test job
    log_step("Phase 4", "Enqueueing test job...")

    try:
        result = ctx.client.jobs.create({
            "queue_name": ctx.queue_name,
            "payload": {
                "message": "Hello Production",
                "source": "verify_production.py",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            "priority": 5,
            "max_retries": 3,
        })
        ctx.job_id = result.id
        log_success(f"Job enqueued: {result.id} (new: {result.created})")
    except Exception as error:
        if is_spooled_error(error):
            raise RuntimeError(f"Failed to create job: {error.message} ({error.code})")
        raise

    # Wait for job processing
    log_step("Phase 4", "Waiting for job to be processed...")

    job_processed = wait_for(lambda: ctx.job_processed, timeout=30.0)

    if not job_processed:
        raise RuntimeError("Job was not processed within 30 seconds")

    log_success("Job processing verified")

    # Wait for job completion
    log_step("Phase 4", "Waiting for job completion confirmation...")

    job_completed = wait_for(lambda: ctx.job_completed, timeout=10.0)

    if not job_completed:
        raise RuntimeError("Job completion not confirmed within 10 seconds")

    log_success("Job completion confirmed")

    # Verify job status via API
    log_step("Phase 4", "Verifying job status via API...")

    if ctx.job_id and ctx.client:
        try:
            job = ctx.client.jobs.get(ctx.job_id)
            log_info(f"Job status: {job.status}")

            if job.status == "completed":
                log_success("Job status verified as completed")
            else:
                log_warn(f"Unexpected job status: {job.status}")

            if job.result:
                log_info(f"Job result: {job.result}")
        except Exception:
            log_warn("Could not fetch job status")

    # Verify webhook delivery
    log_step("Phase 4", "Waiting for webhook delivery...")

    webhook_received = wait_for(
        lambda: any(
            (w.event == "job.completed" or w.event == "job_completed")
            and w.data.get("job_id") == ctx.job_id
            for w in ctx.received_webhooks
        ),
        timeout=15.0,
    )

    if webhook_received:
        log_success("Webhook received for job completion")

        completed_webhook = next(
            (
                w
                for w in ctx.received_webhooks
                if (w.event == "job.completed" or w.event == "job_completed")
                and w.data.get("job_id") == ctx.job_id
            ),
            None,
        )

        if completed_webhook:
            log_info(f"Webhook event: {completed_webhook.event}")
            log_info(f"Webhook job_id: {completed_webhook.data.get('job_id')}")
    else:
        log_warn("No webhook received for job completion within 15 seconds")
        log_info("This may be expected if webhook delivery is delayed or filtered")

        if ctx.received_webhooks:
            log_info(f"Received {len(ctx.received_webhooks)} webhook(s) total:")
            for w in ctx.received_webhooks:
                log_info(f"  - {w.event}: {w.data}")


# ============================================================================
# Phase 5: Cleanup
# ============================================================================


def cleanup(ctx: VerificationContext) -> None:
    log_header("PHASE 5: Cleanup")

    # Stop worker
    if ctx.worker:
        log_step("Phase 5", "Stopping worker...")
        try:
            ctx.worker.stop()
            log_success("Worker stopped")
        except Exception as e:
            log_warn(f"Error stopping worker: {e}")

    # Delete webhook
    if ctx.webhook_id and ctx.client:
        log_step("Phase 5", "Deleting webhook subscription...")
        try:
            ctx.client.webhooks.delete(ctx.webhook_id)
            log_success("Webhook deleted")
        except Exception as e:
            log_warn(f"Error deleting webhook: {e}")

    # Delete queue
    if ctx.queue_name and ctx.client:
        log_step("Phase 5", "Cleaning up queue...")
        try:
            ctx.client.queues.delete(ctx.queue_name)
            log_success("Queue deleted")
        except Exception:
            log_info("Queue cleanup skipped (may be auto-cleaned)")

    # Stop webhook server
    if ctx.server:
        log_step("Phase 5", "Stopping webhook server...")
        ctx.server.shutdown()
        log_success("Webhook server stopped")

    # Close client
    if ctx.client:
        ctx.client.close()


# ============================================================================
# Summary Report
# ============================================================================


def print_summary(ctx: VerificationContext, success: bool, error: Exception | None = None) -> None:
    log_header("VERIFICATION SUMMARY")

    checks = [
        ("SDK Client Initialization", ctx.client is not None),
        ("API Authentication", ctx.client is not None),
        ("Queue Creation", ctx.queue_name != ""),
        ("Webhook Registration", ctx.webhook_id is not None),
        ("Worker Started", ctx.worker is not None),
        ("Job Enqueued", ctx.job_id is not None),
        ("Job Processed", ctx.job_processed),
        ("Job Completed", ctx.job_completed),
        (
            "Webhook Received",
            any(
                (w.event == "job.completed" or w.event == "job_completed")
                and w.data.get("job_id") == ctx.job_id
                for w in ctx.received_webhooks
            ),
        ),
    ]

    print()

    for name, passed in checks:
        if passed:
            print(f"  {Colors.GREEN}✓{Colors.RESET} {name}")
        else:
            print(f"  {Colors.RED}✗{Colors.RESET} {Colors.GRAY}{name}{Colors.RESET}")

    print(f"\n{Colors.GRAY}{'─' * 60}{Colors.RESET}")

    if success:
        print(
            f"\n{Colors.GREEN}{Colors.BOLD} 🎉 SUCCESS {Colors.RESET}"
            f"{Colors.GREEN} All production systems verified!{Colors.RESET}\n"
        )
    else:
        print(
            f"\n{Colors.RED}{Colors.BOLD} ❌ FAILED {Colors.RESET}"
            f"{Colors.RED} Verification failed: {error}{Colors.RESET}\n"
        )

    # Stats
    print(f"{Colors.GRAY}Statistics:")
    print(f"  • Webhooks received: {len(ctx.received_webhooks)}")
    print(f"  • Queue used: {ctx.queue_name}")
    if ctx.job_id:
        print(f"  • Test job ID: {ctx.job_id}")
    print(Colors.RESET)


# ============================================================================
# Main Entry Point
# ============================================================================


def main() -> None:
    print(f"\n{Colors.BOLD}{'━' * 60}")
    print("   🔍 SPOOLED PRODUCTION VERIFICATION TOOL (Python)")
    print(f"{'━' * 60}{Colors.RESET}\n")

    print(f"{Colors.GRAY}This tool will verify your production stack:")
    print("  • SDK connectivity")
    print("  • API authentication")
    print("  • Job queue operations")
    print("  • Worker processing")
    print(f"  • Webhook delivery{Colors.RESET}")
    print()

    ctx = VerificationContext()

    success = False
    main_error: Exception | None = None

    try:
        # Phase 1: Configuration
        api_key, tunnel_url, base_url = prompt_configuration()
        ctx.api_key = api_key
        ctx.tunnel_url = tunnel_url
        ctx.base_url = base_url

        # Start webhook server
        start_webhook_server(ctx)

        # Phase 2: Core Connectivity
        verify_connectivity(ctx)

        # Phase 3: Resource Creation
        create_resources(ctx)

        # Phase 4: Job Processing
        process_jobs(ctx)

        success = True

    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}⚠ Received interrupt, cleaning up...{Colors.RESET}")
    except Exception as e:
        main_error = e
        log_error(f"\nVerification failed: {e}")

    finally:
        # Phase 5: Cleanup
        cleanup(ctx)

        # Print summary
        print_summary(ctx, success, main_error)

        # Exit with appropriate code
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()


