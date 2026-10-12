"""
Async Spooled Worker

Worker runtime for processing jobs from a queue (async version).
"""

from __future__ import annotations

import asyncio
import socket
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from spooled._version import __version__
from spooled.errors import ConflictError
from spooled.types.jobs import ClaimedJob, coerce_fail_error
from spooled.worker.types import (
    AsyncJobContext,
    AsyncJobHandler,
    ErrorEventData,
    JobClaimedEventData,
    JobCompletedEventData,
    JobFailedEventData,
    JobStartedEventData,
    SpooledWorkerOptions,
    StartedEventData,
    StoppedEventData,
    WorkerEvent,
    WorkerState,
)

if TYPE_CHECKING:
    from spooled.async_client import AsyncSpooledClient


# How long stop() waits for cancelled handlers (and acks already in flight) once
# the shutdown timeout is over, before it deregisters.
ACK_GRACE_SECONDS = 10.0


@dataclass
class ActiveJob:
    """Represents an active job being processed."""

    job: ClaimedJob
    started_at: float
    abort_event: asyncio.Event
    heartbeat_task: asyncio.Task[None] | None = None
    process_task: asyncio.Task[None] | None = None
    # Set by whoever acks (complete/fail) first, so a handler returning at the
    # same moment as a timeout never sends both.
    settled: bool = False
    # Why stop() cancelled the handler; the cancelled task fails the job with it.
    cancel_reason: str | None = None


class AsyncSpooledWorker:
    """
    Async Spooled Worker.

    Example:
        >>> from spooled import AsyncSpooledClient, AsyncSpooledWorker
        >>>
        >>> async def main():
        ...     async with AsyncSpooledClient(api_key="sp_live_...") as client:
        ...         worker = AsyncSpooledWorker(client, queue_name="my-queue")
        ...
        ...         @worker.process
        ...         async def handle_job(ctx):
        ...             print(f"Processing job {ctx.job_id}")
        ...             return {"success": True}
        ...
        ...         await worker.start()
    """

    def __init__(
        self,
        client: AsyncSpooledClient,
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
    ) -> None:
        """
        Initialize the async worker.

        Args:
            client: AsyncSpooledClient instance
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
        )

        self._state: WorkerState = "idle"
        self._worker_id: str | None = None
        self._handler: AsyncJobHandler | None = None
        self._active_jobs: dict[str, ActiveJob] = {}
        self._poll_task: asyncio.Task[None] | None = None
        self._worker_heartbeat_task: asyncio.Task[None] | None = None
        self._shutdown_event: asyncio.Event | None = None
        # Guards ownership checks of ``_active_jobs``; never held across I/O.
        self._active_jobs_lock = asyncio.Lock()
        # Strong references to the per-job tasks: the event loop only keeps weak
        # ones, so an unreferenced task could be garbage collected mid-job.
        self._job_tasks: set[asyncio.Task[None]] = set()
        # Closed by stop() once the drain window is over: a job claimed by a poll
        # that was already in flight is then left unstarted (deregister re-queues it).
        self._intake_closed = False
        # Set when stop() has fully finished, so start() can wait for it.
        self._stopped_event: asyncio.Event | None = None

        # Event handlers
        self._event_handlers: dict[WorkerEvent, list[Callable[..., Any]]] = {}

        # Debug function from client
        config = client.get_config()
        self._debug = config.debug_fn

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

    def process(
        self, handler: Callable[[AsyncJobContext], Coroutine[Any, Any, dict[str, Any] | None]]
    ) -> Callable[[AsyncJobContext], Coroutine[Any, Any, dict[str, Any] | None]]:
        """
        Register job handler (decorator).

        Example:
            >>> @worker.process
            ... async def handle_job(ctx):
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

    async def start(self) -> None:
        """Start the worker (runs until it has fully stopped)."""
        if self._state != "idle":
            raise RuntimeError(f"Cannot start worker in state: {self._state}")

        if not self._handler:
            raise RuntimeError("No job handler registered. Call process() first.")

        self._state = "starting"
        self._shutdown_event = asyncio.Event()
        self._stopped_event = asyncio.Event()
        self._intake_closed = False

        if self._debug:
            self._debug(f"Starting async worker for queue: {self._options.queue_name}", None)

        try:
            # Register with the API
            registration = await self._client.workers.register(
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

            # Start worker heartbeat
            heartbeat_interval = registration.heartbeat_interval_secs
            self._worker_heartbeat_task = asyncio.create_task(
                self._worker_heartbeat_loop(heartbeat_interval)
            )

            # Start polling
            self._state = "running"
            self._emit(
                "started",
                StartedEventData(
                    worker_id=self._worker_id,
                    queue_name=self._options.queue_name,
                ),
            )

            # Poll loop
            while self._state == "running":
                await self._poll()
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self._options.poll_interval,
                    )
                    break  # Shutdown requested
                except asyncio.TimeoutError:
                    pass  # Continue polling

            # stop() runs in its own task: hold start() until it has drained and
            # deregistered, so callers can safely close the client once start()
            # returns.
            if self.state == "stopping":
                await self._stopped_event.wait()

        except Exception as e:
            self._state = "error"
            self._emit("error", ErrorEventData(error=e))
            raise

    async def stop(self) -> None:
        """Stop the worker gracefully.

        Stops claiming new jobs, then lets running handlers finish for up to
        ``shutdown_timeout`` seconds: a handler that returns (or raises) in that
        window is still acked with ``complete`` (or ``fail``) and its job heartbeat
        keeps the lease alive. Only handlers still running after the timeout are
        signalled through ``ctx.signal``, cancelled, and failed with "Worker
        shutdown timeout". The worker deregisters last, because deregistering
        re-queues every job the worker still holds.
        """
        if self._state != "running":
            return

        self._state = "stopping"
        if self._shutdown_event:
            self._shutdown_event.set()

        try:
            if self._debug:
                self._debug("Stopping async worker...", None)

            # Drain: job heartbeats and the worker heartbeat keep running so the
            # leases stay valid while handlers finish. Handlers are not signalled
            # yet -- aborting them first is what used to throw their results away.
            loop = asyncio.get_running_loop()
            deadline = loop.time() + self._options.shutdown_timeout
            if self._active_jobs and self._debug:
                self._debug(
                    f"Waiting for {len(self._active_jobs)} active jobs to complete...",
                    None,
                )
            while True:
                running = {t for t in self._job_tasks if not t.done()}
                remaining = deadline - loop.time()
                if not running or remaining <= 0:
                    # Closed in the same step that observes the end of the wait, so
                    # a poll that was already in flight cannot register a job after
                    # this point (there is no await between the check and the flag).
                    self._intake_closed = True
                    break
                await asyncio.wait(running, timeout=remaining)

            # Whatever is still running outlived the shutdown timeout: signal and
            # cancel it; each cancelled task fails its own job with the reason.
            for active in list(self._active_jobs.values()):
                if self._debug:
                    self._debug(f"Force-failing job {active.job.id} due to shutdown timeout", None)
                active.cancel_reason = "Worker shutdown timeout"
                active.abort_event.set()
                # A handler that already returned is mid-ack: cancelling it would
                # interrupt the request, so it gets the ack grace period instead.
                if active.process_task and not active.process_task.done() and not active.settled:
                    active.process_task.cancel()
            cancelled = {t for t in self._job_tasks if not t.done()}
            if cancelled:
                await asyncio.wait(cancelled, timeout=ACK_GRACE_SECONDS)
            # Anything still listed never reached its handler or swallowed the
            # cancellation: fail it here so no claimed job is left silent.
            for active in list(self._active_jobs.values()):
                await self._abandon_job(active, "Worker shutdown timeout")

            # Stop the worker heartbeat now that every job is settled
            if self._worker_heartbeat_task:
                self._worker_heartbeat_task.cancel()
                try:
                    await self._worker_heartbeat_task
                except asyncio.CancelledError:
                    pass
                self._worker_heartbeat_task = None

            # Deregister worker (last: this re-queues any job still unacked)
            if self._worker_id:
                try:
                    await self._client.workers.deregister(self._worker_id)
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
            if self._stopped_event:
                self._stopped_event.set()

    async def _poll(self) -> None:
        """Poll for and claim jobs."""
        if self._state != "running" or not self._worker_id:
            return

        # Check capacity
        available_slots = self._options.concurrency - len(self._active_jobs)
        if available_slots <= 0:
            return

        try:
            result = await self._client.jobs.claim(
                {
                    "queue_name": self._options.queue_name,
                    "worker_id": self._worker_id,
                    "limit": available_slots,
                    "lease_duration_secs": self._options.lease_duration,
                }
            )

            for job in result.jobs:
                active = self._register_job(job)
                if active is None:
                    continue
                task = asyncio.create_task(self._process_job(active))
                active.process_task = task
                self._job_tasks.add(task)
                task.add_done_callback(self._job_tasks.discard)

        except Exception as e:
            if self._debug:
                self._debug(f"Poll failed: {e}", None)
            self._emit("error", ErrorEventData(error=e))

    def _register_job(self, job: ClaimedJob) -> ActiveJob | None:
        """Track a claimed job right away so the next poll counts its slot."""
        if self._intake_closed:
            # stop() already ended its drain window. The claim cannot be undone,
            # but deregistering re-queues it for another worker.
            if self._debug:
                self._debug(f"Not starting job {job.id}: worker is stopping", None)
            return None

        active = ActiveJob(
            job=job,
            started_at=time.time(),
            abort_event=asyncio.Event(),
        )
        self._active_jobs[job.id] = active
        self._emit(
            "job:claimed",
            JobClaimedEventData(
                job_id=job.id,
                queue_name=job.queue_name,
            ),
        )
        return active

    async def _process_job(self, active: ActiveJob) -> None:
        """Start processing a registered job."""
        # Start per-job heartbeat
        heartbeat_interval = self._options.lease_duration * self._options.heartbeat_fraction
        active.heartbeat_task = asyncio.create_task(
            self._job_heartbeat_loop(active, heartbeat_interval)
        )

        # Execute handler
        await self._execute_handler(active)

    async def _execute_handler(self, active: ActiveJob) -> None:
        """Execute job handler."""
        job = active.job

        self._emit(
            "job:started",
            JobStartedEventData(
                job_id=job.id,
                queue_name=job.queue_name,
            ),
        )

        context = AsyncJobContext(
            job_id=job.id,
            queue_name=job.queue_name,
            payload=job.payload,
            retry_count=job.retry_count,
            max_retries=job.max_retries,
            signal=active.abort_event,
        )

        try:
            ok, outcome = await self._run_handler(active, context)
            if ok:
                # A handler that returned must be completed, never dropped, even
                # when stop() was requested meanwhile (the signal is only a hint).
                await self._complete_job(active, outcome)
            else:
                # Likewise a handler that threw is always reported as failed.
                await self._fail_job(active, str(outcome))
        except asyncio.TimeoutError:
            # The job's timeout_seconds elapsed: stop extending its lease, tell
            # the handler to wind down, and fail the job.
            active.abort_event.set()
            await self._fail_job(active, "Job timeout exceeded")
        except asyncio.CancelledError:
            reason = active.cancel_reason
            if reason is None:
                raise  # a genuine external cancellation, not stop()'s timeout
            await self._fail_job(active, reason)
        finally:
            await self._cleanup_job(active)

    async def _run_handler(self, active: ActiveJob, context: AsyncJobContext) -> tuple[bool, Any]:
        """Run the handler, returning ``(True, result)`` or ``(False, exception)``.

        Raises ``asyncio.TimeoutError`` only when the job's ``timeout_seconds``
        elapses (an ``asyncio.TimeoutError`` raised by the handler itself is a
        failure like any other exception).
        """

        async def call() -> tuple[bool, Any]:
            try:
                return True, await self._handler(context)  # type: ignore
            except Exception as exc:
                return False, exc

        seconds = active.job.timeout_seconds
        if not seconds or seconds <= 0:
            return await call()

        task = asyncio.ensure_future(call())
        try:
            done, _ = await asyncio.wait({task}, timeout=seconds)
        except asyncio.CancelledError:
            task.cancel()  # stop()'s cancellation reaches the handler too
            raise
        if task in done:
            return task.result()
        # Cancel without waiting for it: a handler that ignores cancellation must
        # not keep the job (and its lease) alive.
        task.cancel()
        raise asyncio.TimeoutError

    async def _claim_settlement(self, active: ActiveJob) -> str | None:
        """Take the right to ack ``active``; returns the worker id or None.

        Only the execution that still owns its job slot may ack, and only once:
        a late return from an abandoned handler, or a duplicate execution that a
        newer claim replaced, gets None and sends nothing.
        """
        async with self._active_jobs_lock:
            worker_id = self._worker_id
            if active.settled or self._active_jobs.get(active.job.id) is not active:
                return None
            if not worker_id:
                return None
            active.settled = True
            return worker_id

    async def _abandon_job(self, active: ActiveJob, reason: str) -> None:
        """Fail a job whose handler never settled it, and drop it from the worker."""
        active.abort_event.set()
        worker_id = await self._claim_settlement(active)
        if worker_id is not None:
            await self._send_fail(active, worker_id, reason)
        await self._cleanup_job(active)

    async def _complete_job(self, active: ActiveJob, result: dict[str, Any] | None) -> bool:
        """Complete an active execution only while it still owns the job slot."""
        job = active.job
        worker_id = await self._claim_settlement(active)
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
                await self._client.jobs.complete(job.id, params)
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

    async def _fail_job(self, active: ActiveJob, error_message: str) -> bool:
        """Fail an active execution only while it still owns the job slot."""
        worker_id = await self._claim_settlement(active)
        if worker_id is None:
            return False
        return await self._send_fail(active, worker_id, error_message)

    async def _send_fail(self, active: ActiveJob, worker_id: str, error_message: str) -> bool:
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
            await self._client.jobs.fail(job.id, params)

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

    async def _cleanup_job(self, active: ActiveJob) -> None:
        """Clean up only the exact execution that finished."""
        async with self._active_jobs_lock:
            if self._active_jobs.get(active.job.id) is active:
                del self._active_jobs[active.job.id]
        if active.heartbeat_task and active.heartbeat_task is not asyncio.current_task():
            active.heartbeat_task.cancel()
            try:
                await active.heartbeat_task
            except asyncio.CancelledError:
                pass

    async def _job_heartbeat_loop(self, active: ActiveJob, interval: float) -> None:
        """Send heartbeats bound to one immutable execution."""
        job = active.job
        while True:
            await asyncio.sleep(interval)

            async with self._active_jobs_lock:
                worker_id = self._worker_id
                if active.settled or self._active_jobs.get(job.id) is not active or not worker_id:
                    break

            try:
                params: dict[str, Any] = {
                    "worker_id": worker_id,
                    "lease_duration_secs": self._options.lease_duration,
                }
                if job.lease_id is not None:
                    params["lease_id"] = job.lease_id
                await self._client.jobs.heartbeat(job.id, params)
            except Exception as e:
                if self._debug:
                    self._debug(f"Job heartbeat failed for {job.id}: {e}", None)
                self._emit("error", ErrorEventData(error=e))

    async def _worker_heartbeat_loop(self, interval: float) -> None:
        """Worker heartbeat loop (it keeps running while stop() drains)."""
        while self._state in ("running", "stopping") and self._worker_id:
            await asyncio.sleep(interval)

            if self._state not in ("running", "stopping") or not self._worker_id:
                break

            try:
                await self._client.workers.heartbeat(
                    self._worker_id,
                    {
                        "current_jobs": len(self._active_jobs),
                        "status": "healthy",
                    },
                )
            except Exception as e:
                if self._debug:
                    self._debug(f"Worker heartbeat failed: {e}", None)
                self._emit("error", ErrorEventData(error=e))

    def _emit(self, event: WorkerEvent, data: Any) -> None:
        """Emit an event to handlers."""
        handlers = self._event_handlers.get(event, [])
        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                if self._debug:
                    self._debug(f"Event handler error for {event}: {e}", None)
