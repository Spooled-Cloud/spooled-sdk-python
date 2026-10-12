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

from spooled._version import __version__
from spooled.errors import ConflictError
from spooled.types.jobs import ClaimedJob, coerce_fail_error
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


# How long stop() waits for acks that are already in flight once the shutdown
# timeout is over, before it deregisters (which re-queues anything still unacked).
ACK_GRACE_SECONDS = 10.0


@dataclass
class ActiveJob:
    """Represents an active job being processed."""

    job: ClaimedJob
    started_at: float
    abort_event: Event
    heartbeat_timer: threading.Timer | None = None
    timeout_timer: threading.Timer | None = None
    # Set by whoever acks (complete/fail) first, under the worker lock, so a
    # handler returning at the same moment as a timeout never sends both.
    settled: bool = False
    # True while the handler thread still runs after the SDK gave up on the job
    # (job timeout / shutdown timeout). The job was failed server-side and the
    # slot is freed, but the thread cannot be killed, so it still counts toward
    # concurrency until it returns.
    abandoned: bool = False


class SpooledWorker:
    """
    Spooled Worker (synchronous).

    Example:
        >>> from spooled import SpooledClient, SpooledWorker
        >>>
        >>> client = SpooledClient(api_key="sp_live_...")
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
        worker_id: str | None = None,
        worker_type: str = "python",
        version: str = __version__,
        metadata: Any = None,
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
            worker_id: Stable worker id (1-128 chars, ``[A-Za-z0-9._-]``).
                Supplying one makes registration an upsert so a restarting
                worker reuses its row instead of leaving a stale one against
                the plan worker cap; omit it and the server mints a UUID
                per registration
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
            worker_id=worker_id,
            worker_type=worker_type,
            version=version,
            metadata={} if metadata is None else metadata,
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
        # Re-entrant: stop() is usually called from a signal handler on the same
        # thread that runs the poll loop, which may be inside a locked section.
        self._lock = threading.RLock()
        # Signalled whenever a job leaves ``_active_jobs`` so stop() can drain.
        self._idle = threading.Condition(self._lock)
        # Closed by stop() once the drain window is over: a job claimed by a poll
        # that was already in flight is then left unstarted (deregister re-queues it).
        self._intake_closed = False
        self._abandoned_running = 0
        self._worker_heartbeat_stop = Event()
        # Set when stop() has fully finished, so start() can wait for it.
        self._stopped_event = Event()

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

    def on(
        self, event: WorkerEvent, handler: Callable[..., Any] | None = None
    ) -> Callable[..., Any]:
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
        """Start the worker (blocking until it has fully stopped)."""
        if self._state != "idle":
            raise RuntimeError(f"Cannot start worker in state: {self._state}")

        if not self._handler:
            raise RuntimeError("No job handler registered. Call process() first.")

        self._state = "starting"
        self._shutdown_event.clear()
        self._stopped_event.clear()
        self._worker_heartbeat_stop.clear()
        self._intake_closed = False

        if self._debug:
            self._debug(f"Starting worker for queue: {self._options.queue_name}", None)

        try:
            # Register with the API
            registration = self._client.workers.register(
                {
                    "queue_name": self._options.queue_name,
                    "hostname": self._options.hostname,
                    # Dropped when None, so the server mints a UUID instead.
                    "worker_id": self._options.worker_id,
                    "worker_type": self._options.worker_type,
                    "max_concurrency": self._options.concurrency,
                    "metadata": self._options.metadata,
                    "version": self._options.version,
                }
            )

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
            self._emit(
                "started",
                StartedEventData(
                    worker_id=self._worker_id,
                    queue_name=self._options.queue_name,
                ),
            )

            # Poll loop (blocking)
            while self._state == "running" and not self._shutdown_event.is_set():
                self._poll()
                self._shutdown_event.wait(self._options.poll_interval)

            # stop() may be running on another thread: hold start() until it has
            # drained and deregistered, so callers can safely close the client
            # as soon as start() returns.
            if self.state == "stopping":
                self._stopped_event.wait()

        except Exception as e:
            self._state = "error"
            self._emit("error", ErrorEventData(error=e))
            raise

    def stop(self) -> None:
        """Stop the worker gracefully.

        Stops claiming new jobs, then lets running handlers finish for up to
        ``shutdown_timeout`` seconds: a handler that returns (or raises) in that
        window is still acked with ``complete`` (or ``fail``) and its job heartbeat
        keeps the lease alive. Only handlers still running after the timeout are
        signalled through ``ctx.signal`` and failed with "Worker shutdown timeout".
        The worker deregisters last, because deregistering re-queues every job
        the worker still holds.
        """
        with self._lock:
            if self._state != "running":
                return
            self._state = "stopping"
        self._shutdown_event.set()

        try:
            if self._debug:
                self._debug("Stopping worker...", None)

            # Stop polling
            if self._poll_timer:
                self._poll_timer.cancel()
                self._poll_timer = None

            # Drain: job heartbeats and the worker heartbeat keep running so the
            # leases stay valid while handlers finish. Handlers are not signalled
            # yet -- aborting them first is what used to throw their results away.
            deadline = time.monotonic() + self._options.shutdown_timeout
            if self._active_jobs and self._debug:
                self._debug(
                    f"Waiting for {len(self._active_jobs)} active jobs to complete...",
                    None,
                )
            self._wait_for_idle(deadline, close_intake=True)

            # Whatever is still running outlived the shutdown timeout.
            for active in list(self._active_jobs.values()):
                if self._debug:
                    self._debug(f"Force-failing job {active.job.id} due to shutdown timeout", None)
                self._abandon_job(active, "Worker shutdown timeout")
            # An ack that was already in flight when the timeout hit is left to finish.
            self._wait_for_idle(time.monotonic() + ACK_GRACE_SECONDS)

            # Stop worker heartbeat
            self._worker_heartbeat_stop.set()
            if self._worker_heartbeat_timer:
                self._worker_heartbeat_timer.cancel()
                self._worker_heartbeat_timer = None

            # Shutdown executor
            if self._executor:
                self._executor.shutdown(wait=False)
                self._executor = None

            # Deregister worker (last: this re-queues any job still unacked)
            if self._worker_id:
                try:
                    self._client.workers.deregister(self._worker_id)
                    if self._debug:
                        self._debug("Worker deregistered", None)
                except Exception as e:
                    if self._debug:
                        self._debug(f"Failed to deregister worker: {e}", None)

            self._state = "stopped"
            self._emit(
                "stopped",
                StoppedEventData(
                    worker_id=self._worker_id or "",
                    reason="graceful",
                ),
            )
            self._worker_id = None
        finally:
            self._stopped_event.set()

    def _wait_for_idle(self, deadline: float, *, close_intake: bool = False) -> None:
        """Block until no job is active or ``deadline`` (a monotonic time) passes.

        ``close_intake`` also closes the intake in the same locked step that
        observes the end of the wait, so a poll that was already in flight cannot
        register a job after stop() decided nothing is left to drain.
        """
        with self._idle:
            while self._active_jobs:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._idle.wait(remaining)
            if close_intake:
                self._intake_closed = True

    def _poll(self) -> None:
        """Poll for and claim jobs."""
        if self._state != "running" or not self._worker_id:
            return

        # Check capacity (handlers abandoned after a timeout still occupy a thread)
        with self._lock:
            available_slots = (
                self._options.concurrency - len(self._active_jobs) - self._abandoned_running
            )

        if available_slots <= 0:
            return

        try:
            result = self._client.jobs.claim(
                {
                    "queue_name": self._options.queue_name,
                    "worker_id": self._worker_id,
                    "limit": available_slots,
                    "lease_duration_secs": self._options.lease_duration,
                }
            )

            for job in result.jobs:
                self._process_job(job)

        except Exception as e:
            if self._debug:
                self._debug(f"Poll failed: {e}", None)
            self._emit("error", ErrorEventData(error=e))

    def _process_job(self, job: ClaimedJob) -> None:
        """Start processing a job."""
        abort_event = Event()
        active = ActiveJob(
            job=job,
            started_at=time.time(),
            abort_event=abort_event,
        )

        with self._lock:
            if self._intake_closed:
                # stop() already ended its drain window. The claim cannot be
                # undone, but deregistering re-queues it for another worker.
                if self._debug:
                    self._debug(f"Not starting job {job.id}: worker is stopping", None)
                return
            self._active_jobs[job.id] = active

        self._emit(
            "job:claimed",
            JobClaimedEventData(
                job_id=job.id,
                queue_name=job.queue_name,
            ),
        )

        # Start per-job heartbeat
        heartbeat_interval = self._options.lease_duration * self._options.heartbeat_fraction
        self._schedule_job_heartbeat(active, heartbeat_interval)

        # Execute handler in thread pool
        try:
            if self._executor:
                self._executor.submit(self._execute_handler, active)
        except RuntimeError:
            # Executor was shut down between the check above and submit().
            self._cleanup_job(active)

    def _execute_handler(self, active: ActiveJob) -> None:
        """Execute job handler."""
        job = active.job

        self._emit(
            "job:started",
            JobStartedEventData(
                job_id=job.id,
                queue_name=job.queue_name,
            ),
        )

        context = JobContext(
            job_id=job.id,
            queue_name=job.queue_name,
            payload=job.payload,
            retry_count=job.retry_count,
            max_retries=job.max_retries,
            signal=active.abort_event,
        )

        self._start_job_timeout(active)

        try:
            result = self._handler(context)  # type: ignore
        except Exception as e:
            # The handler threw: always report it, even when stop() was requested
            # meanwhile (the abort signal is only a hint to stop early).
            self._fail_job(active, str(e))
        else:
            # Likewise a handler that returned must be completed, never dropped.
            self._complete_job(active, result)
        finally:
            self._cleanup_job(active)

    def _start_job_timeout(self, active: ActiveJob) -> None:
        """Arm the per-job ``timeout_seconds`` once the handler starts running."""
        seconds = active.job.timeout_seconds
        if not seconds or seconds <= 0:
            return
        timer = threading.Timer(seconds, self._on_job_timeout, args=(active,))
        timer.daemon = True
        with self._lock:
            if active.settled:
                return
            active.timeout_timer = timer
        timer.start()

    def _on_job_timeout(self, active: ActiveJob) -> None:
        """The handler ran past the job's ``timeout_seconds``: stop extending its lease."""
        if self._debug:
            self._debug(
                f"Job {active.job.id} exceeded its {active.job.timeout_seconds}s timeout", None
            )
        self._abandon_job(active, "Job timeout exceeded")

    def _abandon_job(self, active: ActiveJob, reason: str) -> None:
        """Give up on a handler that is still running and fail its job.

        A thread cannot be killed, so ``ctx.signal`` is set (handlers that watch
        it stop early) and the handler's eventual return value is dropped: the
        job is failed here and no longer owned by this execution. The slot stays
        counted in ``_abandoned_running`` until the thread really returns.
        """
        active.abort_event.set()
        worker_id = self._claim_settlement(active)
        if worker_id is None:
            return  # the handler already returned; its own ack is in flight
        self._send_fail(active, worker_id, reason)
        with self._lock:
            if self._active_jobs.get(active.job.id) is active:
                del self._active_jobs[active.job.id]
            if not active.abandoned:
                active.abandoned = True
                self._abandoned_running += 1
            if active.heartbeat_timer:
                active.heartbeat_timer.cancel()
            if active.timeout_timer:
                active.timeout_timer.cancel()
            self._idle.notify_all()

    def _claim_settlement(self, active: ActiveJob) -> str | None:
        """Atomically take the right to ack ``active``; returns the worker id or None.

        Only the execution that still owns its job slot may ack, and only once:
        a late return from an abandoned handler, or a duplicate execution that a
        newer claim replaced, gets None and sends nothing.
        """
        with self._lock:
            worker_id = self._worker_id
            if active.settled or self._active_jobs.get(active.job.id) is not active:
                return None
            if not worker_id:
                return None
            active.settled = True
            return worker_id

    def _complete_job(self, active: ActiveJob, result: dict[str, Any] | None) -> bool:
        """Complete an active execution only while it still owns the job slot."""
        job = active.job
        worker_id = self._claim_settlement(active)
        if worker_id is None:
            return False
        try:
            params: dict[str, Any] = {
                "worker_id": worker_id,
                "result": result,
            }
            if job.lease_id is not None:
                params["lease_id"] = job.lease_id
            try:
                self._client.jobs.complete(job.id, params)
            except ConflictError as e:
                # The ack is retried on network errors; if the first attempt had
                # actually landed, the server answers the replay with 409
                # "Job is already completed" -- that is success, not a failure.
                if "already completed" not in e.message.lower():
                    raise

            self._emit(
                "job:completed",
                JobCompletedEventData(
                    job_id=job.id,
                    queue_name=job.queue_name,
                    result=result,
                ),
            )
            return True

        except Exception as e:
            if self._debug:
                self._debug(f"Failed to complete job {job.id}: {e}", None)
            self._emit("error", ErrorEventData(error=e))
            return False

    def _fail_job(self, active: ActiveJob, error_message: str) -> bool:
        """Fail an active execution only while it still owns the job slot."""
        worker_id = self._claim_settlement(active)
        if worker_id is None:
            return False
        return self._send_fail(active, worker_id, error_message)

    def _send_fail(self, active: ActiveJob, worker_id: str, error_message: str) -> bool:
        """Send ``fail`` for an execution whose settlement was already claimed."""
        job = active.job
        will_retry = job.retry_count < job.max_retries
        # The API rejects empty or over-long failure text with 400, which would
        # leave the job processing until its lease expired.
        error_message = coerce_fail_error(error_message)
        try:
            params: dict[str, Any] = {
                "worker_id": worker_id,
                "error": error_message,
            }
            if job.lease_id is not None:
                params["lease_id"] = job.lease_id
            self._client.jobs.fail(job.id, params)

            self._emit(
                "job:failed",
                JobFailedEventData(
                    job_id=job.id,
                    queue_name=job.queue_name,
                    error=error_message,
                    will_retry=will_retry,
                ),
            )
            return True

        except Exception as e:
            if self._debug:
                self._debug(f"Failed to fail job {job.id}: {e}", None)
            self._emit("error", ErrorEventData(error=e))
            return False

    def _cleanup_job(self, active: ActiveJob) -> None:
        """Clean up only the exact execution that finished."""
        with self._lock:
            if self._active_jobs.get(active.job.id) is active:
                del self._active_jobs[active.job.id]
            if active.abandoned:
                # The handler thread is finally back: free its concurrency slot.
                active.abandoned = False
                self._abandoned_running = max(0, self._abandoned_running - 1)
            if active.heartbeat_timer:
                active.heartbeat_timer.cancel()
            if active.timeout_timer:
                active.timeout_timer.cancel()
            self._idle.notify_all()

    def _schedule_job_heartbeat(self, active: ActiveJob, interval: float) -> None:
        """Schedule heartbeats bound to one immutable execution."""
        job = active.job

        def send_heartbeat() -> None:
            try:
                with self._lock:
                    worker_id = self._worker_id
                    if (
                        active.settled
                        or self._active_jobs.get(job.id) is not active
                        or not worker_id
                    ):
                        return
                params: dict[str, Any] = {
                    "worker_id": worker_id,
                    "lease_duration_secs": self._options.lease_duration,
                }
                if job.lease_id is not None:
                    params["lease_id"] = job.lease_id
                self._client.jobs.heartbeat(job.id, params)
            except Exception as e:
                if self._debug:
                    self._debug(f"Job heartbeat failed for {job.id}: {e}", None)
                self._emit("error", ErrorEventData(error=e))

            timer = threading.Timer(interval, send_heartbeat)
            timer.daemon = True
            with self._lock:
                if not active.settled and self._active_jobs.get(job.id) is active:
                    active.heartbeat_timer = timer
                    timer.start()

        timer = threading.Timer(interval, send_heartbeat)
        timer.daemon = True
        with self._lock:
            if self._active_jobs.get(job.id) is active:
                active.heartbeat_timer = timer
                timer.start()

    def _schedule_worker_heartbeat(self, interval: float) -> None:
        """Schedule worker heartbeat (it keeps running while stop() drains)."""

        def send_heartbeat() -> None:
            if self._worker_heartbeat_stop.is_set() or not self._worker_id:
                return

            try:
                self._client.workers.heartbeat(
                    self._worker_id,
                    {
                        "current_jobs": len(self._active_jobs) + self._abandoned_running,
                        "status": "healthy",
                    },
                )
            except Exception as e:
                if self._debug:
                    self._debug(f"Worker heartbeat failed: {e}", None)
                self._emit("error", ErrorEventData(error=e))

            # Reschedule
            if not self._worker_heartbeat_stop.is_set():
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
