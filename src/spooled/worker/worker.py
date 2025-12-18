"""
Spooled Worker (synchronous)

Worker runtime for processing jobs from a queue.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Event
from typing import TYPE_CHECKING, Any

from spooled.types.jobs import ClaimedJob
from spooled.worker.types import (
    ErrorEventData,
    JobClaimedEventData,
    JobCompletedEventData,
    JobContext,
    JobFailedEventData,
    JobHandler,
    JobStartedEventData,
    SpooledWorkerOptions,
    StartedEventData,
    StoppedEventData,
    WorkerEvent,
    WorkerState,
)

if TYPE_CHECKING:
    from spooled.client import SpooledClient


@dataclass
class ActiveJob:
    """Represents an active job being processed."""

    job: ClaimedJob
    started_at: float
    abort_event: Event
    heartbeat_timer: threading.Timer | None = None


class SpooledWorker:
    """
    Spooled Worker (synchronous).

    Example:
        >>> from spooled import SpooledClient, SpooledWorker
        >>>
        >>> client = SpooledClient(api_key="sk_live_...")
        >>> worker = SpooledWorker(client, queue_name="my-queue", concurrency=10)
        >>>
        >>> @worker.process
        ... def handle_job(ctx):
        ...     print(f"Processing job {ctx.job_id}")
        ...     return {"success": True}
        >>>
        >>> worker.start()  # Blocks until stopped
    """

    def __init__(
        self,
        client: SpooledClient,
        queue_name: str,
        *,
        concurrency: int = 5,
        poll_interval: float = 1.0,
        lease_duration: int = 30,
        heartbeat_fraction: float = 0.5,
        shutdown_timeout: float = 30.0,
        hostname: str | None = None,
        worker_type: str = "python",
        version: str = "1.0.0",
        metadata: dict[str, Any] | None = None,
        auto_start: bool = False,
    ) -> None:
        """
        Initialize the worker.

        Args:
            client: SpooledClient instance
            queue_name: Name of the queue to process
            concurrency: Maximum number of concurrent jobs
            poll_interval: Seconds between polling for new jobs
            lease_duration: Job lease duration in seconds
            heartbeat_fraction: Fraction of lease to wait before heartbeat
            shutdown_timeout: Seconds to wait for jobs to complete on shutdown
            hostname: Worker hostname (auto-detected if not provided)
            worker_type: Type identifier for this worker
            version: Version string for this worker
            metadata: Additional metadata to attach to worker
            auto_start: Whether to start the worker automatically
        """
        self._client = client
        self._options = SpooledWorkerOptions(
            queue_name=queue_name,
            concurrency=concurrency,
            poll_interval=poll_interval,
            lease_duration=lease_duration,
            heartbeat_fraction=heartbeat_fraction,
            shutdown_timeout=shutdown_timeout,
            hostname=hostname or socket.gethostname(),
            worker_type=worker_type,
            version=version,
            metadata=metadata or {},
            auto_start=auto_start,
        )

        self._state: WorkerState = "idle"
        self._worker_id: str | None = None
        self._handler: JobHandler | None = None
        self._active_jobs: dict[str, ActiveJob] = {}
        self._poll_timer: threading.Timer | None = None
        self._worker_heartbeat_timer: threading.Timer | None = None
        self._shutdown_event = Event()
        self._executor: ThreadPoolExecutor | None = None
        self._lock = threading.Lock()

        # Event handlers
        self._event_handlers: dict[WorkerEvent, list[Callable[..., Any]]] = {}

        # Debug function from client
        config = client.get_config()
        self._debug = config.debug_fn

        if auto_start:
            # Defer start to allow process() to be called
            threading.Timer(0, self.start).start()

    @property
    def state(self) -> WorkerState:
        """Get current worker state."""
        return self._state

    @property
    def worker_id(self) -> str | None:
        """Get worker ID (available after start)."""
        return self._worker_id

    @property
    def active_job_count(self) -> int:
        """Get number of active jobs."""
        return len(self._active_jobs)

    def process(self, handler: JobHandler) -> JobHandler:
        """
        Register job handler (decorator).

        Example:
            >>> @worker.process
            ... def handle_job(ctx):
            ...     return {"result": "done"}
        """
        if self._state != "idle":
            raise RuntimeError("Cannot set handler after worker has started")
        self._handler = handler
        return handler

    def on(self, event: WorkerEvent, handler: Callable[..., Any] | None = None) -> Callable[..., Any]:
        """
        Register event handler (decorator).

        Example:
            >>> @worker.on("job:completed")
            ... def on_completed(event):
            ...     print(f"Job {event.job_id} completed")
        """

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            if event not in self._event_handlers:
                self._event_handlers[event] = []
            self._event_handlers[event].append(fn)
            return fn

        if handler is not None:
            decorator(handler)
            return handler
        return decorator

    def start(self) -> None:
        """Start the worker (blocking)."""
        if self._state != "idle":
            raise RuntimeError(f"Cannot start worker in state: {self._state}")

        if not self._handler:
            raise RuntimeError("No job handler registered. Call process() first.")

        self._state = "starting"
        self._shutdown_event.clear()

        if self._debug:
            self._debug(f"Starting worker for queue: {self._options.queue_name}", None)

        try:
            # Register with the API
            registration = self._client.workers.register({
                "queue_name": self._options.queue_name,
                "hostname": self._options.hostname,
                "worker_type": self._options.worker_type,
                "max_concurrency": self._options.concurrency,
                "metadata": self._options.metadata,
                "version": self._options.version,
            })

            self._worker_id = registration.id

            if self._debug:
                self._debug(f"Worker registered: {self._worker_id}", None)

            # Start executor
            self._executor = ThreadPoolExecutor(max_workers=self._options.concurrency)

            # Start worker heartbeat
            heartbeat_interval = registration.heartbeat_interval_secs
            self._schedule_worker_heartbeat(heartbeat_interval)

            # Start polling
            self._state = "running"
            self._emit("started", StartedEventData(
                worker_id=self._worker_id,
                queue_name=self._options.queue_name,
            ))

            # Poll loop (blocking)
            while self._state == "running" and not self._shutdown_event.is_set():
                self._poll()
                self._shutdown_event.wait(self._options.poll_interval)

        except Exception as e:
            self._state = "error"
            self._emit("error", ErrorEventData(error=e))
            raise

    def stop(self) -> None:
        """Stop the worker gracefully."""
        if self._state != "running":
            return

        self._state = "stopping"
        self._shutdown_event.set()

        if self._debug:
            self._debug("Stopping worker...", None)

        # Stop polling
        if self._poll_timer:
            self._poll_timer.cancel()
            self._poll_timer = None

        # Stop worker heartbeat
        if self._worker_heartbeat_timer:
            self._worker_heartbeat_timer.cancel()
            self._worker_heartbeat_timer = None

        # Signal all active jobs to stop
        for active in self._active_jobs.values():
            active.abort_event.set()
            if active.heartbeat_timer:
                active.heartbeat_timer.cancel()

        # Wait for active jobs to complete (with timeout)
        if self._active_jobs:
            if self._debug:
                self._debug(
                    f"Waiting for {len(self._active_jobs)} active jobs to complete...",
                    None,
                )

            deadline = time.time() + self._options.shutdown_timeout
            while self._active_jobs and time.time() < deadline:
                time.sleep(0.1)

            # Force-fail remaining jobs
            for job_id, active in list(self._active_jobs.items()):
                if self._debug:
                    self._debug(f"Force-failing job {job_id} due to shutdown timeout", None)
                self._fail_job(active.job, "Worker shutdown timeout")

        # Shutdown executor
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None

        # Deregister worker
        if self._worker_id:
            try:
                self._client.workers.deregister(self._worker_id)
                if self._debug:
                    self._debug("Worker deregistered", None)
            except Exception as e:
                if self._debug:
                    self._debug(f"Failed to deregister worker: {e}", None)

        self._state = "stopped"
        self._emit("stopped", StoppedEventData(
            worker_id=self._worker_id or "",
            reason="graceful",
        ))
        self._worker_id = None

    def _poll(self) -> None:
        """Poll for and claim jobs."""
        if self._state != "running" or not self._worker_id:
            return

        # Check capacity
        with self._lock:
            available_slots = self._options.concurrency - len(self._active_jobs)

        if available_slots <= 0:
            return

        try:
            result = self._client.jobs.claim({
                "queue_name": self._options.queue_name,
                "worker_id": self._worker_id,
                "limit": available_slots,
                "lease_duration_secs": self._options.lease_duration,
            })

            for job in result.jobs:
                self._process_job(job)

        except Exception as e:
            if self._debug:
                self._debug(f"Poll failed: {e}", None)
            self._emit("error", ErrorEventData(error=e))

    def _process_job(self, job: ClaimedJob) -> None:
        """Start processing a job."""
        self._emit("job:claimed", JobClaimedEventData(
            job_id=job.id,
            queue_name=job.queue_name,
        ))

        abort_event = Event()
        active = ActiveJob(
            job=job,
            started_at=time.time(),
            abort_event=abort_event,
        )

        with self._lock:
            self._active_jobs[job.id] = active

        # Start per-job heartbeat
        heartbeat_interval = self._options.lease_duration * self._options.heartbeat_fraction
        self._schedule_job_heartbeat(job.id, heartbeat_interval)

        # Execute handler in thread pool
        if self._executor:
            self._executor.submit(self._execute_handler, active)

    def _execute_handler(self, active: ActiveJob) -> None:
        """Execute job handler."""
        job = active.job

        self._emit("job:started", JobStartedEventData(
            job_id=job.id,
            queue_name=job.queue_name,
        ))

        context = JobContext(
            job_id=job.id,
            queue_name=job.queue_name,
            payload=job.payload,
            retry_count=job.retry_count,
            max_retries=job.max_retries,
            signal=active.abort_event,
        )

        try:
            result = self._handler(context)  # type: ignore

            # Check if aborted
            if active.abort_event.is_set():
                if self._debug:
                    self._debug(f"Job {job.id} was aborted", None)
                return

            # Complete the job
            self._complete_job(job, result)

        except Exception as e:
            # Check if aborted
            if active.abort_event.is_set():
                if self._debug:
                    self._debug(f"Job {job.id} was aborted", None)
                return

            error_message = str(e)
            self._fail_job(job, error_message)

        finally:
            self._cleanup_job(job.id)

    def _complete_job(self, job: ClaimedJob, result: dict[str, Any] | None) -> None:
        """Complete a job."""
        if not self._worker_id:
            return

        try:
            self._client.jobs.complete(job.id, {
                "worker_id": self._worker_id,
                "result": result,
            })

            self._emit("job:completed", JobCompletedEventData(
                job_id=job.id,
                queue_name=job.queue_name,
                result=result,
            ))

        except Exception as e:
            if self._debug:
                self._debug(f"Failed to complete job {job.id}: {e}", None)

    def _fail_job(self, job: ClaimedJob, error_message: str) -> None:
        """Fail a job."""
        if not self._worker_id:
            return

        will_retry = job.retry_count < job.max_retries

        try:
            self._client.jobs.fail(job.id, {
                "worker_id": self._worker_id,
                "error": error_message,
            })

            self._emit("job:failed", JobFailedEventData(
                job_id=job.id,
                queue_name=job.queue_name,
                error=error_message,
                will_retry=will_retry,
            ))

        except Exception as e:
            if self._debug:
                self._debug(f"Failed to fail job {job.id}: {e}", None)

    def _cleanup_job(self, job_id: str) -> None:
        """Clean up after job completion."""
        with self._lock:
            active = self._active_jobs.pop(job_id, None)
            if active and active.heartbeat_timer:
                active.heartbeat_timer.cancel()

    def _schedule_job_heartbeat(self, job_id: str, interval: float) -> None:
        """Schedule job heartbeat."""

        def send_heartbeat() -> None:
            if job_id not in self._active_jobs or not self._worker_id:
                return

            try:
                self._client.jobs.heartbeat(job_id, {
                    "worker_id": self._worker_id,
                    "lease_duration_secs": self._options.lease_duration,
                })
            except Exception as e:
                if self._debug:
                    self._debug(f"Job heartbeat failed for {job_id}: {e}", None)

            # Reschedule
            if job_id in self._active_jobs:
                timer = threading.Timer(interval, send_heartbeat)
                timer.daemon = True
                with self._lock:
                    if job_id in self._active_jobs:
                        self._active_jobs[job_id].heartbeat_timer = timer
                        timer.start()

        timer = threading.Timer(interval, send_heartbeat)
        timer.daemon = True
        with self._lock:
            if job_id in self._active_jobs:
                self._active_jobs[job_id].heartbeat_timer = timer
                timer.start()

    def _schedule_worker_heartbeat(self, interval: float) -> None:
        """Schedule worker heartbeat."""

        def send_heartbeat() -> None:
            if self._state != "running" or not self._worker_id:
                return

            try:
                self._client.workers.heartbeat(self._worker_id, {
                    "current_jobs": len(self._active_jobs),
                    "status": "healthy",
                })
            except Exception as e:
                if self._debug:
                    self._debug(f"Worker heartbeat failed: {e}", None)

            # Reschedule
            if self._state == "running":
                self._worker_heartbeat_timer = threading.Timer(interval, send_heartbeat)
                self._worker_heartbeat_timer.daemon = True
                self._worker_heartbeat_timer.start()

        self._worker_heartbeat_timer = threading.Timer(interval, send_heartbeat)
        self._worker_heartbeat_timer.daemon = True
        self._worker_heartbeat_timer.start()

    def _emit(self, event: WorkerEvent, data: Any) -> None:
        """Emit an event to handlers."""
        handlers = self._event_handlers.get(event, [])
        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                if self._debug:
                    self._debug(f"Event handler error for {event}: {e}", None)
