"""Graceful stop, job timeouts and failure-text coercion for both workers.

SDKNP-01: ``stop()`` used to set every handler's abort signal first, and a handler
that then returned normally had its result thrown away (no ``complete``/``fail``);
deregistering re-queued the job and it ran twice. SDKNP-16: ``timeout_seconds`` was
never enforced. Brief item 4: an empty or over-long failure text was rejected by
the API with 400, leaving the job ``processing`` until its lease expired.
"""

from __future__ import annotations

import asyncio
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest

from spooled.types.jobs import (
    FAIL_ERROR_FALLBACK,
    FAIL_ERROR_MAX_LENGTH,
    ClaimedJob,
    coerce_fail_error,
)
from spooled.worker import AsyncSpooledWorker, SpooledWorker
from spooled.worker.async_worker import ActiveJob as AsyncActiveJob
from spooled.worker.worker import ActiveJob as SyncActiveJob


def _job(
    job_id: str = "job-1",
    timeout_seconds: int = 300,
    lease_id: str = "lease-1",
    max_retries: int = 3,
) -> ClaimedJob:
    return ClaimedJob(
        id=job_id,
        queue_name="q",
        payload={},
        retry_count=0,
        max_retries=max_retries,
        timeout_seconds=timeout_seconds,
        lease_id=lease_id,
    )


class FakeClient:
    """Records every call in order; claims each queued job once."""

    def __init__(self, jobs: list[ClaimedJob], *, is_async: bool = False) -> None:
        self.calls: list[tuple[str, Any]] = []
        self._pending = list(jobs)
        self._is_async = is_async
        self.heartbeat_error: Exception | None = None
        self.fail_error: Exception | None = None
        self.complete_error: Exception | None = None
        self.workers = SimpleNamespace(
            register=self._wrap(self._register),
            heartbeat=self._wrap(lambda *a, **k: None),
            deregister=self._wrap(self._deregister),
        )
        self.jobs = SimpleNamespace(
            claim=self._wrap(self._claim),
            complete=self._wrap(self._complete),
            fail=self._wrap(self._fail),
            heartbeat=self._wrap(self._heartbeat),
        )

    def get_config(self) -> Any:
        return SimpleNamespace(debug_fn=None)

    def _wrap(self, fn: Any) -> Any:
        if not self._is_async:
            return fn

        async def call(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        return call

    def _register(self, _params: Any) -> Any:
        return SimpleNamespace(id="worker-1", heartbeat_interval_secs=30)

    def _claim(self, _params: Any) -> Any:
        jobs, self._pending = self._pending, []
        return SimpleNamespace(jobs=jobs)

    def _complete(self, job_id: str, params: Any) -> None:
        self.calls.append(("complete", (job_id, params)))
        if self.complete_error is not None:
            raise self.complete_error

    def _fail(self, job_id: str, params: Any) -> None:
        self.calls.append(("fail", (job_id, params)))
        if self.fail_error is not None:
            raise self.fail_error

    def _heartbeat(self, job_id: str, params: Any) -> None:
        self.calls.append(("job_heartbeat", (job_id, params)))
        if self.heartbeat_error is not None:
            raise self.heartbeat_error

    def _deregister(self, worker_id: str) -> None:
        self.calls.append(("deregister", worker_id))

    def names(self) -> list[str]:
        return [name for name, _ in self.calls if name != "job_heartbeat"]

    def of(self, name: str) -> list[Any]:
        return [payload for n, payload in self.calls if n == name]


def _wait_for(predicate: Any, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not reached in time")


async def _await_for(predicate: Any, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition not reached in time")


# ─────────────────────────────────────────────────────────────────────────────
# coerce_fail_error
# ─────────────────────────────────────────────────────────────────────────────


class TestCoerceFailError:
    def test_empty_becomes_fallback(self) -> None:
        assert coerce_fail_error("") == FAIL_ERROR_FALLBACK == "Job failed"

    def test_long_text_is_truncated_to_2048_characters(self) -> None:
        assert coerce_fail_error("x" * 5000) == "x" * FAIL_ERROR_MAX_LENGTH
        assert len(coerce_fail_error("é" * 5000)) == 2048

    def test_multibyte_text_is_cut_on_a_character_boundary(self) -> None:
        text = "日本語" * 1000  # 3000 characters, 9000 UTF-8 bytes
        cut = coerce_fail_error(text)
        assert cut == text[:2048]
        cut.encode("utf-8")  # a split code point would raise here

    def test_short_text_is_untouched(self) -> None:
        assert coerce_fail_error("boom") == "boom"


def _sync_worker(client: FakeClient, **kwargs: Any) -> SpooledWorker:
    options: dict[str, Any] = {
        "poll_interval": 0.05,
        "lease_duration": 5,
        "shutdown_timeout": 5.0,
    }
    options.update(kwargs)
    return SpooledWorker(client, "q", **options)  # type: ignore[arg-type]


def _run_sync(worker: SpooledWorker) -> threading.Thread:
    thread = threading.Thread(target=worker.start, daemon=True)
    thread.start()
    return thread


class TestSyncWorkerDrain:
    def test_stop_lets_a_running_handler_finish_and_completes_it(self) -> None:
        client = FakeClient([_job()])
        worker = _sync_worker(client)
        started, release = threading.Event(), threading.Event()
        seen_signal: list[bool] = []

        @worker.process
        def handle(ctx: Any) -> dict[str, Any]:
            started.set()
            release.wait(5)
            seen_signal.append(ctx.signal.is_set())
            return {"ok": True}

        runner = _run_sync(worker)
        assert started.wait(5)

        stopper = threading.Thread(target=worker.stop)
        stopper.start()
        _wait_for(lambda: worker.state == "stopping")
        time.sleep(0.2)
        # Still draining: nothing acked, nothing deregistered, handler not told to stop.
        assert client.names() == []
        assert worker.state == "stopping"

        release.set()
        stopper.join(5)
        runner.join(5)

        assert not stopper.is_alive()
        assert seen_signal == [False]
        assert client.names() == ["complete", "deregister"]
        job_id, params = client.of("complete")[0]
        assert job_id == "job-1"
        assert params["result"] == {"ok": True}
        assert params["lease_id"] == "lease-1"
        assert worker.state == "stopped"

    def test_job_heartbeat_keeps_running_while_draining(self) -> None:
        client = FakeClient([_job()])
        worker = _sync_worker(client, lease_duration=5, heartbeat_fraction=0.02)
        started, release = threading.Event(), threading.Event()

        @worker.process
        def handle(ctx: Any) -> None:
            started.set()
            release.wait(5)

        runner = _run_sync(worker)
        assert started.wait(5)
        stopper = threading.Thread(target=worker.stop)
        stopper.start()
        _wait_for(lambda: worker.state == "stopping")
        before = len(client.of("job_heartbeat"))
        # stop() used to cancel the timers at once, so the lease could lapse mid-drain.
        _wait_for(lambda: len(client.of("job_heartbeat")) > before)
        release.set()
        stopper.join(5)
        runner.join(5)

    def test_stop_fails_a_handler_that_raised_during_the_drain(self) -> None:
        client = FakeClient([_job()])
        worker = _sync_worker(client)
        started, release = threading.Event(), threading.Event()

        @worker.process
        def handle(ctx: Any) -> None:
            started.set()
            release.wait(5)
            raise RuntimeError("kaput")

        runner = _run_sync(worker)
        assert started.wait(5)
        stopper = threading.Thread(target=worker.stop)
        stopper.start()
        _wait_for(lambda: worker.state == "stopping")
        release.set()
        stopper.join(5)
        runner.join(5)

        assert client.names() == ["fail", "deregister"]
        assert client.of("fail")[0][1]["error"] == "kaput"

    def test_handler_still_running_after_the_timeout_is_failed_then_deregistered(self) -> None:
        client = FakeClient([_job()])
        worker = _sync_worker(client, shutdown_timeout=0.3)
        started, release = threading.Event(), threading.Event()
        signal_seen = threading.Event()

        @worker.process
        def handle(ctx: Any) -> dict[str, Any]:
            started.set()
            release.wait(5)
            if ctx.signal.is_set():
                signal_seen.set()
            return {"late": True}

        runner = _run_sync(worker)
        assert started.wait(5)
        began = time.monotonic()
        worker.stop()
        assert time.monotonic() - began >= 0.3

        assert client.names() == ["fail", "deregister"]
        assert client.of("fail")[0][1]["error"] == "Worker shutdown timeout"

        # The handler wakes up later: its result must not be acked for a job that
        # was already failed and deregistered.
        release.set()
        assert signal_seen.wait(5)
        time.sleep(0.2)
        assert client.names() == ["fail", "deregister"]
        runner.join(5)

    def test_start_returns_only_after_stop_finished(self) -> None:
        client = FakeClient([_job()])
        worker = _sync_worker(client)
        started, release = threading.Event(), threading.Event()

        @worker.process
        def handle(ctx: Any) -> None:
            started.set()
            release.wait(5)

        runner = _run_sync(worker)
        assert started.wait(5)
        stopper = threading.Thread(target=worker.stop)
        stopper.start()
        _wait_for(lambda: worker.state == "stopping")
        time.sleep(0.2)
        # start() must hold until the drain and deregister are over, so callers
        # that close the client right after start() cannot cut the acks off.
        assert runner.is_alive()
        release.set()
        runner.join(5)
        assert not runner.is_alive()
        assert worker.state == "stopped"
        stopper.join(5)

    def test_job_claimed_after_the_drain_window_is_failed(self) -> None:
        """A claim that lands after stop() closed intake is nacked, not dropped.

        Deregister leaves a live lease in processing. Failing the job reschedules
        it when retries remain (and dead-letters it when they do not).
        """
        client = FakeClient([])
        worker = _sync_worker(client)
        # stop() has already cleared the live id; the registered id still
        # owns the lease.
        worker._worker_id = None
        worker._registered_worker_id = "worker-1"
        worker._intake_closed = True
        claimed: list[Any] = []
        failed: list[Any] = []
        worker.on("job:claimed", claimed.append)
        worker.on("job:failed", failed.append)

        worker._process_job(_job(max_retries=0))

        assert worker._active_jobs == {}
        assert claimed == []
        assert client.names() == ["fail"]
        params = client.of("fail")[0][1]
        assert params["worker_id"] == "worker-1"
        assert params["lease_id"] == "lease-1"
        assert params["error"] == "Worker stopped before the job started"
        assert failed[0].will_retry is False

    def test_claim_in_flight_when_stop_starts_is_processed_before_deregister(self) -> None:
        """stop() waits for a claim already on the wire and runs that job."""
        gate = threading.Event()
        release = threading.Event()

        class GatedClient(FakeClient):
            def _claim(self, params: Any) -> Any:
                gate.set()
                assert release.wait(5)
                return super()._claim(params)

        client = GatedClient([_job(max_retries=0)])
        worker = _sync_worker(client, shutdown_timeout=2.0)
        ran = threading.Event()

        @worker.process
        def handle(ctx: Any) -> dict[str, Any]:
            ran.set()
            return {"ok": True}

        runner = _run_sync(worker)
        stopper: threading.Thread | None = None
        try:
            assert gate.wait(5)
            stopper = threading.Thread(target=worker.stop)
            stopper.start()
            _wait_for(lambda: worker.state == "stopping")
            time.sleep(0.1)
            # Still inside the claim: deregister must not run yet, or the job
            # would be left processing with a live lease.
            assert client.names() == []
            release.set()
            stopper.join(5)
            runner.join(5)
            assert not stopper.is_alive()
            assert not runner.is_alive()
        finally:
            release.set()
            if stopper is not None:
                stopper.join(5)
            runner.join(5)

        assert ran.is_set()
        assert client.names() == ["complete", "deregister"]
        assert worker.state == "stopped"

    def test_hung_claim_does_not_hold_stop_past_the_shutdown_timeout(self) -> None:
        """A claim that outlives the shutdown budget does not block stop()."""
        gate = threading.Event()
        release = threading.Event()

        class HungClient(FakeClient):
            def _claim(self, params: Any) -> Any:
                gate.set()
                release.wait(10)
                return super()._claim(params)

        client = HungClient([_job(max_retries=0)])
        worker = _sync_worker(client, shutdown_timeout=0.5)

        @worker.process
        def handle(ctx: Any) -> dict[str, Any]:
            return {"ok": True}

        runner = _run_sync(worker)
        try:
            assert gate.wait(5)
            started = time.monotonic()
            worker.stop()
            assert time.monotonic() - started < 3.0
            assert "deregister" in client.names()
        finally:
            release.set()
            runner.join(5)

    def test_failed_complete_ack_is_reported_as_an_error_event(self) -> None:
        client = FakeClient([])
        client.complete_error = RuntimeError("502 after retries")
        worker = _sync_worker(client)
        worker._worker_id = "worker-1"
        errors: list[Any] = []
        worker.on("error", errors.append)
        active = SyncActiveJob(job=_job(), started_at=0.0, abort_event=threading.Event())
        worker._active_jobs["job-1"] = active

        assert worker._complete_job(active, {"ok": True}) is False

        assert len(errors) == 1
        assert str(errors[0].error) == "502 after retries"

    def test_replayed_complete_that_answers_409_already_completed_is_success(self) -> None:
        from spooled.errors import ConflictError

        client = FakeClient([])
        client.complete_error = ConflictError("Job is already completed")
        worker = _sync_worker(client)
        worker._worker_id = "worker-1"
        done: list[Any] = []
        worker.on("job:completed", done.append)
        active = SyncActiveJob(job=_job(), started_at=0.0, abort_event=threading.Event())
        worker._active_jobs["job-1"] = active

        assert worker._complete_job(active, None) is True
        assert len(done) == 1

    @pytest.mark.parametrize(
        ("raised", "expected"),
        [("", "Job failed"), ("x" * 5000, "x" * 2048)],
    )
    def test_failure_text_is_coerced_before_calling_fail(self, raised: str, expected: str) -> None:
        client = FakeClient([_job()])
        worker = _sync_worker(client)

        @worker.process
        def handle(ctx: Any) -> None:
            raise RuntimeError(raised)

        runner = _run_sync(worker)
        _wait_for(lambda: client.names() == ["fail"])
        worker.stop()
        runner.join(5)

        assert client.of("fail")[0][1]["error"] == expected


class TestSyncJobTimeout:
    def test_hung_handler_is_failed_after_timeout_seconds_and_its_return_dropped(self) -> None:
        client = FakeClient([_job(timeout_seconds=1)])
        worker = _sync_worker(client, concurrency=1, lease_duration=5, heartbeat_fraction=0.1)
        started, release = threading.Event(), threading.Event()
        signalled = threading.Event()

        @worker.process
        def handle(ctx: Any) -> dict[str, Any]:
            started.set()
            release.wait(10)
            if ctx.signal.is_set():
                signalled.set()
            return {"late": True}

        runner = _run_sync(worker)
        assert started.wait(5)
        _wait_for(lambda: client.names() == ["fail"], timeout=5)

        assert client.of("fail")[0][1]["error"] == "Job timeout exceeded"
        # The lease is no longer extended for the hung handler.
        beats = len(client.of("job_heartbeat"))
        time.sleep(0.4)
        assert len(client.of("job_heartbeat")) == beats
        # The hung thread still occupies a concurrency slot until it returns.
        assert worker._abandoned_running == 1

        release.set()
        assert signalled.wait(5)
        _wait_for(lambda: worker._abandoned_running == 0)
        assert client.names() == ["fail"]  # the late return was not acked

        worker.stop()
        runner.join(5)

    def test_handler_finishing_before_the_timeout_is_completed_normally(self) -> None:
        client = FakeClient([_job(timeout_seconds=30)])
        worker = _sync_worker(client)

        @worker.process
        def handle(ctx: Any) -> dict[str, Any]:
            return {"fast": True}

        runner = _run_sync(worker)
        _wait_for(lambda: client.names() == ["complete"])
        worker.stop()
        runner.join(5)
        assert client.names() == ["complete", "deregister"]


# ─────────────────────────────────────────────────────────────────────────────
# Async worker
# ─────────────────────────────────────────────────────────────────────────────


def _async_worker(client: FakeClient, **kwargs: Any) -> AsyncSpooledWorker:
    options: dict[str, Any] = {
        "poll_interval": 0.05,
        "lease_duration": 5,
        "shutdown_timeout": 5.0,
    }
    options.update(kwargs)
    return AsyncSpooledWorker(client, "q", **options)  # type: ignore[arg-type]


class TestAsyncWorkerDrain:
    @pytest.mark.asyncio
    async def test_stop_lets_a_running_handler_finish_and_completes_it(self) -> None:
        client = FakeClient([_job()], is_async=True)
        worker = _async_worker(client)
        started, release = asyncio.Event(), asyncio.Event()
        seen_signal: list[bool] = []

        @worker.process
        async def handle(ctx: Any) -> dict[str, Any]:
            started.set()
            await release.wait()
            seen_signal.append(ctx.signal.is_set())
            return {"ok": True}

        runner = asyncio.create_task(worker.start())
        await asyncio.wait_for(started.wait(), 5)

        stopper = asyncio.create_task(worker.stop())
        await _await_for(lambda: worker.state == "stopping")
        await asyncio.sleep(0.2)
        assert client.names() == []

        release.set()
        await asyncio.wait_for(stopper, 5)
        await asyncio.wait_for(runner, 5)

        assert seen_signal == [False]
        assert client.names() == ["complete", "deregister"]
        assert client.of("complete")[0][1]["result"] == {"ok": True}
        assert worker.state == "stopped"

    @pytest.mark.asyncio
    async def test_stop_fails_a_handler_that_raised_during_the_drain(self) -> None:
        client = FakeClient([_job()], is_async=True)
        worker = _async_worker(client)
        started, release = asyncio.Event(), asyncio.Event()

        @worker.process
        async def handle(ctx: Any) -> None:
            started.set()
            await release.wait()
            raise RuntimeError("kaput")

        runner = asyncio.create_task(worker.start())
        await asyncio.wait_for(started.wait(), 5)
        stopper = asyncio.create_task(worker.stop())
        await _await_for(lambda: worker.state == "stopping")
        release.set()
        await asyncio.wait_for(stopper, 5)
        await asyncio.wait_for(runner, 5)

        assert client.names() == ["fail", "deregister"]
        assert client.of("fail")[0][1]["error"] == "kaput"

    @pytest.mark.asyncio
    async def test_handler_still_running_after_the_timeout_is_cancelled_and_failed(self) -> None:
        client = FakeClient([_job()], is_async=True)
        worker = _async_worker(client, shutdown_timeout=0.3)
        started = asyncio.Event()
        cancelled = asyncio.Event()

        @worker.process
        async def handle(ctx: Any) -> None:
            started.set()
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                cancelled.set()
                raise

        runner = asyncio.create_task(worker.start())
        await asyncio.wait_for(started.wait(), 5)
        began = time.monotonic()
        await asyncio.wait_for(worker.stop(), 5)
        assert time.monotonic() - began >= 0.3
        await asyncio.wait_for(runner, 5)

        assert cancelled.is_set()
        assert client.names() == ["fail", "deregister"]
        assert client.of("fail")[0][1]["error"] == "Worker shutdown timeout"
        assert worker._active_jobs == {}

    @pytest.mark.asyncio
    async def test_job_heartbeat_keeps_running_while_draining(self) -> None:
        client = FakeClient([_job()], is_async=True)
        worker = _async_worker(client, heartbeat_fraction=0.02)
        started, release = asyncio.Event(), asyncio.Event()

        @worker.process
        async def handle(ctx: Any) -> None:
            started.set()
            await release.wait()

        runner = asyncio.create_task(worker.start())
        await asyncio.wait_for(started.wait(), 5)
        stopper = asyncio.create_task(worker.stop())
        await _await_for(lambda: worker.state == "stopping")
        before = len(client.of("job_heartbeat"))
        await _await_for(lambda: len(client.of("job_heartbeat")) > before)
        release.set()
        await asyncio.wait_for(stopper, 5)
        await asyncio.wait_for(runner, 5)

    @pytest.mark.asyncio
    async def test_job_claimed_after_the_drain_window_is_failed(self) -> None:
        """A claim that lands after stop() closed intake is nacked, not dropped."""
        client = FakeClient([_job(max_retries=0)], is_async=True)
        worker = _async_worker(client)
        worker._state = "running"
        worker._worker_id = "worker-1"
        worker._registered_worker_id = "worker-1"

        async def claim(_params: Any) -> Any:
            worker._intake_closed = True
            return client._claim(_params)

        client.jobs.claim = claim
        failed: list[Any] = []
        worker.on("job:failed", failed.append)

        await worker._poll()

        assert worker._active_jobs == {}
        assert client.names() == ["fail"]
        params = client.of("fail")[0][1]
        assert params["worker_id"] == "worker-1"
        assert params["lease_id"] == "lease-1"
        assert params["error"] == "Worker stopped before the job started"
        assert failed[0].will_retry is False

    @pytest.mark.asyncio
    async def test_claim_in_flight_when_stop_starts_is_processed_before_deregister(self) -> None:
        """stop() waits for a claim already on the wire and runs that job."""
        client = FakeClient([_job(max_retries=0)], is_async=True)
        started_claim = asyncio.Event()
        release_claim = asyncio.Event()

        async def claim(_params: Any) -> Any:
            started_claim.set()
            await release_claim.wait()
            return client._claim(_params)

        client.jobs.claim = claim
        worker = _async_worker(client, shutdown_timeout=2.0)
        ran = asyncio.Event()

        @worker.process
        async def handle(ctx: Any) -> dict[str, Any]:
            ran.set()
            return {"ok": True}

        runner = asyncio.create_task(worker.start())
        try:
            await asyncio.wait_for(started_claim.wait(), 5)
            stopper = asyncio.create_task(worker.stop())
            await asyncio.sleep(0.05)
            assert client.names() == []
            release_claim.set()
            await asyncio.wait_for(stopper, 5)
            await asyncio.wait_for(runner, 5)
        finally:
            release_claim.set()

        assert ran.is_set()
        assert client.names() == ["complete", "deregister"]
        assert worker.state == "stopped"

    @pytest.mark.asyncio
    async def test_failed_complete_ack_is_reported_as_an_error_event(self) -> None:
        client = FakeClient([], is_async=True)
        client.complete_error = RuntimeError("502 after retries")
        worker = _async_worker(client)
        worker._worker_id = "worker-1"
        errors: list[Any] = []
        worker.on("error", errors.append)
        active = AsyncActiveJob(job=_job(), started_at=0.0, abort_event=asyncio.Event())
        worker._active_jobs["job-1"] = active

        assert await worker._complete_job(active, None) is False
        assert [str(e.error) for e in errors] == ["502 after retries"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("raised", "expected"),
        [("", "Job failed"), ("x" * 5000, "x" * 2048)],
    )
    async def test_failure_text_is_coerced_before_calling_fail(
        self, raised: str, expected: str
    ) -> None:
        client = FakeClient([_job()], is_async=True)
        worker = _async_worker(client)

        @worker.process
        async def handle(ctx: Any) -> None:
            raise RuntimeError(raised)

        runner = asyncio.create_task(worker.start())
        await _await_for(lambda: client.names() == ["fail"])
        await worker.stop()
        await asyncio.wait_for(runner, 5)

        assert client.of("fail")[0][1]["error"] == expected

    @pytest.mark.asyncio
    async def test_claimed_job_tasks_are_kept_referenced(self) -> None:
        client = FakeClient([_job()], is_async=True)
        worker = _async_worker(client)
        release = asyncio.Event()

        @worker.process
        async def handle(ctx: Any) -> None:
            await release.wait()

        runner = asyncio.create_task(worker.start())
        await _await_for(lambda: len(worker._job_tasks) == 1)
        release.set()
        await _await_for(lambda: not worker._job_tasks)
        await worker.stop()
        await asyncio.wait_for(runner, 5)


class TestAsyncJobTimeout:
    @pytest.mark.asyncio
    async def test_hung_handler_is_failed_after_timeout_seconds(self) -> None:
        client = FakeClient([_job(timeout_seconds=1)], is_async=True)
        worker = _async_worker(client, concurrency=1)
        cancelled = asyncio.Event()

        @worker.process
        async def handle(ctx: Any) -> None:
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                cancelled.set()
                raise

        runner = asyncio.create_task(worker.start())
        await _await_for(lambda: client.names() == ["fail"], timeout=5)

        assert client.of("fail")[0][1]["error"] == "Job timeout exceeded"
        # The handler is cancelled without being awaited, so give it a loop turn.
        await asyncio.wait_for(cancelled.wait(), 2)
        await _await_for(lambda: worker._active_jobs == {})

        await worker.stop()
        await asyncio.wait_for(runner, 5)
        assert client.names() == ["fail", "deregister"]

    @pytest.mark.asyncio
    async def test_a_handler_that_ignores_cancellation_cannot_hold_the_lease(self) -> None:
        client = FakeClient([_job(timeout_seconds=1)], is_async=True)
        worker = _async_worker(client, concurrency=1)
        release = asyncio.Event()

        @worker.process
        async def handle(ctx: Any) -> None:
            while not release.is_set():
                try:
                    await asyncio.sleep(0.05)
                except asyncio.CancelledError:
                    continue  # swallows every cancellation

        runner = asyncio.create_task(worker.start())
        await _await_for(lambda: client.names() == ["fail"], timeout=5)
        assert client.of("fail")[0][1]["error"] == "Job timeout exceeded"

        release.set()
        await worker.stop()
        await asyncio.wait_for(runner, 5)

    @pytest.mark.asyncio
    async def test_an_asyncio_timeout_raised_by_the_handler_is_a_plain_failure(self) -> None:
        client = FakeClient([_job(timeout_seconds=30)], is_async=True)
        worker = _async_worker(client)

        @worker.process
        async def handle(ctx: Any) -> None:
            raise asyncio.TimeoutError("upstream timed out")

        runner = asyncio.create_task(worker.start())
        await _await_for(lambda: client.names() == ["fail"])
        await worker.stop()
        await asyncio.wait_for(runner, 5)

        assert client.of("fail")[0][1]["error"] == "upstream timed out"
