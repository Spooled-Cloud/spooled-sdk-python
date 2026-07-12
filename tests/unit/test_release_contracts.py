"""Release metadata and lease-fencing regression tests."""

import asyncio
import re
import runpy
import threading
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from spooled import __version__
from spooled.config import DEFAULT_USER_AGENT, SpooledClientConfig
from spooled.grpc import GrpcRegisterWorkerRequest
from spooled.types.jobs import ClaimedJob
from spooled.worker import AsyncSpooledWorker, SpooledWorker
from spooled.worker.async_worker import ActiveJob as AsyncActiveJob
from spooled.worker.types import SpooledWorkerOptions
from spooled.worker.worker import ActiveJob as SyncActiveJob


def _project_version() -> str:
    pyproject = (Path(__file__).parents[2] / "pyproject.toml").read_text()
    project = pyproject.split("[project]", 1)[1].split("\n[", 1)[0]
    match = re.search(r'^version = "([^"]+)"$', project, re.MULTILINE)
    assert match is not None
    return match.group(1)


def test_source_checkout_version_fallback() -> None:
    """A checkout without installed metadata still reports the project version."""
    version_module = Path(__file__).parents[2] / "src" / "spooled" / "_version.py"
    with patch("importlib.metadata.version", side_effect=PackageNotFoundError):
        namespace = runpy.run_path(str(version_module))

    assert namespace["__version__"] == _project_version()


def test_runtime_metadata_uses_project_version() -> None:
    """Every default that identifies this SDK derives from the project version."""
    expected_version = _project_version()
    client = MagicMock()
    client.get_config.return_value = MagicMock(debug_fn=None)

    assert __version__ == expected_version
    expected_user_agent = f"spooled-python/{expected_version}"
    assert expected_user_agent == DEFAULT_USER_AGENT
    assert expected_user_agent == SpooledClientConfig().user_agent
    assert SpooledWorkerOptions(queue_name="test").version == expected_version
    assert SpooledWorker(client, "test")._options.version == expected_version
    assert AsyncSpooledWorker(client, "test")._options.version == expected_version
    assert GrpcRegisterWorkerRequest(queue_name="test", hostname="host").version == expected_version


@pytest.mark.asyncio
async def test_async_heartbeat_serializes_lease_id() -> None:
    """Async heartbeats echo the immutable lease fencing token from the claim."""
    client = MagicMock()
    client.get_config.return_value = MagicMock(debug_fn=None)
    worker = AsyncSpooledWorker(client, queue_name="test")
    worker._worker_id = "worker-1"

    async def stop_after_heartbeat(*_args: object, **_kwargs: object) -> None:
        worker._worker_id = None

    client.jobs.heartbeat = AsyncMock(side_effect=stop_after_heartbeat)
    job = ClaimedJob(
        id="job-1",
        queue_name="test",
        payload={},
        retry_count=0,
        max_retries=3,
        timeout_seconds=300,
        lease_id="lease-abc",
    )
    active = AsyncActiveJob(
        job=job,
        started_at=0.0,
        abort_event=asyncio.Event(),
    )
    worker._active_jobs[job.id] = active

    with patch("spooled.worker.async_worker.asyncio.sleep", new=AsyncMock()):
        await worker._job_heartbeat_loop(active, 1.0)

    client.jobs.heartbeat.assert_awaited_once_with(
        "job-1",
        {
            "worker_id": "worker-1",
            "lease_duration_secs": worker._options.lease_duration,
            "lease_id": "lease-abc",
        },
    )


def test_sync_stale_execution_cannot_touch_replacement() -> None:
    """Lease A cannot heartbeat, settle, or clean up replacement lease B."""
    client = MagicMock()
    client.get_config.return_value = MagicMock(debug_fn=None)
    worker = SpooledWorker(client, queue_name="test")
    worker._worker_id = "worker-1"

    old = SyncActiveJob(
        job=_claimed_job("lease-a"), started_at=0.0, abort_event=__import__("threading").Event()
    )
    replacement = SyncActiveJob(
        job=_claimed_job("lease-b"), started_at=1.0, abort_event=__import__("threading").Event()
    )
    replacement.heartbeat_timer = MagicMock()
    worker._active_jobs[old.job.id] = old

    with patch("spooled.worker.worker.threading.Timer") as timer_factory:
        old_timer = MagicMock()
        new_timer = MagicMock()
        timer_factory.side_effect = [old_timer, new_timer, MagicMock()]
        worker._schedule_job_heartbeat(old, 60.0)
        old_callback = timer_factory.call_args_list[0].args[1]

        worker._active_jobs[old.job.id] = replacement
        old_callback()
        worker._complete_job(old, {"lease": "a"})
        worker._fail_job(old, "stale")
        worker._cleanup_job(old)

        assert worker._active_jobs[old.job.id] is replacement
        replacement.heartbeat_timer.cancel.assert_not_called()
        client.jobs.heartbeat.assert_not_called()
        client.jobs.complete.assert_not_called()
        client.jobs.fail.assert_not_called()

        worker._schedule_job_heartbeat(replacement, 60.0)
        new_callback = timer_factory.call_args_list[1].args[1]
        new_callback()
        worker._complete_job(replacement, {"lease": "b"})
        worker._fail_job(replacement, "current")

    client.jobs.heartbeat.assert_called_once_with(
        "job-1",
        {
            "worker_id": "worker-1",
            "lease_duration_secs": worker._options.lease_duration,
            "lease_id": "lease-b",
        },
    )
    client.jobs.complete.assert_called_once_with(
        "job-1",
        {
            "worker_id": "worker-1",
            "result": {"lease": "b"},
            "lease_id": "lease-b",
        },
    )
    client.jobs.fail.assert_called_once_with(
        "job-1",
        {
            "worker_id": "worker-1",
            "error": "current",
            "lease_id": "lease-b",
        },
    )


def test_sync_slow_heartbeat_does_not_hold_active_jobs_lock() -> None:
    """A blocked heartbeat allows replacement and stays bound to its original lease."""
    client = MagicMock()
    client.get_config.return_value = MagicMock(debug_fn=None)
    worker = SpooledWorker(client, queue_name="test")
    worker._worker_id = "worker-1"
    old = SyncActiveJob(job=_claimed_job("lease-a"), started_at=0.0, abort_event=threading.Event())
    replacement = SyncActiveJob(
        job=_claimed_job("lease-b"), started_at=1.0, abort_event=threading.Event()
    )
    worker._active_jobs[old.job.id] = old
    request_started = threading.Event()
    release_request = threading.Event()

    def slow_heartbeat(*_args: object, **_kwargs: object) -> None:
        request_started.set()
        assert release_request.wait(timeout=2.0)

    client.jobs.heartbeat.side_effect = slow_heartbeat
    with patch("spooled.worker.worker.threading.Timer") as timer_factory:
        worker._schedule_job_heartbeat(old, 60.0)
        callback = timer_factory.call_args.args[1]
        callback_thread = threading.Thread(target=callback)
        callback_thread.start()
        assert request_started.wait(timeout=2.0)

        assert worker._lock.acquire(timeout=0.5)
        try:
            worker._active_jobs[old.job.id] = replacement
        finally:
            worker._lock.release()

        release_request.set()
        callback_thread.join(timeout=2.0)
        assert not callback_thread.is_alive()

    client.jobs.heartbeat.assert_called_once_with(
        "job-1",
        {
            "worker_id": "worker-1",
            "lease_duration_secs": worker._options.lease_duration,
            "lease_id": "lease-a",
        },
    )
    assert worker._active_jobs[old.job.id] is replacement


@pytest.mark.asyncio
async def test_async_slow_heartbeat_does_not_hold_active_jobs_lock() -> None:
    """Awaited heartbeat I/O allows replacement without borrowing its lease."""
    client = MagicMock()
    client.get_config.return_value = MagicMock(debug_fn=None)
    worker = AsyncSpooledWorker(client, queue_name="test")
    worker._worker_id = "worker-1"
    old = AsyncActiveJob(job=_claimed_job("lease-a"), started_at=0.0, abort_event=asyncio.Event())
    replacement = AsyncActiveJob(
        job=_claimed_job("lease-b"), started_at=1.0, abort_event=asyncio.Event()
    )
    worker._active_jobs[old.job.id] = old
    request_started = asyncio.Event()
    release_request = asyncio.Event()

    async def slow_heartbeat(*_args: object, **_kwargs: object) -> None:
        request_started.set()
        await release_request.wait()

    client.jobs.heartbeat = AsyncMock(side_effect=slow_heartbeat)
    with patch("spooled.worker.async_worker.asyncio.sleep", new=AsyncMock()):
        heartbeat_task = asyncio.create_task(worker._job_heartbeat_loop(old, 1.0))
        await asyncio.wait_for(request_started.wait(), timeout=2.0)

        async def install_replacement() -> None:
            async with worker._active_jobs_lock:
                worker._active_jobs[old.job.id] = replacement

        await asyncio.wait_for(install_replacement(), timeout=0.5)
        release_request.set()
        await asyncio.wait_for(heartbeat_task, timeout=2.0)

    client.jobs.heartbeat.assert_awaited_once_with(
        "job-1",
        {
            "worker_id": "worker-1",
            "lease_duration_secs": worker._options.lease_duration,
            "lease_id": "lease-a",
        },
    )
    assert worker._active_jobs[old.job.id] is replacement


@pytest.mark.asyncio
async def test_async_stale_execution_cannot_touch_replacement() -> None:
    """Async lease A cannot heartbeat, settle, or clean up replacement lease B."""
    client = MagicMock()
    client.get_config.return_value = MagicMock(debug_fn=None)
    client.jobs.heartbeat = AsyncMock()
    client.jobs.complete = AsyncMock()
    client.jobs.fail = AsyncMock()
    worker = AsyncSpooledWorker(client, queue_name="test")
    worker._worker_id = "worker-1"

    old = AsyncActiveJob(job=_claimed_job("lease-a"), started_at=0.0, abort_event=asyncio.Event())
    replacement = AsyncActiveJob(
        job=_claimed_job("lease-b"), started_at=1.0, abort_event=asyncio.Event()
    )
    replacement.heartbeat_task = MagicMock()
    worker._active_jobs[old.job.id] = replacement

    with patch("spooled.worker.async_worker.asyncio.sleep", new=AsyncMock()):
        await worker._job_heartbeat_loop(old, 1.0)
    await worker._complete_job(old, {"lease": "a"})
    await worker._fail_job(old, "stale")
    await worker._cleanup_job(old)

    assert worker._active_jobs[old.job.id] is replacement
    replacement.heartbeat_task.cancel.assert_not_called()
    client.jobs.heartbeat.assert_not_awaited()
    client.jobs.complete.assert_not_awaited()
    client.jobs.fail.assert_not_awaited()

    async def stop_after_heartbeat(*_args: object, **_kwargs: object) -> None:
        worker._worker_id = None

    client.jobs.heartbeat.side_effect = stop_after_heartbeat
    with patch("spooled.worker.async_worker.asyncio.sleep", new=AsyncMock()):
        await worker._job_heartbeat_loop(replacement, 1.0)
    worker._worker_id = "worker-1"
    await worker._complete_job(replacement, {"lease": "b"})
    await worker._fail_job(replacement, "current")

    client.jobs.heartbeat.assert_awaited_once_with(
        "job-1",
        {
            "worker_id": "worker-1",
            "lease_duration_secs": worker._options.lease_duration,
            "lease_id": "lease-b",
        },
    )
    client.jobs.complete.assert_awaited_once_with(
        "job-1",
        {
            "worker_id": "worker-1",
            "result": {"lease": "b"},
            "lease_id": "lease-b",
        },
    )
    client.jobs.fail.assert_awaited_once_with(
        "job-1",
        {
            "worker_id": "worker-1",
            "error": "current",
            "lease_id": "lease-b",
        },
    )


def _claimed_job(lease_id: str) -> ClaimedJob:
    return ClaimedJob(
        id="job-1",
        queue_name="test",
        payload={},
        retry_count=0,
        max_retries=3,
        timeout_seconds=300,
        lease_id=lease_id,
    )


def test_generated_stubs_import() -> None:
    """All generated protobuf and gRPC modules import in the normal test suite."""
    from spooled.grpc.stubs import spooled_pb2, spooled_pb2_grpc

    assert spooled_pb2.DESCRIPTOR.name == "spooled.proto"
    assert spooled_pb2_grpc.GRPC_GENERATED_VERSION == "1.80.0"
