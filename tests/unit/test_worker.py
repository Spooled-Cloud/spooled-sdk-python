"""Unit tests for worker module."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest

from spooled.worker.types import (
    AsyncJobContext,
    JobContext,
    SpooledWorkerOptions,
    WorkerState,
)


class TestJobContext:
    """Tests for JobContext."""

    def test_context_creation(self) -> None:
        """Test creating a job context."""
        signal = threading.Event()
        ctx = JobContext(
            job_id="job_123",
            queue_name="test",
            payload={"key": "value"},
            retry_count=0,
            max_retries=3,
            signal=signal,
        )
        assert ctx.job_id == "job_123"
        assert ctx.queue_name == "test"
        assert ctx.payload == {"key": "value"}
        assert ctx.retry_count == 0
        assert ctx.max_retries == 3

    def test_signal_not_set_initially(self) -> None:
        """Test signal is not set initially."""
        signal = threading.Event()
        ctx = JobContext(
            job_id="job_123",
            queue_name="test",
            payload={},
            retry_count=0,
            max_retries=3,
            signal=signal,
        )
        assert ctx.signal.is_set() is False

    def test_signal_can_be_set(self) -> None:
        """Test signal can be set for abort."""
        signal = threading.Event()
        ctx = JobContext(
            job_id="job_123",
            queue_name="test",
            payload={},
            retry_count=0,
            max_retries=3,
            signal=signal,
        )
        signal.set()
        assert ctx.signal.is_set() is True

    def test_log_method(self) -> None:
        """Test log method."""
        signal = threading.Event()
        ctx = JobContext(
            job_id="job_123",
            queue_name="test",
            payload={},
            retry_count=0,
            max_retries=3,
            signal=signal,
        )
        # Should not raise
        ctx.log("info", "Test message")
        ctx.log("debug", "Debug message", {"key": "value"})
        ctx.log("warn", "Warning message")
        ctx.log("error", "Error message")

    def test_progress_method(self) -> None:
        """Test progress method."""
        signal = threading.Event()
        ctx = JobContext(
            job_id="job_123",
            queue_name="test",
            payload={},
            retry_count=0,
            max_retries=3,
            signal=signal,
        )
        # Should not raise
        ctx.progress(50)
        ctx.progress(75, "Three quarters done")


class TestSpooledWorkerOptions:
    """Tests for SpooledWorkerOptions."""

    def test_minimal_options(self) -> None:
        """Test minimal required options."""
        options = SpooledWorkerOptions(queue_name="test")
        assert options.queue_name == "test"
        assert options.concurrency == 5
        assert options.poll_interval == 1.0
        assert options.lease_duration == 30

    def test_all_options(self) -> None:
        """Test all options."""
        options = SpooledWorkerOptions(
            queue_name="emails",
            concurrency=10,
            poll_interval=2.0,
            lease_duration=60,
            heartbeat_fraction=0.3,
            shutdown_timeout=60.0,
            hostname="worker-1.local",
            worker_type="email-processor",
            version="2.0.0",
            metadata={"env": "prod"},
            auto_start=True,
        )
        assert options.concurrency == 10
        assert options.heartbeat_fraction == 0.3
        assert options.auto_start is True

    def test_queue_name_validation(self) -> None:
        """Test queue_name validation."""
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            SpooledWorkerOptions(queue_name="")

        with pytest.raises(PydanticValidationError):
            SpooledWorkerOptions(queue_name="x" * 101)

    def test_concurrency_bounds(self) -> None:
        """Test concurrency validation."""
        from pydantic import ValidationError as PydanticValidationError

        SpooledWorkerOptions(queue_name="q", concurrency=1)
        SpooledWorkerOptions(queue_name="q", concurrency=100)

        with pytest.raises(PydanticValidationError):
            SpooledWorkerOptions(queue_name="q", concurrency=0)

        with pytest.raises(PydanticValidationError):
            SpooledWorkerOptions(queue_name="q", concurrency=101)

    def test_poll_interval_validation(self) -> None:
        """Test poll_interval must be positive."""
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError):
            SpooledWorkerOptions(queue_name="q", poll_interval=0)

        with pytest.raises(PydanticValidationError):
            SpooledWorkerOptions(queue_name="q", poll_interval=-1)

    def test_lease_duration_bounds(self) -> None:
        """Test lease_duration validation."""
        from pydantic import ValidationError as PydanticValidationError

        SpooledWorkerOptions(queue_name="q", lease_duration=5)
        SpooledWorkerOptions(queue_name="q", lease_duration=3600)

        with pytest.raises(PydanticValidationError):
            SpooledWorkerOptions(queue_name="q", lease_duration=4)

        with pytest.raises(PydanticValidationError):
            SpooledWorkerOptions(queue_name="q", lease_duration=3601)

    def test_heartbeat_fraction_bounds(self) -> None:
        """Test heartbeat_fraction validation."""
        from pydantic import ValidationError as PydanticValidationError

        SpooledWorkerOptions(queue_name="q", heartbeat_fraction=0.1)
        SpooledWorkerOptions(queue_name="q", heartbeat_fraction=1.0)

        with pytest.raises(PydanticValidationError):
            SpooledWorkerOptions(queue_name="q", heartbeat_fraction=0)

        with pytest.raises(PydanticValidationError):
            SpooledWorkerOptions(queue_name="q", heartbeat_fraction=1.1)


class TestWorkerState:
    """Tests for WorkerState type."""

    def test_valid_states(self) -> None:
        """Test all valid worker states."""
        valid_states: list[WorkerState] = [
            "idle",
            "starting",
            "running",
            "stopping",
            "stopped",
            "error",
        ]
        for state in valid_states:
            # Should be valid literals
            assert state in ["idle", "starting", "running", "stopping", "stopped", "error"]


class TestSpooledWorkerMocked:
    """Tests for SpooledWorker with mocked client."""

    def test_worker_creation(self) -> None:
        """Test worker creation."""
        from spooled.worker import SpooledWorker

        mock_client = MagicMock()
        mock_client.get_config.return_value = MagicMock(debug_fn=None)

        worker = SpooledWorker(
            mock_client,
            queue_name="test",
            concurrency=5,
        )
        assert worker.state == "idle"
        assert worker.worker_id is None
        assert worker.active_job_count == 0

    def test_process_decorator(self) -> None:
        """Test process decorator registers handler."""
        from spooled.worker import SpooledWorker

        mock_client = MagicMock()
        mock_client.get_config.return_value = MagicMock(debug_fn=None)

        worker = SpooledWorker(mock_client, queue_name="test")

        @worker.process
        def handle_job(ctx):
            return {"processed": True}

        # Handler should be registered
        assert worker._handler is not None

    def test_cannot_set_handler_after_start(self) -> None:
        """Test cannot set handler after worker starts."""
        from spooled.worker import SpooledWorker

        mock_client = MagicMock()
        mock_client.get_config.return_value = MagicMock(debug_fn=None)

        worker = SpooledWorker(mock_client, queue_name="test")
        worker._state = "running"  # Simulate running state

        with pytest.raises(RuntimeError, match="Cannot set handler"):
            @worker.process
            def handle_job(ctx):
                pass

    def test_on_event_decorator(self) -> None:
        """Test on event decorator registers handler."""
        from spooled.worker import SpooledWorker

        mock_client = MagicMock()
        mock_client.get_config.return_value = MagicMock(debug_fn=None)

        worker = SpooledWorker(mock_client, queue_name="test")

        calls = []

        @worker.on("job:completed")
        def on_completed(event):
            calls.append(event)

        # Handler should be registered
        assert "job:completed" in worker._event_handlers
        assert len(worker._event_handlers["job:completed"]) == 1

    def test_start_requires_handler(self) -> None:
        """Test start requires handler to be set."""
        from spooled.worker import SpooledWorker

        mock_client = MagicMock()
        mock_client.get_config.return_value = MagicMock(debug_fn=None)

        worker = SpooledWorker(mock_client, queue_name="test")

        with pytest.raises(RuntimeError, match="No job handler registered"):
            worker.start()

    def test_cannot_start_twice(self) -> None:
        """Test cannot start worker twice."""
        from spooled.worker import SpooledWorker

        mock_client = MagicMock()
        mock_client.get_config.return_value = MagicMock(debug_fn=None)

        worker = SpooledWorker(mock_client, queue_name="test")

        @worker.process
        def handle(ctx):
            pass

        # Manually set state to running after setting handler
        worker._state = "running"

        with pytest.raises(RuntimeError, match="Cannot start worker"):
            worker.start()


class TestWorkerEventEmission:
    """Tests for worker event emission."""

    def test_emit_calls_handlers(self) -> None:
        """Test emit calls registered handlers."""
        from spooled.worker import SpooledWorker
        from spooled.worker.types import JobCompletedEventData

        mock_client = MagicMock()
        mock_client.get_config.return_value = MagicMock(debug_fn=None)

        worker = SpooledWorker(mock_client, queue_name="test")

        events_received = []

        @worker.on("job:completed")
        def handler(event):
            events_received.append(event)

        # Emit event
        event_data = JobCompletedEventData(
            job_id="job_123",
            queue_name="test",
            result={"success": True},
        )
        worker._emit("job:completed", event_data)

        assert len(events_received) == 1
        assert events_received[0].job_id == "job_123"

    def test_emit_handles_handler_errors(self) -> None:
        """Test emit handles errors in handlers."""
        from spooled.worker import SpooledWorker
        from spooled.worker.types import StartedEventData

        mock_client = MagicMock()
        mock_client.get_config.return_value = MagicMock(debug_fn=None)

        worker = SpooledWorker(mock_client, queue_name="test")

        @worker.on("started")
        def bad_handler(event):
            raise ValueError("Handler error")

        @worker.on("started")
        def good_handler(event):
            pass  # Should still be called

        # Should not raise
        event_data = StartedEventData(worker_id="w_1", queue_name="test")
        worker._emit("started", event_data)


class TestAsyncJobContext:
    """Tests for AsyncJobContext."""

    @pytest.mark.asyncio
    async def test_async_context_creation(self) -> None:
        """Test creating an async job context."""
        import asyncio

        signal = asyncio.Event()
        ctx = AsyncJobContext(
            job_id="job_123",
            queue_name="test",
            payload={"key": "value"},
            retry_count=0,
            max_retries=3,
            signal=signal,
        )
        assert ctx.job_id == "job_123"

    @pytest.mark.asyncio
    async def test_async_log_method(self) -> None:
        """Test async log method."""
        import asyncio

        signal = asyncio.Event()
        ctx = AsyncJobContext(
            job_id="job_123",
            queue_name="test",
            payload={},
            retry_count=0,
            max_retries=3,
            signal=signal,
        )
        # Should not raise
        await ctx.log("info", "Test message")
        await ctx.log("debug", "Debug", {"key": "value"})
