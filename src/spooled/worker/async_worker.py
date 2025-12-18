"""
Async Spooled Worker

Worker runtime for processing jobs from a queue (async version).
"""

from __future__ import annotations

import asyncio
import socket
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from spooled.types.jobs import ClaimedJob
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


@dataclass
class ActiveJob:
    """Represents an active job being processed."""

    job: ClaimedJob
    started_at: float
    abort_event: asyncio.Event
    heartbeat_task: asyncio.Task[None] | None = None
    process_task: asyncio.Task[None] | None = None


class AsyncSpooledWorker:
    """
    Async Spooled Worker.

    Example:
        >>> from spooled import AsyncSpooledClient, AsyncSpooledWorker
        >>>
        >>> async def main():
        ...     async with AsyncSpooledClient(api_key="sk_live_...") as client:
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
        worker_type: str = "python",
        version: str = "1.0.0",
        metadata: dict[str, Any] | None = None,
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
            worker_type=worker_type,
            version=version,
            metadata=metadata or {},
        )

        self._state: WorkerState = "idle"
        self._worker_id: str | None = None
        self._handler: AsyncJobHandler | None = None
        self._active_jobs: dict[str, ActiveJob] = {}
        self._poll_task: asyncio.Task[None] | None = None
        self._worker_heartbeat_task: asyncio.Task[None] | None = None
        self._shutdown_event: asyncio.Event | None = None
        self._semaphore: asyncio.Semaphore | None = None

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

    async def start(self) -> None:
        """Start the worker (runs until stopped)."""
        if self._state != "idle":
            raise RuntimeError(f"Cannot start worker in state: {self._state}")

        if not self._handler:
            raise RuntimeError("No job handler registered. Call process() first.")

        self._state = "starting"
        self._shutdown_event = asyncio.Event()
        self._semaphore = asyncio.Semaphore(self._options.concurrency)

        if self._debug:
            self._debug(f"Starting async worker for queue: {self._options.queue_name}", None)

        try:
            # Register with the API
            registration = await self._client.workers.register({
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

            # Start worker heartbeat
            heartbeat_interval = registration.heartbeat_interval_secs
            self._worker_heartbeat_task = asyncio.create_task(
                self._worker_heartbeat_loop(heartbeat_interval)
            )

            # Start polling
            self._state = "running"
            self._emit("started", StartedEventData(
                worker_id=self._worker_id,
                queue_name=self._options.queue_name,
            ))

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

        except Exception as e:
            self._state = "error"
            self._emit("error", ErrorEventData(error=e))
            raise

    async def stop(self) -> None:
        """Stop the worker gracefully."""
        if self._state != "running":
            return

        self._state = "stopping"
        if self._shutdown_event:
            self._shutdown_event.set()

        if self._debug:
            self._debug("Stopping async worker...", None)

        # Cancel worker heartbeat
        if self._worker_heartbeat_task:
            self._worker_heartbeat_task.cancel()
            try:
                await self._worker_heartbeat_task
            except asyncio.CancelledError:
                pass
            self._worker_heartbeat_task = None

        # Signal all active jobs to stop
        for active in self._active_jobs.values():
            active.abort_event.set()
            if active.heartbeat_task:
                active.heartbeat_task.cancel()

        # Wait for active jobs to complete (with timeout)
        if self._active_jobs:
            if self._debug:
                self._debug(
                    f"Waiting for {len(self._active_jobs)} active jobs to complete...",
                    None,
                )

            pending_tasks = [
                a.process_task for a in self._active_jobs.values() if a.process_task
            ]
            if pending_tasks:
                done, pending = await asyncio.wait(
                    pending_tasks,
                    timeout=self._options.shutdown_timeout,
                )

                # Cancel remaining tasks
                for task in pending:
                    task.cancel()

            # Force-fail remaining jobs
            for job_id, active in list(self._active_jobs.items()):
                if self._debug:
                    self._debug(f"Force-failing job {job_id} due to shutdown timeout", None)
                await self._fail_job(active.job, "Worker shutdown timeout")

        # Deregister worker
        if self._worker_id:
            try:
                await self._client.workers.deregister(self._worker_id)
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

    async def _poll(self) -> None:
        """Poll for and claim jobs."""
        if self._state != "running" or not self._worker_id or not self._semaphore:
            return

        # Check capacity
        available_slots = self._options.concurrency - len(self._active_jobs)
        if available_slots <= 0:
            return

        try:
            result = await self._client.jobs.claim({
                "queue_name": self._options.queue_name,
                "worker_id": self._worker_id,
                "limit": available_slots,
                "lease_duration_secs": self._options.lease_duration,
            })

            for job in result.jobs:
                asyncio.create_task(self._process_job(job))

        except Exception as e:
            if self._debug:
                self._debug(f"Poll failed: {e}", None)
            self._emit("error", ErrorEventData(error=e))

    async def _process_job(self, job: ClaimedJob) -> None:
        """Start processing a job."""
        if not self._semaphore:
            return

        async with self._semaphore:
            self._emit("job:claimed", JobClaimedEventData(
                job_id=job.id,
                queue_name=job.queue_name,
            ))

            abort_event = asyncio.Event()
            active = ActiveJob(
                job=job,
                started_at=asyncio.get_event_loop().time(),
                abort_event=abort_event,
            )

            self._active_jobs[job.id] = active

            # Start per-job heartbeat
            heartbeat_interval = (
                self._options.lease_duration * self._options.heartbeat_fraction
            )
            active.heartbeat_task = asyncio.create_task(
                self._job_heartbeat_loop(job.id, heartbeat_interval)
            )

            # Execute handler
            active.process_task = asyncio.current_task()
            await self._execute_handler(active)

    async def _execute_handler(self, active: ActiveJob) -> None:
        """Execute job handler."""
        job = active.job

        self._emit("job:started", JobStartedEventData(
            job_id=job.id,
            queue_name=job.queue_name,
        ))

        context = AsyncJobContext(
            job_id=job.id,
            queue_name=job.queue_name,
            payload=job.payload,
            retry_count=job.retry_count,
            max_retries=job.max_retries,
            signal=active.abort_event,
        )

        try:
            result = await self._handler(context)  # type: ignore

            # Check if aborted
            if active.abort_event.is_set():
                if self._debug:
                    self._debug(f"Job {job.id} was aborted", None)
                return

            # Complete the job
            await self._complete_job(job, result)

        except Exception as e:
            # Check if aborted
            if active.abort_event.is_set():
                if self._debug:
                    self._debug(f"Job {job.id} was aborted", None)
                return

            error_message = str(e)
            await self._fail_job(job, error_message)

        finally:
            await self._cleanup_job(job.id)

    async def _complete_job(self, job: ClaimedJob, result: dict[str, Any] | None) -> None:
        """Complete a job."""
        if not self._worker_id:
            return

        try:
            await self._client.jobs.complete(job.id, {
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

    async def _fail_job(self, job: ClaimedJob, error_message: str) -> None:
        """Fail a job."""
        if not self._worker_id:
            return

        will_retry = job.retry_count < job.max_retries

        try:
            await self._client.jobs.fail(job.id, {
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

    async def _cleanup_job(self, job_id: str) -> None:
        """Clean up after job completion."""
        active = self._active_jobs.pop(job_id, None)
        if active and active.heartbeat_task:
            active.heartbeat_task.cancel()
            try:
                await active.heartbeat_task
            except asyncio.CancelledError:
                pass

    async def _job_heartbeat_loop(self, job_id: str, interval: float) -> None:
        """Job heartbeat loop."""
        while job_id in self._active_jobs and self._worker_id:
            await asyncio.sleep(interval)

            if job_id not in self._active_jobs or not self._worker_id:
                break

            try:
                await self._client.jobs.heartbeat(job_id, {
                    "worker_id": self._worker_id,
                    "lease_duration_secs": self._options.lease_duration,
                })
            except Exception as e:
                if self._debug:
                    self._debug(f"Job heartbeat failed for {job_id}: {e}", None)

    async def _worker_heartbeat_loop(self, interval: float) -> None:
        """Worker heartbeat loop."""
        while self._state == "running" and self._worker_id:
            await asyncio.sleep(interval)

            if self._state != "running" or not self._worker_id:
                break

            try:
                await self._client.workers.heartbeat(self._worker_id, {
                    "current_jobs": len(self._active_jobs),
                    "status": "healthy",
                })
            except Exception as e:
                if self._debug:
                    self._debug(f"Worker heartbeat failed: {e}", None)

    def _emit(self, event: WorkerEvent, data: Any) -> None:
        """Emit an event to handlers."""
        handlers = self._event_handlers.get(event, [])
        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                if self._debug:
                    self._debug(f"Event handler error for {event}: {e}", None)
