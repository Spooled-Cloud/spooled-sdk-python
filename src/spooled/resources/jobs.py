"""
Jobs resource for Spooled SDK.
"""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING, Any

from spooled.resources.base import AsyncBaseResource, BaseResource
from spooled.types.common import Page, parse_has_more
from spooled.types.jobs import (
    BatchJobStatus,
    BoostPriorityResponse,
    BulkEnqueueParams,
    BulkEnqueueResponse,
    ClaimJobsParams,
    ClaimJobsResponse,
    CompleteJobParams,
    CompleteJobResponse,
    CreateJobParams,
    CreateJobResponse,
    FailJobParams,
    FailJobResponse,
    Job,
    JobHeartbeatParams,
    JobHistoryEvent,
    JobHistoryParams,
    JobStats,
    JobSummary,
    ListDlqParams,
    ListJobsParams,
    PurgeDlqParams,
    PurgeDlqResponse,
    RetryDlqParams,
    RetryDlqResponse,
)

if TYPE_CHECKING:
    from spooled.utils.async_http import AsyncHttpClient
    from spooled.utils.http import HttpClient


class DlqResource:
    """Dead-letter queue operations (sync)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def list(self, params: ListDlqParams | dict[str, Any] | None = None) -> Page[JobSummary]:
        """List jobs in dead-letter queue.

        Returns a list with ``has_more`` (from ``X-Has-More``) for paging.
        """
        if isinstance(params, dict):
            params = ListDlqParams.model_validate(params)
        query_params = params.to_query() if params else None
        data, headers = self._http.get("/jobs/dlq", params=query_params, with_headers=True)
        return Page(
            (JobSummary.model_validate(item) for item in data), has_more=parse_has_more(headers)
        )

    def retry(self, params: RetryDlqParams | dict[str, Any]) -> RetryDlqResponse:
        """Retry jobs from DLQ."""
        if isinstance(params, dict):
            params = RetryDlqParams.model_validate(params)
        data = self._http.post("/jobs/dlq/retry", params.model_dump(exclude_none=True))
        return RetryDlqResponse.model_validate(data)

    def purge(self, params: PurgeDlqParams | dict[str, Any]) -> PurgeDlqResponse:
        """Purge jobs from DLQ."""
        if isinstance(params, dict):
            params = PurgeDlqParams.model_validate(params)
        data = self._http.post("/jobs/dlq/purge", params.to_payload())
        return PurgeDlqResponse.model_validate(data)


class AsyncDlqResource:
    """Dead-letter queue operations (async)."""

    def __init__(self, http: AsyncHttpClient) -> None:
        self._http = http

    async def list(self, params: ListDlqParams | dict[str, Any] | None = None) -> Page[JobSummary]:
        """List jobs in dead-letter queue.

        Returns a list with ``has_more`` (from ``X-Has-More``) for paging.
        """
        if isinstance(params, dict):
            params = ListDlqParams.model_validate(params)
        query_params = params.to_query() if params else None
        data, headers = await self._http.get("/jobs/dlq", params=query_params, with_headers=True)
        return Page(
            (JobSummary.model_validate(item) for item in data), has_more=parse_has_more(headers)
        )

    async def retry(self, params: RetryDlqParams | dict[str, Any]) -> RetryDlqResponse:
        """Retry jobs from DLQ."""
        if isinstance(params, dict):
            params = RetryDlqParams.model_validate(params)
        data = await self._http.post("/jobs/dlq/retry", params.model_dump(exclude_none=True))
        return RetryDlqResponse.model_validate(data)

    async def purge(self, params: PurgeDlqParams | dict[str, Any]) -> PurgeDlqResponse:
        """Purge jobs from DLQ."""
        if isinstance(params, dict):
            params = PurgeDlqParams.model_validate(params)
        data = await self._http.post("/jobs/dlq/purge", params.to_payload())
        return PurgeDlqResponse.model_validate(data)


class JobsResource(BaseResource):
    """Jobs resource (sync)."""

    def __init__(self, http: HttpClient) -> None:
        super().__init__(http)
        self._dlq = DlqResource(http)

    @property
    def dlq(self) -> DlqResource:
        """Dead-letter queue operations."""
        return self._dlq

    def create(self, params: CreateJobParams | dict[str, Any]) -> CreateJobResponse:
        """Create a new job."""
        if isinstance(params, dict):
            params = CreateJobParams.model_validate(params)
        data = self._http.post(
            "/jobs", params.model_dump(exclude_none=True, exclude_unset=True, mode="json")
        )
        return CreateJobResponse.model_validate(data)

    def create_and_get(self, params: CreateJobParams | dict[str, Any]) -> Job:
        """Create a job and return the full job object."""
        result = self.create(params)
        return self.get(result.id)

    def list(self, params: ListJobsParams | dict[str, Any] | None = None) -> Page[JobSummary]:
        """List jobs with optional filtering.

        Filters: ``queue_name``, ``status`` (one, a list or ``"a,b"``), ``q``,
        ``job_type``, ``created_after``, ``created_before``, ``tag``. Returns a
        list with ``has_more`` (from ``X-Has-More``): when it is ``True``, ask
        for the next page with ``offset + limit``.
        """
        if isinstance(params, dict):
            params = ListJobsParams.model_validate(params)
        query_params = params.to_query() if params else None
        data, headers = self._http.get("/jobs", params=query_params, with_headers=True)
        return Page(
            (JobSummary.model_validate(item) for item in data), has_more=parse_has_more(headers)
        )

    def get(self, job_id: str) -> Job:
        """Get a job by ID."""
        data = self._http.get(f"/jobs/{job_id}")
        return Job.model_validate(data)

    def history(
        self, job_id: str, params: JobHistoryParams | dict[str, Any] | None = None
    ) -> Page[JobHistoryEvent]:
        """A job's recorded lifecycle events (``GET /jobs/{id}/history``).

        Oldest first unless ``order_dir="desc"``. Returns a list with
        ``has_more`` for paging. Another organization's job, or one outside an
        API key's queue scope, raises ``NotFoundError``.
        """
        if isinstance(params, dict):
            params = JobHistoryParams.model_validate(params)
        query_params = params.model_dump(exclude_none=True) if params else None
        data, headers = self._http.get(
            f"/jobs/{job_id}/history", params=query_params, with_headers=True
        )
        return Page(
            (JobHistoryEvent.model_validate(item) for item in data),
            has_more=parse_has_more(headers),
        )

    def cancel(self, job_id: str) -> None:
        """Cancel a pending or scheduled job."""
        self._http.delete(f"/jobs/{job_id}")

    def retry(self, job_id: str) -> Job:
        """Retry a failed or dead-lettered job."""
        data = self._http.post(f"/jobs/{job_id}/retry")
        return Job.model_validate(data)

    def boost_priority(self, job_id: str, priority: int) -> BoostPriorityResponse:
        """Boost job priority."""
        data = self._http.put(f"/jobs/{job_id}/priority", {"priority": priority})
        return BoostPriorityResponse.model_validate(data)

    def get_stats(self) -> JobStats:
        """Get job statistics."""
        data = self._http.get("/jobs/stats")
        return JobStats.model_validate(data)

    def batch_status(self, job_ids: builtins.list[str]) -> builtins.list[BatchJobStatus]:
        """Get status of multiple jobs at once."""
        if not job_ids:
            return []
        if len(job_ids) > 100:
            raise ValueError("Maximum 100 job IDs allowed per request")
        data = self._http.get("/jobs/status", params={"ids": ",".join(job_ids)})
        return [BatchJobStatus.model_validate(item) for item in data]

    def bulk_enqueue(self, params: BulkEnqueueParams | dict[str, Any]) -> BulkEnqueueResponse:
        """Bulk enqueue multiple jobs."""
        if isinstance(params, dict):
            params = BulkEnqueueParams.model_validate(params)
        data = self._http.post("/jobs/bulk", params.model_dump(exclude_none=True, mode="json"))
        return BulkEnqueueResponse.model_validate(data)

    # Worker processing endpoints

    def claim(self, params: ClaimJobsParams | dict[str, Any]) -> ClaimJobsResponse:
        """Claim jobs for worker processing."""
        if isinstance(params, dict):
            params = ClaimJobsParams.model_validate(params)
        data = self._http.post("/jobs/claim", params.model_dump(exclude_none=True))
        return ClaimJobsResponse.model_validate(data)

    def complete(
        self, job_id: str, params: CompleteJobParams | dict[str, Any]
    ) -> CompleteJobResponse:
        """Complete a job (worker ack).

        Lease-fenced on the server, so a network error, timeout or 5xx is retried
        (a replay of an already-landed ack answers 409 instead of acting twice).
        """
        if isinstance(params, dict):
            params = CompleteJobParams.model_validate(params)
        data = self._http.post(
            f"/jobs/{job_id}/complete",
            params.model_dump(exclude_none=True, mode="json"),
            idempotent=True,
        )
        return CompleteJobResponse.model_validate(data)

    def fail(self, job_id: str, params: FailJobParams | dict[str, Any]) -> FailJobResponse:
        """Fail a job (worker nack)."""
        if isinstance(params, dict):
            params = FailJobParams.model_validate(params)
        data = self._http.post(
            f"/jobs/{job_id}/fail", params.model_dump(exclude_none=True), idempotent=True
        )
        return FailJobResponse.model_validate(data)

    def heartbeat(self, job_id: str, params: JobHeartbeatParams | dict[str, Any]) -> None:
        """Extend job lease (heartbeat)."""
        if isinstance(params, dict):
            params = JobHeartbeatParams.model_validate(params)
        self._http.post(
            f"/jobs/{job_id}/heartbeat", params.model_dump(exclude_none=True), idempotent=True
        )


class AsyncJobsResource(AsyncBaseResource):
    """Jobs resource (async)."""

    def __init__(self, http: AsyncHttpClient) -> None:
        super().__init__(http)
        self._dlq = AsyncDlqResource(http)

    @property
    def dlq(self) -> AsyncDlqResource:
        """Dead-letter queue operations."""
        return self._dlq

    async def create(self, params: CreateJobParams | dict[str, Any]) -> CreateJobResponse:
        """Create a new job."""
        if isinstance(params, dict):
            params = CreateJobParams.model_validate(params)
        data = await self._http.post(
            "/jobs", params.model_dump(exclude_none=True, exclude_unset=True, mode="json")
        )
        return CreateJobResponse.model_validate(data)

    async def create_and_get(self, params: CreateJobParams | dict[str, Any]) -> Job:
        """Create a job and return the full job object."""
        result = await self.create(params)
        return await self.get(result.id)

    async def list(self, params: ListJobsParams | dict[str, Any] | None = None) -> Page[JobSummary]:
        """List jobs with optional filtering (see ``JobsResource.list``)."""
        if isinstance(params, dict):
            params = ListJobsParams.model_validate(params)
        query_params = params.to_query() if params else None
        data, headers = await self._http.get("/jobs", params=query_params, with_headers=True)
        return Page(
            (JobSummary.model_validate(item) for item in data), has_more=parse_has_more(headers)
        )

    async def get(self, job_id: str) -> Job:
        """Get a job by ID."""
        data = await self._http.get(f"/jobs/{job_id}")
        return Job.model_validate(data)

    async def history(
        self, job_id: str, params: JobHistoryParams | dict[str, Any] | None = None
    ) -> Page[JobHistoryEvent]:
        """A job's recorded lifecycle events (see ``JobsResource.history``)."""
        if isinstance(params, dict):
            params = JobHistoryParams.model_validate(params)
        query_params = params.model_dump(exclude_none=True) if params else None
        data, headers = await self._http.get(
            f"/jobs/{job_id}/history", params=query_params, with_headers=True
        )
        return Page(
            (JobHistoryEvent.model_validate(item) for item in data),
            has_more=parse_has_more(headers),
        )

    async def cancel(self, job_id: str) -> None:
        """Cancel a pending or scheduled job."""
        await self._http.delete(f"/jobs/{job_id}")

    async def retry(self, job_id: str) -> Job:
        """Retry a failed or dead-lettered job."""
        data = await self._http.post(f"/jobs/{job_id}/retry")
        return Job.model_validate(data)

    async def boost_priority(self, job_id: str, priority: int) -> BoostPriorityResponse:
        """Boost job priority."""
        data = await self._http.put(f"/jobs/{job_id}/priority", {"priority": priority})
        return BoostPriorityResponse.model_validate(data)

    async def get_stats(self) -> JobStats:
        """Get job statistics."""
        data = await self._http.get("/jobs/stats")
        return JobStats.model_validate(data)

    async def batch_status(self, job_ids: builtins.list[str]) -> builtins.list[BatchJobStatus]:
        """Get status of multiple jobs at once."""
        if not job_ids:
            return []
        if len(job_ids) > 100:
            raise ValueError("Maximum 100 job IDs allowed per request")
        data = await self._http.get("/jobs/status", params={"ids": ",".join(job_ids)})
        return [BatchJobStatus.model_validate(item) for item in data]

    async def bulk_enqueue(self, params: BulkEnqueueParams | dict[str, Any]) -> BulkEnqueueResponse:
        """Bulk enqueue multiple jobs."""
        if isinstance(params, dict):
            params = BulkEnqueueParams.model_validate(params)
        data = await self._http.post(
            "/jobs/bulk", params.model_dump(exclude_none=True, mode="json")
        )
        return BulkEnqueueResponse.model_validate(data)

    # Worker processing endpoints

    async def claim(self, params: ClaimJobsParams | dict[str, Any]) -> ClaimJobsResponse:
        """Claim jobs for worker processing."""
        if isinstance(params, dict):
            params = ClaimJobsParams.model_validate(params)
        data = await self._http.post("/jobs/claim", params.model_dump(exclude_none=True))
        return ClaimJobsResponse.model_validate(data)

    async def complete(
        self, job_id: str, params: CompleteJobParams | dict[str, Any]
    ) -> CompleteJobResponse:
        """Complete a job (worker ack).

        Lease-fenced on the server, so a network error, timeout or 5xx is retried
        (a replay of an already-landed ack answers 409 instead of acting twice).
        """
        if isinstance(params, dict):
            params = CompleteJobParams.model_validate(params)
        data = await self._http.post(
            f"/jobs/{job_id}/complete",
            params.model_dump(exclude_none=True, mode="json"),
            idempotent=True,
        )
        return CompleteJobResponse.model_validate(data)

    async def fail(self, job_id: str, params: FailJobParams | dict[str, Any]) -> FailJobResponse:
        """Fail a job (worker nack)."""
        if isinstance(params, dict):
            params = FailJobParams.model_validate(params)
        data = await self._http.post(
            f"/jobs/{job_id}/fail", params.model_dump(exclude_none=True), idempotent=True
        )
        return FailJobResponse.model_validate(data)

    async def heartbeat(self, job_id: str, params: JobHeartbeatParams | dict[str, Any]) -> None:
        """Extend job lease (heartbeat)."""
        if isinstance(params, dict):
            params = JobHeartbeatParams.model_validate(params)
        await self._http.post(
            f"/jobs/{job_id}/heartbeat", params.model_dump(exclude_none=True), idempotent=True
        )
