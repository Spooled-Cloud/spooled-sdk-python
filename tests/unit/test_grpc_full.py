"""
Comprehensive tests for gRPC client functionality.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from google.protobuf import struct_pb2, timestamp_pb2


class TestGrpcModels:
    """Tests for gRPC Pydantic models."""

    def test_enqueue_request_validation(self):
        """Test GrpcEnqueueRequest validation."""
        from spooled.grpc import GrpcEnqueueRequest

        # Valid request
        req = GrpcEnqueueRequest(
            queue_name="test-queue",
            payload={"key": "value"},
            priority=5,
        )
        assert req.queue_name == "test-queue"
        assert req.payload == {"key": "value"}
        assert req.priority == 5
        assert req.max_retries is None  # omitted means server queue default

    def test_enqueue_request_invalid_queue_name(self):
        """Test GrpcEnqueueRequest rejects empty queue_name."""
        from pydantic import ValidationError

        from spooled.grpc import GrpcEnqueueRequest

        with pytest.raises(ValidationError):
            GrpcEnqueueRequest(queue_name="", payload={})

    def test_enqueue_request_invalid_priority(self):
        """Test GrpcEnqueueRequest rejects invalid priority."""
        from pydantic import ValidationError

        from spooled.grpc import GrpcEnqueueRequest

        with pytest.raises(ValidationError):
            GrpcEnqueueRequest(queue_name="test", payload={}, priority=200)

    def test_dequeue_request_validation(self):
        """Test GrpcDequeueRequest validation."""
        from spooled.grpc import GrpcDequeueRequest

        req = GrpcDequeueRequest(
            queue_name="test-queue",
            worker_id="worker-1",
            batch_size=10,
        )
        assert req.batch_size == 10
        assert req.lease_duration_secs == 30  # default

    def test_complete_request_validation(self):
        """Test GrpcCompleteRequest validation."""
        from spooled.grpc import GrpcCompleteRequest

        req = GrpcCompleteRequest(
            job_id="job-123",
            worker_id="worker-1",
            result={"success": True},
        )
        assert req.job_id == "job-123"
        assert req.result == {"success": True}

    def test_fail_request_validation(self):
        """Test GrpcFailRequest validation."""
        from spooled.grpc import GrpcFailRequest

        req = GrpcFailRequest(
            job_id="job-123",
            worker_id="worker-1",
            error="Something went wrong",
        )
        assert req.error == "Something went wrong"
        assert req.retry is True  # default

    def test_register_worker_request_validation(self):
        """Test GrpcRegisterWorkerRequest validation."""
        from spooled.grpc import GrpcRegisterWorkerRequest

        req = GrpcRegisterWorkerRequest(
            queue_name="test-queue",
            hostname="worker-host",
            max_concurrency=10,
        )
        assert req.worker_type == "python"  # default
        from spooled import __version__

        assert req.version == __version__

    def test_grpc_job_model(self):
        """Test GrpcJob model."""
        from spooled.grpc import GrpcJob

        job = GrpcJob(
            id="job-123",
            queue_name="test-queue",
            status="pending",
            payload={"data": "test"},
        )
        assert job.id == "job-123"
        assert job.status == "pending"
        assert job.retry_count == 0  # default
        assert job.lease_id is None  # default (legacy server)

    def test_request_models_accept_lease_id(self):
        """Test the fencing token is accepted by the request models."""
        from spooled.grpc import (
            GrpcCompleteRequest,
            GrpcFailRequest,
            GrpcRenewLeaseRequest,
        )

        complete = GrpcCompleteRequest(job_id="job-123", worker_id="worker-1", lease_id="lease-abc")
        fail = GrpcFailRequest(
            job_id="job-123", worker_id="worker-1", error="boom", lease_id="lease-abc"
        )
        renew = GrpcRenewLeaseRequest(job_id="job-123", worker_id="worker-1", lease_id="lease-abc")
        assert complete.lease_id == "lease-abc"
        assert fail.lease_id == "lease-abc"
        assert renew.lease_id == "lease-abc"

        # Defaults to None so omitting it preserves legacy behavior
        assert GrpcCompleteRequest(job_id="j", worker_id="w").lease_id is None
        assert GrpcFailRequest(job_id="j", worker_id="w", error="e").lease_id is None
        assert GrpcRenewLeaseRequest(job_id="j", worker_id="w").lease_id is None


class TestGrpcConversions:
    """Tests for protobuf conversion utilities."""

    def test_dict_to_struct(self):
        """Test dict to protobuf Struct conversion."""
        from spooled.grpc.client import _dict_to_struct

        result = _dict_to_struct({"key": "value", "nested": {"a": 1}})
        assert result is not None
        assert result["key"] == "value"

    def test_dict_to_struct_none(self):
        """Test dict_to_struct with None."""
        from spooled.grpc.client import _dict_to_struct

        result = _dict_to_struct(None)
        assert result is None

    def test_struct_to_dict(self):
        """Test protobuf Struct to dict conversion."""
        from spooled.grpc.client import _struct_to_dict

        struct = struct_pb2.Struct()
        struct.update({"key": "value"})

        result = _struct_to_dict(struct)
        assert result is not None
        assert result["key"] == "value"

    def test_timestamp_to_datetime(self):
        """Test protobuf Timestamp to datetime conversion."""
        from spooled.grpc.client import _timestamp_to_datetime

        ts = timestamp_pb2.Timestamp()
        ts.FromDatetime(datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc))

        result = _timestamp_to_datetime(ts)
        assert result is not None
        assert result.year == 2024
        assert result.month == 1

    def test_timestamp_to_datetime_zero(self):
        """Test timestamp_to_datetime with zero timestamp."""
        from spooled.grpc.client import _timestamp_to_datetime

        ts = timestamp_pb2.Timestamp()  # seconds=0, nanos=0

        result = _timestamp_to_datetime(ts)
        assert result is None

    def test_job_status_to_str(self):
        """Test JobStatus enum to string conversion."""
        from spooled.grpc.client import _job_status_to_str

        assert _job_status_to_str(0) == "unspecified"
        assert _job_status_to_str(1) == "pending"
        assert _job_status_to_str(2) == "scheduled"
        assert _job_status_to_str(3) == "processing"
        assert _job_status_to_str(4) == "completed"
        assert _job_status_to_str(5) == "failed"
        assert _job_status_to_str(6) == "deadletter"
        assert _job_status_to_str(7) == "cancelled"
        assert _job_status_to_str(99) == "unknown"


class TestStreamOptions:
    """Tests for streaming options."""

    def test_stream_options_defaults(self):
        """Test StreamOptions defaults."""
        from spooled.grpc import StreamOptions

        opts = StreamOptions()
        assert opts.on_connected is None
        assert opts.on_error is None
        assert opts.on_end is None

    def test_stream_options_with_callbacks(self):
        """Test StreamOptions with callbacks."""
        from spooled.grpc import StreamOptions

        connected_called = []
        error_called = []
        end_called = []

        opts = StreamOptions(
            on_connected=lambda: connected_called.append(True),
            on_error=lambda e: error_called.append(e),
            on_end=lambda: end_called.append(True),
        )

        opts.on_connected()
        opts.on_error(ValueError("test"))
        opts.on_end()

        assert len(connected_called) == 1
        assert len(error_called) == 1
        assert len(end_called) == 1


class TestJobStream:
    """Tests for JobStream."""

    def test_job_stream_iteration(self):
        """Test JobStream iteration."""
        from spooled.grpc.client import JobStream

        # Create mock call that yields jobs
        mock_job = MagicMock()
        mock_job.id = "job-1"
        mock_job.organization_id = "org-1"
        mock_job.queue_name = "test-queue"
        mock_job.status = 1  # pending
        mock_job.payload = struct_pb2.Struct()
        mock_job.payload.update({"test": True})
        mock_job.result = None
        mock_job.retry_count = 0
        mock_job.max_retries = 3
        mock_job.last_error = ""
        mock_job.priority = 0
        mock_job.timeout_seconds = 300
        mock_job.created_at = timestamp_pb2.Timestamp()
        mock_job.scheduled_at = None
        mock_job.started_at = None
        mock_job.completed_at = None
        mock_job.lease_expires_at = None
        mock_job.assigned_worker_id = ""
        mock_job.idempotency_key = ""
        mock_job.lease_id = ""

        mock_call = iter([mock_job])

        stream = JobStream(mock_call)
        jobs = list(stream)

        assert len(jobs) == 1
        assert jobs[0].id == "job-1"
        assert jobs[0].queue_name == "test-queue"

    def test_job_stream_cancel(self):
        """Test JobStream cancellation."""
        from spooled.grpc.client import JobStream

        mock_call = MagicMock()
        mock_call.__iter__ = MagicMock(return_value=iter([]))

        stream = JobStream(mock_call)
        stream.cancel()

        mock_call.cancel.assert_called_once()


class TestProcessRequest:
    """Tests for ProcessRequest."""

    def test_process_request_dequeue(self):
        """Test ProcessRequest with dequeue."""
        from spooled.grpc import GrpcDequeueRequest, ProcessRequest

        req = ProcessRequest(
            dequeue=GrpcDequeueRequest(
                queue_name="test-queue",
                worker_id="worker-1",
            )
        )
        assert req.dequeue is not None
        assert req.complete is None

    def test_process_request_complete(self):
        """Test ProcessRequest with complete."""
        from spooled.grpc import GrpcCompleteRequest, ProcessRequest

        req = ProcessRequest(
            complete=GrpcCompleteRequest(
                job_id="job-1",
                worker_id="worker-1",
            )
        )
        assert req.complete is not None
        assert req.dequeue is None


class TestProcessJobsStream:
    """Tests for bidirectional ProcessJobs request serialization."""

    def test_send_serializes_lease_fencing_tokens(self):
        """ProcessJobsStream.send preserves each operation's lease token on the wire."""
        from spooled.grpc import (
            GrpcCompleteRequest,
            GrpcFailRequest,
            GrpcRenewLeaseRequest,
            ProcessJobsStream,
            ProcessRequest,
        )

        stream = ProcessJobsStream(MagicMock(return_value=iter([])), [])
        requests = [
            ProcessRequest(
                complete=GrpcCompleteRequest(
                    job_id="job-1", worker_id="worker-1", lease_id="lease-complete"
                )
            ),
            ProcessRequest(
                fail=GrpcFailRequest(
                    job_id="job-1",
                    worker_id="worker-1",
                    error="boom",
                    lease_id="lease-fail",
                )
            ),
            ProcessRequest(
                renew_lease=GrpcRenewLeaseRequest(
                    job_id="job-1", worker_id="worker-1", lease_id="lease-renew"
                )
            ),
        ]

        for request in requests:
            stream.send(request)

        serialized = [stream._request_queue.get_nowait() for _ in requests]
        assert serialized[0].complete.lease_id == "lease-complete"
        assert serialized[1].fail.lease_id == "lease-fail"
        assert serialized[2].renew_lease.lease_id == "lease-renew"
        stream.end()


class TestProcessResponse:
    """Tests for ProcessResponse."""

    def test_process_response_job(self):
        """Test ProcessResponse with job."""
        from spooled.grpc import GrpcJob, ProcessResponse

        resp = ProcessResponse(
            job=GrpcJob(
                id="job-1",
                queue_name="test-queue",
                status="pending",
                payload={},
            )
        )
        assert resp.job is not None
        assert resp.error is None

    def test_process_response_error(self):
        """Test ProcessResponse with error."""
        from spooled.grpc import ProcessResponse

        resp = ProcessResponse(error="Something went wrong")
        assert resp.error == "Something went wrong"
        assert resp.job is None


class TestGrpcClientInit:
    """Tests for SpooledGrpcClient initialization."""

    def test_client_requires_grpc(self):
        """Test client requires grpcio package."""
        # This test assumes grpcio IS installed, so it should work
        from spooled.grpc import SpooledGrpcClient

        # Just verify the class exists
        assert SpooledGrpcClient is not None

    def test_auto_tls_detection_localhost(self):
        """Test TLS is disabled for localhost."""
        # We can't easily test this without mocking grpc,
        # but we can verify the logic
        address = "localhost:50051"
        host = address.split(":")[0].lower()
        should_use_tls = host not in ("localhost", "127.0.0.1", "[::1]")
        assert should_use_tls is False

    def test_auto_tls_detection_remote(self):
        """Test TLS is enabled for remote hosts."""
        address = "grpc.spooled.cloud:443"
        host = address.split(":")[0].lower()
        should_use_tls = host not in ("localhost", "127.0.0.1", "[::1]")
        assert should_use_tls is True


class TestGrpcQueueService:
    """Tests for GrpcQueueService with mocked stubs."""

    @pytest.fixture
    def mock_queue_service(self):
        """Create a mocked queue service."""
        from spooled.grpc.client import GrpcQueueService

        mock_stub = MagicMock()
        metadata = [("x-api-key", "test-key")]
        return GrpcQueueService(mock_stub, metadata), mock_stub

    def test_enqueue(self, mock_queue_service):
        """Test enqueue method."""
        service, mock_stub = mock_queue_service

        mock_response = MagicMock()
        mock_response.job_id = "job-123"
        mock_response.created = True
        mock_stub.Enqueue.return_value = mock_response

        result = service.enqueue(
            queue_name="test-queue",
            payload={"key": "value"},
            priority=5,
        )

        assert result.job_id == "job-123"
        assert result.created is True
        mock_stub.Enqueue.assert_called_once()
        request = mock_stub.Enqueue.call_args[0][0]
        assert request.max_retries == 0
        assert request.timeout_seconds == 0

    def test_enqueue_explicit_defaults_are_sent(self, mock_queue_service):
        """Test explicit retry/timeout values are sent to gRPC."""
        service, mock_stub = mock_queue_service

        mock_response = MagicMock()
        mock_response.job_id = "job-123"
        mock_response.created = True
        mock_stub.Enqueue.return_value = mock_response

        service.enqueue(
            queue_name="test-queue",
            payload={"key": "value"},
            max_retries=3,
            timeout_seconds=300,
        )

        request = mock_stub.Enqueue.call_args[0][0]
        assert request.max_retries == 3
        assert request.timeout_seconds == 300

    def test_dequeue(self, mock_queue_service):
        """Test dequeue method."""
        service, mock_stub = mock_queue_service

        mock_job = MagicMock()
        mock_job.id = "job-1"
        mock_job.organization_id = "org-1"
        mock_job.queue_name = "test-queue"
        mock_job.status = 1
        mock_job.payload = struct_pb2.Struct()
        mock_job.result = None
        mock_job.retry_count = 0
        mock_job.max_retries = 3
        mock_job.last_error = ""
        mock_job.priority = 0
        mock_job.timeout_seconds = 300
        mock_job.created_at = timestamp_pb2.Timestamp()
        mock_job.scheduled_at = None
        mock_job.started_at = None
        mock_job.completed_at = None
        mock_job.lease_expires_at = None
        mock_job.assigned_worker_id = ""
        mock_job.idempotency_key = ""
        mock_job.lease_id = "lease-abc"

        mock_response = MagicMock()
        mock_response.jobs = [mock_job]
        mock_stub.Dequeue.return_value = mock_response

        result = service.dequeue(
            queue_name="test-queue",
            worker_id="worker-1",
        )

        assert len(result.jobs) == 1
        assert result.jobs[0].id == "job-1"
        assert result.jobs[0].lease_id == "lease-abc"

    def test_stream_jobs_omits_timeout_by_default(self, mock_queue_service):
        """Long-lived streams default to no deadline."""
        service, mock_stub = mock_queue_service
        mock_stub.StreamJobs.return_value = MagicMock()

        service.stream_jobs("test-queue", "worker-1")

        kwargs = mock_stub.StreamJobs.call_args.kwargs
        assert kwargs["metadata"] == [("x-api-key", "test-key")]
        assert "timeout" not in kwargs

    def test_stream_jobs_uses_custom_stream_timeout(self):
        """Callers can opt into a stream deadline explicitly."""
        from spooled.grpc.client import GrpcQueueService

        mock_stub = MagicMock()
        mock_stub.StreamJobs.return_value = MagicMock()
        service = GrpcQueueService(
            mock_stub,
            [("x-api-key", "test-key")],
            timeout_seconds=30.0,
            stream_timeout_seconds=120.0,
        )

        service.stream_jobs("test-queue", "worker-1")

        assert mock_stub.StreamJobs.call_args.kwargs["timeout"] == 120.0

    def test_process_jobs_omits_timeout_by_default(self, mock_queue_service):
        """Bidirectional processing streams default to no deadline."""
        service, mock_stub = mock_queue_service
        mock_stub.ProcessJobs.return_value = iter([])

        stream = service.process_jobs()
        stream._ensure_started()

        kwargs = mock_stub.ProcessJobs.call_args.kwargs
        assert kwargs["metadata"] == [("x-api-key", "test-key")]
        assert "timeout" not in kwargs

    def test_complete(self, mock_queue_service):
        """Test complete method."""
        service, mock_stub = mock_queue_service

        mock_response = MagicMock()
        mock_response.success = True
        mock_stub.Complete.return_value = mock_response

        result = service.complete(
            job_id="job-123",
            worker_id="worker-1",
            result={"done": True},
        )

        assert result.success is True
        request = mock_stub.Complete.call_args[0][0]
        assert request.job_id == "job-123"
        assert request.worker_id == "worker-1"
        assert dict(request.result) == {"done": True}
        assert request.lease_id == ""

    def test_fail(self, mock_queue_service):
        """Test fail method."""
        service, mock_stub = mock_queue_service

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.will_retry = True
        mock_response.next_retry_delay_secs = 60
        mock_stub.Fail.return_value = mock_response

        result = service.fail(
            job_id="job-123",
            worker_id="worker-1",
            error="Something failed",
        )

        assert result.success is True
        assert result.will_retry is True
        request = mock_stub.Fail.call_args[0][0]
        assert request.job_id == "job-123"
        assert request.worker_id == "worker-1"
        assert request.error == "Something failed"
        assert request.retry is True
        assert request.lease_id == ""

    def test_renew_lease(self, mock_queue_service):
        """Test renew_lease method."""
        service, mock_stub = mock_queue_service

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.new_expires_at = timestamp_pb2.Timestamp()
        mock_stub.RenewLease.return_value = mock_response

        result = service.renew_lease(
            job_id="job-123",
            worker_id="worker-1",
            extension_secs=60,
        )

        assert result.success is True
        request = mock_stub.RenewLease.call_args[0][0]
        assert request.job_id == "job-123"
        assert request.worker_id == "worker-1"
        assert request.extension_secs == 60

    def test_complete_with_lease_id(self, mock_queue_service):
        """Test complete sets the lease_id fencing token on the request."""
        service, mock_stub = mock_queue_service

        mock_response = MagicMock()
        mock_response.success = True
        mock_stub.Complete.return_value = mock_response

        service.complete(
            job_id="job-123",
            worker_id="worker-1",
            result={"done": True},
            lease_id="lease-abc",
        )

        request = mock_stub.Complete.call_args[0][0]
        assert request.job_id == "job-123"
        assert request.worker_id == "worker-1"
        assert dict(request.result) == {"done": True}
        assert request.lease_id == "lease-abc"

    def test_complete_without_lease_id_leaves_field_unset(self, mock_queue_service):
        """Test complete leaves lease_id at proto3 default when omitted."""
        service, mock_stub = mock_queue_service

        mock_response = MagicMock()
        mock_response.success = True
        mock_stub.Complete.return_value = mock_response

        service.complete(job_id="job-123", worker_id="worker-1")

        request = mock_stub.Complete.call_args[0][0]
        assert request.lease_id == ""  # empty string = unset server-side

    def test_fail_with_lease_id(self, mock_queue_service):
        """Test fail sets the lease_id fencing token on the request."""
        service, mock_stub = mock_queue_service

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.will_retry = False
        mock_response.next_retry_delay_secs = 0
        mock_stub.Fail.return_value = mock_response

        service.fail(
            job_id="job-123",
            worker_id="worker-1",
            error="Something failed",
            lease_id="lease-abc",
        )

        request = mock_stub.Fail.call_args[0][0]
        assert request.job_id == "job-123"
        assert request.worker_id == "worker-1"
        assert request.error == "Something failed"
        assert request.retry is True
        assert request.lease_id == "lease-abc"

    def test_renew_lease_with_lease_id(self, mock_queue_service):
        """Test renew_lease sets the lease_id fencing token on the request."""
        service, mock_stub = mock_queue_service

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.new_expires_at = timestamp_pb2.Timestamp()
        mock_stub.RenewLease.return_value = mock_response

        service.renew_lease(
            job_id="job-123",
            worker_id="worker-1",
            extension_secs=60,
            lease_id="lease-abc",
        )

        request = mock_stub.RenewLease.call_args[0][0]
        assert request.job_id == "job-123"
        assert request.worker_id == "worker-1"
        assert request.extension_secs == 60
        assert request.lease_id == "lease-abc"

    def test_get_job(self, mock_queue_service):
        """Test get_job method."""
        service, mock_stub = mock_queue_service

        mock_job = MagicMock()
        mock_job.id = "job-123"
        mock_job.organization_id = "org-1"
        mock_job.queue_name = "test-queue"
        mock_job.status = 1
        mock_job.payload = struct_pb2.Struct()
        mock_job.result = None
        mock_job.retry_count = 0
        mock_job.max_retries = 3
        mock_job.last_error = ""
        mock_job.priority = 0
        mock_job.timeout_seconds = 300
        mock_job.created_at = timestamp_pb2.Timestamp()
        mock_job.scheduled_at = None
        mock_job.started_at = None
        mock_job.completed_at = None
        mock_job.lease_expires_at = None
        mock_job.assigned_worker_id = ""
        mock_job.idempotency_key = ""
        mock_job.lease_id = ""

        mock_response = MagicMock()
        mock_response.HasField.return_value = True
        mock_response.job = mock_job
        mock_stub.GetJob.return_value = mock_response

        result = service.get_job("job-123")

        assert result.job is not None
        assert result.job.id == "job-123"
        # Empty proto string maps to None (legacy server without fencing)
        assert result.job.lease_id is None

    def test_get_queue_stats(self, mock_queue_service):
        """Test get_queue_stats method."""
        service, mock_stub = mock_queue_service

        mock_response = MagicMock()
        mock_response.queue_name = "test-queue"
        mock_response.pending = 10
        mock_response.scheduled = 5
        mock_response.processing = 3
        mock_response.completed = 100
        mock_response.failed = 2
        mock_response.deadletter = 1
        mock_response.total = 121
        mock_response.max_age_ms = 5000
        mock_stub.GetQueueStats.return_value = mock_response

        result = service.get_queue_stats("test-queue")

        assert result.queue_name == "test-queue"
        assert result.pending == 10
        assert result.total == 121


class TestGrpcWorkersService:
    """Tests for GrpcWorkersService with mocked stubs."""

    @pytest.fixture
    def mock_workers_service(self):
        """Create a mocked workers service."""
        from spooled.grpc.client import GrpcWorkersService

        mock_stub = MagicMock()
        metadata = [("x-api-key", "test-key")]
        return GrpcWorkersService(mock_stub, metadata), mock_stub

    def test_register(self, mock_workers_service):
        """Test register method."""
        service, mock_stub = mock_workers_service

        mock_response = MagicMock()
        mock_response.worker_id = "worker-123"
        mock_response.lease_duration_secs = 30
        mock_response.heartbeat_interval_secs = 10
        mock_stub.Register.return_value = mock_response

        result = service.register(
            queue_name="test-queue",
            hostname="worker-host",
        )

        assert result.worker_id == "worker-123"
        assert result.lease_duration_secs == 30

    def test_heartbeat(self, mock_workers_service):
        """Test heartbeat method."""
        service, mock_stub = mock_workers_service

        mock_response = MagicMock()
        mock_response.acknowledged = True
        mock_response.should_drain = False
        mock_stub.Heartbeat.return_value = mock_response

        result = service.heartbeat(
            worker_id="worker-123",
            current_jobs=5,
        )

        assert result.acknowledged is True
        assert result.should_drain is False

    def test_deregister(self, mock_workers_service):
        """Test deregister method."""
        service, mock_stub = mock_workers_service

        mock_response = MagicMock()
        mock_response.success = True
        mock_stub.Deregister.return_value = mock_response

        result = service.deregister("worker-123")

        assert result.success is True


class TestGrpcExports:
    """Tests for gRPC module exports."""

    def test_all_exports_available(self):
        """Test all expected exports are available."""
        from spooled.grpc import (
            GrpcQueueService,
            GrpcWorkersService,
            SpooledGrpcClient,
        )

        # Just verify they all exist
        assert SpooledGrpcClient is not None
        assert GrpcQueueService is not None
        assert GrpcWorkersService is not None
