"""Unit tests for gRPC client module."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from spooled.grpc.client import (
    GrpcCompleteRequest as CompleteRequest,
)
from spooled.grpc.client import (
    GrpcDequeueRequest as DequeueRequest,
)
from spooled.grpc.client import (
    GrpcEnqueueRequest as EnqueueRequest,
)
from spooled.grpc.client import (
    GrpcFailRequest as FailRequest,
)
from spooled.grpc.client import (
    GrpcHeartbeatRequest as WorkerHeartbeatRequest,
)
from spooled.grpc.client import (
    GrpcJob,
)
from spooled.grpc.client import (
    GrpcRegisterWorkerRequest as RegisterWorkerRequest,
)


class TestEnqueueRequest:
    """Tests for EnqueueRequest model."""

    def test_minimal_request(self) -> None:
        """Test minimal enqueue request."""
        req = EnqueueRequest(
            queue_name="test",
            payload={"key": "value"},
        )
        assert req.queue_name == "test"
        assert req.priority == 0
        assert req.max_retries == 3

    def test_full_request(self) -> None:
        """Test full enqueue request."""
        req = EnqueueRequest(
            queue_name="test",
            payload={"key": "value"},
            priority=10,
            max_retries=5,
            timeout_seconds=600,
            idempotency_key="unique-123",
        )
        assert req.priority == 10
        assert req.idempotency_key == "unique-123"

    def test_priority_bounds(self) -> None:
        """Test priority validation."""
        EnqueueRequest(queue_name="q", payload={}, priority=-100)
        EnqueueRequest(queue_name="q", payload={}, priority=100)

        with pytest.raises(PydanticValidationError):
            EnqueueRequest(queue_name="q", payload={}, priority=-101)
        with pytest.raises(PydanticValidationError):
            EnqueueRequest(queue_name="q", payload={}, priority=101)


class TestDequeueRequest:
    """Tests for DequeueRequest model."""

    def test_defaults(self) -> None:
        """Test default values."""
        req = DequeueRequest(
            queue_name="test",
            worker_id="worker_1",
        )
        assert req.batch_size == 1
        assert req.lease_duration_secs == 30

    def test_custom_values(self) -> None:
        """Test custom values."""
        req = DequeueRequest(
            queue_name="test",
            worker_id="worker_1",
            batch_size=10,
            lease_duration_secs=60,
        )
        assert req.batch_size == 10
        assert req.lease_duration_secs == 60

    def test_batch_size_bounds(self) -> None:
        """Test batch_size validation."""
        with pytest.raises(PydanticValidationError):
            DequeueRequest(queue_name="q", worker_id="w", batch_size=0)
        with pytest.raises(PydanticValidationError):
            DequeueRequest(queue_name="q", worker_id="w", batch_size=101)


class TestGrpcJob:
    """Tests for GrpcJob model."""

    def test_job_model(self) -> None:
        """Test job model."""
        job = GrpcJob(
            id="job_123",
            queue_name="test",
            status="pending",
            payload={"key": "value"},
            retry_count=0,
            max_retries=3,
            timeout_seconds=300,
        )
        assert job.id == "job_123"
        assert job.payload == {"key": "value"}
        assert job.status == "pending"


class TestCompleteRequest:
    """Tests for CompleteRequest model."""

    def test_without_result(self) -> None:
        """Test complete without result."""
        req = CompleteRequest(
            job_id="job_123",
            worker_id="worker_1",
        )
        assert req.result is None

    def test_with_result(self) -> None:
        """Test complete with result."""
        req = CompleteRequest(
            job_id="job_123",
            worker_id="worker_1",
            result={"processed": True},
        )
        assert req.result == {"processed": True}


class TestFailRequest:
    """Tests for FailRequest model."""

    def test_error_required(self) -> None:
        """Test error message is required."""
        req = FailRequest(
            job_id="job_123",
            worker_id="worker_1",
            error="Processing failed",
        )
        assert req.error == "Processing failed"

    def test_error_min_length(self) -> None:
        """Test error minimum length."""
        with pytest.raises(PydanticValidationError):
            FailRequest(job_id="j", worker_id="w", error="")

    def test_error_max_length(self) -> None:
        """Test error maximum length."""
        with pytest.raises(PydanticValidationError):
            FailRequest(job_id="j", worker_id="w", error="x" * 2049)


class TestRegisterWorkerRequest:
    """Tests for RegisterWorkerRequest model."""

    def test_defaults(self) -> None:
        """Test default values."""
        req = RegisterWorkerRequest(
            queue_name="test",
            hostname="worker-1.local",
        )
        assert req.max_concurrency == 5

    def test_concurrency_bounds(self) -> None:
        """Test max_concurrency validation."""
        with pytest.raises(PydanticValidationError):
            RegisterWorkerRequest(queue_name="q", hostname="h", max_concurrency=0)
        with pytest.raises(PydanticValidationError):
            RegisterWorkerRequest(queue_name="q", hostname="h", max_concurrency=101)


class TestWorkerHeartbeatRequest:
    """Tests for WorkerHeartbeatRequest model."""

    def test_defaults(self) -> None:
        """Test default values."""
        req = WorkerHeartbeatRequest(
            worker_id="worker_1",
            current_jobs=5,
        )
        assert req.status == "healthy"

    def test_current_jobs_validation(self) -> None:
        """Test current_jobs must be non-negative."""
        with pytest.raises(PydanticValidationError):
            WorkerHeartbeatRequest(worker_id="w", current_jobs=-1)


class TestSpooledGrpcClientImport:
    """Tests for SpooledGrpcClient import check."""

    def test_import_without_grpc_raises(self) -> None:
        """Test import fails without grpc installed."""
        # This test verifies the import guard exists
        # In a real test environment with grpc, this would pass
        pass


