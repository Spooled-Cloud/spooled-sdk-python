"""A lost lease must abort the handler and must not ack the job.

SDK-02: a job heartbeat that returns 409 LEASE_EXPIRED (lease timed out, or
lease_id does not match) used to be logged and retried. The handler kept
running and then complete/fail'd with the stale lease, so the same payload
could run on two workers.
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

from spooled.errors import ConflictError
from spooled.worker.async_worker import ActiveJob as AsyncActiveJob
from spooled.worker.worker import ActiveJob as SyncActiveJob
from tests.unit.test_worker_drain import (
    FakeClient,
    _async_worker,
    _await_for,
    _job,
    _run_sync,
    _sync_worker,
    _wait_for,
)

_LEASE_EXPIRED = ConflictError(
    "lease_id does not match the job's current lease; this worker no longer holds it",
    code="LEASE_EXPIRED",
)


def _lease_client(*, is_async: bool = False) -> FakeClient:
    client = FakeClient([_job(timeout_seconds=0)], is_async=is_async)
    client.heartbeat_error = _LEASE_EXPIRED
    return client


class TestSyncLeaseLost:
    def test_expired_heartbeat_signals_and_skips_complete(self) -> None:
        client = _lease_client()
        worker = _sync_worker(client, lease_duration=5, heartbeat_fraction=0.02)
        started, release = threading.Event(), threading.Event()
        saw_signal: list[bool] = []
        lost: list[Any] = []
        errors: list[Any] = []
        worker.on("job:lease_lost", lost.append)
        worker.on("error", errors.append)

        @worker.process
        def handle(ctx: Any) -> dict[str, Any]:
            started.set()
            release.wait(5)
            saw_signal.append(ctx.signal.is_set())
            return {"stale": True}

        runner = _run_sync(worker)
        try:
            assert started.wait(5)
            _wait_for(lambda: len(lost) == 1)
            release.set()
            _wait_for(lambda: worker.active_job_count == 0)
            time.sleep(0.25)
        finally:
            release.set()
            worker.stop()
            runner.join(5)

        assert saw_signal == [True]
        assert lost[0].operation == "heartbeat"
        assert lost[0].lease_id == "lease-1"
        assert lost[0].job_id == "job-1"
        assert errors == []
        assert client.of("complete") == []
        assert client.of("fail") == []
        assert len(client.of("job_heartbeat")) == 1
        assert len(lost) == 1

    def test_expired_heartbeat_skips_fail_when_the_handler_raises(self) -> None:
        client = _lease_client()
        worker = _sync_worker(client, lease_duration=5, heartbeat_fraction=0.02)
        started, release = threading.Event(), threading.Event()
        failed: list[Any] = []
        worker.on("job:failed", failed.append)

        @worker.process
        def handle(ctx: Any) -> None:
            started.set()
            release.wait(5)
            raise RuntimeError("handler gave up after the signal")

        runner = _run_sync(worker)
        try:
            assert started.wait(5)
            _wait_for(lambda: client.of("job_heartbeat") != [])
            # The signal is set before the handler is released, so the raise
            # happens after the lease is already gone.
            _wait_for(lambda: worker._active_jobs["job-1"].abort_event.is_set())
            release.set()
            _wait_for(lambda: worker.active_job_count == 0)
        finally:
            release.set()
            worker.stop()
            runner.join(5)

        assert client.of("fail") == []
        assert client.of("complete") == []
        assert failed == []

    def test_other_heartbeat_conflict_still_completes(self) -> None:
        client = FakeClient([_job(timeout_seconds=0)])
        client.heartbeat_error = ConflictError("Job is already completed", code="CONFLICT")
        worker = _sync_worker(client, lease_duration=5, heartbeat_fraction=0.02)
        started, release = threading.Event(), threading.Event()
        saw_signal: list[bool] = []

        @worker.process
        def handle(ctx: Any) -> dict[str, Any]:
            started.set()
            release.wait(5)
            saw_signal.append(ctx.signal.is_set())
            return {"ok": True}

        runner = _run_sync(worker)
        try:
            assert started.wait(5)
            _wait_for(lambda: len(client.of("job_heartbeat")) >= 1)
            release.set()
            _wait_for(lambda: "complete" in client.names())
        finally:
            release.set()
            worker.stop()
            runner.join(5)

        assert saw_signal == [False]
        assert client.of("complete")[0][1]["result"] == {"ok": True}

    def test_complete_and_fail_are_not_sent_once_the_lease_is_lost(self) -> None:
        client = FakeClient([])
        worker = _sync_worker(client)
        worker._worker_id = "worker-1"
        active = SyncActiveJob(job=_job(), started_at=0.0, abort_event=threading.Event())
        active.lease_lost = True
        worker._active_jobs[active.job.id] = active

        assert worker._complete_job(active, {"ok": True}) is False
        assert worker._fail_job(active, "boom") is False
        assert client.of("complete") == []
        assert client.of("fail") == []

    def test_complete_that_answers_lease_expired_is_not_success(self) -> None:
        client = FakeClient([])
        client.complete_error = ConflictError(
            "Job lease expired and cannot be extended", code="LEASE_EXPIRED"
        )
        worker = _sync_worker(client)
        worker._worker_id = "worker-1"
        lost: list[Any] = []
        done: list[Any] = []
        errors: list[Any] = []
        worker.on("job:lease_lost", lost.append)
        worker.on("job:completed", done.append)
        worker.on("error", errors.append)
        active = SyncActiveJob(job=_job(), started_at=0.0, abort_event=threading.Event())
        worker._active_jobs[active.job.id] = active

        assert worker._complete_job(active, {"ok": True}) is False

        assert len(client.of("complete")) == 1
        assert done == []
        assert errors == []
        assert lost[0].operation == "complete"
        assert active.abort_event.is_set()

    def test_fail_that_answers_lease_expired_is_not_a_failure(self) -> None:
        client = FakeClient([])
        client.fail_error = _LEASE_EXPIRED
        worker = _sync_worker(client)
        worker._worker_id = "worker-1"
        lost: list[Any] = []
        failed: list[Any] = []
        errors: list[Any] = []
        worker.on("job:lease_lost", lost.append)
        worker.on("job:failed", failed.append)
        worker.on("error", errors.append)
        active = SyncActiveJob(job=_job(), started_at=0.0, abort_event=threading.Event())
        worker._active_jobs[active.job.id] = active

        assert worker._fail_job(active, "boom") is False

        assert len(client.of("fail")) == 1
        assert failed == []
        assert errors == []
        assert lost[0].operation == "fail"
        assert active.abort_event.is_set()


class TestAsyncLeaseLost:
    async def test_expired_heartbeat_cancels_handler_and_skips_complete(self) -> None:
        client = _lease_client(is_async=True)
        worker = _async_worker(client, lease_duration=5, heartbeat_fraction=0.02)
        started = asyncio.Event()
        saw_signal: list[bool] = []
        lost: list[Any] = []
        errors: list[Any] = []
        worker.on("job:lease_lost", lost.append)
        worker.on("error", errors.append)

        @worker.process
        async def handle(ctx: Any) -> dict[str, Any]:
            started.set()
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                saw_signal.append(ctx.signal.is_set())
            return {"stale": True}

        runner = asyncio.create_task(worker.start())
        try:
            await asyncio.wait_for(started.wait(), 5)
            await _await_for(lambda: len(lost) == 1)
            await _await_for(lambda: worker.active_job_count == 0)
            await asyncio.sleep(0.25)
        finally:
            await worker.stop()
            await asyncio.wait_for(runner, 5)

        assert saw_signal == [True]
        assert lost[0].operation == "heartbeat"
        assert lost[0].lease_id == "lease-1"
        assert errors == []
        assert client.of("complete") == []
        assert client.of("fail") == []
        assert len(client.of("job_heartbeat")) == 1
        assert len(lost) == 1

    async def test_cancelled_handler_is_not_failed(self) -> None:
        client = _lease_client(is_async=True)
        worker = _async_worker(client, lease_duration=5, heartbeat_fraction=0.02)
        started = asyncio.Event()
        cancelled = asyncio.Event()
        failed: list[Any] = []
        worker.on("job:failed", failed.append)

        @worker.process
        async def handle(ctx: Any) -> None:
            started.set()
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                cancelled.set()
                raise

        runner = asyncio.create_task(worker.start())
        try:
            await asyncio.wait_for(started.wait(), 5)
            await _await_for(lambda: cancelled.is_set())
            await _await_for(lambda: worker.active_job_count == 0)
        finally:
            await worker.stop()
            await asyncio.wait_for(runner, 5)

        assert client.of("fail") == []
        assert client.of("complete") == []
        assert failed == []

    async def test_complete_and_fail_are_not_sent_once_the_lease_is_lost(self) -> None:
        client = FakeClient([], is_async=True)
        worker = _async_worker(client)
        worker._worker_id = "worker-1"
        active = AsyncActiveJob(job=_job(), started_at=0.0, abort_event=asyncio.Event())
        active.lease_lost = True
        worker._active_jobs[active.job.id] = active

        assert await worker._complete_job(active, {"ok": True}) is False
        assert await worker._fail_job(active, "boom") is False
        assert client.of("complete") == []
        assert client.of("fail") == []

    async def test_complete_that_answers_lease_expired_is_not_success(self) -> None:
        client = FakeClient([], is_async=True)
        client.complete_error = ConflictError(
            "Job lease expired and cannot be extended", code="LEASE_EXPIRED"
        )
        worker = _async_worker(client)
        worker._worker_id = "worker-1"
        lost: list[Any] = []
        done: list[Any] = []
        errors: list[Any] = []
        worker.on("job:lease_lost", lost.append)
        worker.on("job:completed", done.append)
        worker.on("error", errors.append)
        active = AsyncActiveJob(job=_job(), started_at=0.0, abort_event=asyncio.Event())
        worker._active_jobs[active.job.id] = active

        assert await worker._complete_job(active, {"ok": True}) is False

        assert len(client.of("complete")) == 1
        assert done == []
        assert errors == []
        assert lost[0].operation == "complete"
        assert active.abort_event.is_set()

    async def test_fail_that_answers_lease_expired_is_not_a_failure(self) -> None:
        client = FakeClient([], is_async=True)
        client.fail_error = _LEASE_EXPIRED
        worker = _async_worker(client)
        worker._worker_id = "worker-1"
        lost: list[Any] = []
        failed: list[Any] = []
        errors: list[Any] = []
        worker.on("job:lease_lost", lost.append)
        worker.on("job:failed", failed.append)
        worker.on("error", errors.append)
        active = AsyncActiveJob(job=_job(), started_at=0.0, abort_event=asyncio.Event())
        worker._active_jobs[active.job.id] = active

        assert await worker._fail_job(active, "boom") is False

        assert len(client.of("fail")) == 1
        assert failed == []
        assert errors == []
        assert lost[0].operation == "fail"
        assert active.abort_event.is_set()
