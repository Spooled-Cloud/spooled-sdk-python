"""gRPC lease default, integer decoding and client-side cancel.

NP-3: ``dequeue``/``stream_jobs`` sent ``lease_duration_secs=30`` when the caller
omitted it, so the server's gRPC default (300 s) never applied. NP-4: ``Struct``
numbers are doubles and decoded as floats (``{"x": 1}`` came back as
``{"x": 1.0}``). NP-13: cancelling a stream from the client made the loop that
iterated it raise ``ServerError("Locally cancelled by application!")``.
"""

from __future__ import annotations

import threading
from typing import Any
from unittest.mock import MagicMock

import pytest
from google.protobuf import struct_pb2

grpc = pytest.importorskip("grpc")

from spooled.errors import SpooledError  # noqa: E402
from spooled.grpc import GrpcDequeueRequest, ProcessRequest  # noqa: E402
from spooled.grpc.client import (  # noqa: E402
    GrpcQueueService,
    JobStream,
    ProcessJobsStream,
    StreamOptions,
    _proto_job_to_grpc_job,
    _struct_to_dict,
)


def _service() -> tuple[GrpcQueueService, MagicMock]:
    stub = MagicMock()
    return GrpcQueueService(stub, [("x-api-key", "k")]), stub


class TestLeaseDefault:
    def test_dequeue_leaves_the_lease_unset_by_default(self) -> None:
        service, stub = _service()
        stub.Dequeue.return_value = MagicMock(jobs=[])

        service.dequeue("q", "w")

        request = stub.Dequeue.call_args[0][0]
        # 0 is "unset" for a proto3 int32; the server applies its default.
        assert request.lease_duration_secs == 0

    def test_dequeue_sends_an_explicit_lease(self) -> None:
        service, stub = _service()
        stub.Dequeue.return_value = MagicMock(jobs=[])

        service.dequeue("q", "w", lease_duration_secs=60)

        assert stub.Dequeue.call_args[0][0].lease_duration_secs == 60

    def test_stream_jobs_leaves_the_lease_unset_by_default(self) -> None:
        service, stub = _service()

        service.stream_jobs("q", "w")
        assert stub.StreamJobs.call_args[0][0].lease_duration_secs == 0

        service.stream_jobs("q", "w", lease_duration_secs=120)
        assert stub.StreamJobs.call_args[0][0].lease_duration_secs == 120

    def test_process_jobs_dequeue_leaves_the_lease_unset_by_default(self) -> None:
        assert GrpcDequeueRequest(queue_name="q", worker_id="w").lease_duration_secs is None

        stream = ProcessJobsStream(MagicMock(), [])
        stream.send(ProcessRequest(dequeue=GrpcDequeueRequest(queue_name="q", worker_id="w")))
        stream.send(
            ProcessRequest(
                dequeue=GrpcDequeueRequest(queue_name="q", worker_id="w", lease_duration_secs=45)
            )
        )

        first = stream._request_queue.get_nowait()
        second = stream._request_queue.get_nowait()
        assert first.dequeue.lease_duration_secs == 0
        assert second.dequeue.lease_duration_secs == 45


class TestIntegerDecoding:
    def test_whole_numbers_come_back_as_int(self) -> None:
        struct = struct_pb2.Struct()
        struct.update(
            {
                "x": 1,
                "neg": -4,
                "zero": 0,
                "price": 1.5,
                "flag": True,
                "none": None,
                "name": "a",
                "nested": {"items": [1, 2.5, {"y": 3}], "deep": {"z": 10}},
            }
        )

        result = _struct_to_dict(struct)

        assert result == {
            "x": 1,
            "neg": -4,
            "zero": 0,
            "price": 1.5,
            "flag": True,
            "none": None,
            "name": "a",
            "nested": {"items": [1, 2.5, {"y": 3}], "deep": {"z": 10}},
        }
        assert result is not None
        assert type(result["x"]) is int
        assert type(result["price"]) is float
        assert type(result["flag"]) is bool
        assert type(result["nested"]["items"][0]) is int
        assert type(result["nested"]["items"][2]["y"]) is int

    def test_integers_beyond_2_pow_53_stay_float(self) -> None:
        struct = struct_pb2.Struct()
        struct.update({"safe": 2**53 - 1, "big": 2**60})

        result = _struct_to_dict(struct)

        assert result is not None
        assert result["safe"] == 2**53 - 1 and type(result["safe"]) is int
        assert type(result["big"]) is float

    def test_job_payload_and_result_keep_integers(self) -> None:
        from spooled.grpc.stubs import Job

        job = Job(id="j", queue_name="q", status=3)
        job.payload.update({"count": 2, "ratio": 0.25})
        job.result.update({"sent": 7})

        converted = _proto_job_to_grpc_job(job)

        assert converted.payload == {"count": 2, "ratio": 0.25}
        assert type(converted.payload["count"]) is int
        assert converted.result == {"sent": 7}
        assert type(converted.result["sent"]) is int


class _CancelledRpc(grpc.RpcError):
    def __init__(self, details: str = "Locally cancelled by application!") -> None:
        self._details = details

    def code(self) -> Any:
        return grpc.StatusCode.CANCELLED

    def details(self) -> str:
        return self._details


class _BlockingCall:
    """A server stream that blocks until cancel(), then raises CANCELLED like grpc does."""

    def __init__(self) -> None:
        self.cancelled = threading.Event()

    def __iter__(self) -> _BlockingCall:
        return self

    def __next__(self) -> Any:
        self.cancelled.wait(5)
        raise _CancelledRpc()

    def cancel(self) -> None:
        self.cancelled.set()


class TestClientCancel:
    def test_cancel_from_another_thread_ends_iteration_quietly(self) -> None:
        call = _BlockingCall()
        ended: list[bool] = []
        errors: list[Exception] = []
        stream = JobStream(
            call, StreamOptions(on_end=lambda: ended.append(True), on_error=errors.append)
        )

        timer = threading.Timer(0.1, stream.cancel)
        timer.start()
        jobs = list(stream)
        timer.join()

        assert jobs == []
        assert errors == []
        assert ended == [True]
        # Iterating again stays ended and does not fire on_end twice.
        assert list(stream) == []
        assert ended == [True]

    def test_server_cancel_still_raises(self) -> None:
        class ServerCancelled:
            def __iter__(self) -> Any:
                return self

            def __next__(self) -> Any:
                raise _CancelledRpc("Cancelled by server")

        stream = JobStream(ServerCancelled())

        with pytest.raises(SpooledError):
            next(stream)

    def test_process_jobs_cancel_ends_receive_quietly(self) -> None:
        call = _BlockingCall()
        ended: list[bool] = []
        errors: list[Exception] = []
        stream = ProcessJobsStream(
            MagicMock(return_value=call),
            [],
            options=StreamOptions(on_end=lambda: ended.append(True), on_error=errors.append),
        )
        stream._ensure_started()

        timer = threading.Timer(0.1, stream.cancel)
        timer.start()
        responses = list(stream.receive())
        timer.join()

        assert responses == []
        assert errors == []
        assert ended == [True]
