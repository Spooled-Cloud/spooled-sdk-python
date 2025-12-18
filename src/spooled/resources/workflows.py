"""
Workflows resource for Spooled SDK.
"""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING, Any

from spooled.resources.base import AsyncBaseResource, BaseResource
from spooled.types.workflows import (
    AddDependenciesParams,
    AddDependenciesResponse,
    CreateWorkflowParams,
    CreateWorkflowResponse,
    JobWithDependencies,
    ListWorkflowsParams,
    WorkflowJob,
    WorkflowJobStatus,
    WorkflowResponse,
)

if TYPE_CHECKING:
    from spooled.utils.async_http import AsyncHttpClient
    from spooled.utils.http import HttpClient


class WorkflowJobsResource:
    """Workflow jobs operations (sync)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def list(self, workflow_id: str) -> list[WorkflowJob]:
        """List all jobs in a workflow."""
        data = self._http.get(f"/workflows/{workflow_id}/jobs")
        return [WorkflowJob.model_validate(item) for item in data]

    def get(self, workflow_id: str, job_id: str) -> WorkflowJob:
        """Get a specific job within a workflow."""
        data = self._http.get(f"/workflows/{workflow_id}/jobs/{job_id}")
        return WorkflowJob.model_validate(data)

    def get_status(self, workflow_id: str) -> builtins.list[WorkflowJobStatus]:
        """Get the status of all jobs in a workflow."""
        data = self._http.get(f"/workflows/{workflow_id}/jobs/status")
        return [WorkflowJobStatus.model_validate(item) for item in data]

    def get_dependencies(self, job_id: str) -> JobWithDependencies:
        """Get job dependencies."""
        data = self._http.get(f"/jobs/{job_id}/dependencies")
        return JobWithDependencies.model_validate(data)

    def add_dependencies(
        self, job_id: str, params: AddDependenciesParams | dict[str, Any]
    ) -> AddDependenciesResponse:
        """Add dependencies to a job."""
        if isinstance(params, dict):
            params = AddDependenciesParams.model_validate(params)
        data = self._http.post(
            f"/jobs/{job_id}/dependencies", params.model_dump(exclude_none=True)
        )
        return AddDependenciesResponse.model_validate(data)


class AsyncWorkflowJobsResource:
    """Workflow jobs operations (async)."""

    def __init__(self, http: AsyncHttpClient) -> None:
        self._http = http

    async def list(self, workflow_id: str) -> list[WorkflowJob]:
        """List all jobs in a workflow."""
        data = await self._http.get(f"/workflows/{workflow_id}/jobs")
        return [WorkflowJob.model_validate(item) for item in data]

    async def get(self, workflow_id: str, job_id: str) -> WorkflowJob:
        """Get a specific job within a workflow."""
        data = await self._http.get(f"/workflows/{workflow_id}/jobs/{job_id}")
        return WorkflowJob.model_validate(data)

    async def get_status(self, workflow_id: str) -> builtins.list[WorkflowJobStatus]:
        """Get the status of all jobs in a workflow."""
        data = await self._http.get(f"/workflows/{workflow_id}/jobs/status")
        return [WorkflowJobStatus.model_validate(item) for item in data]

    async def get_dependencies(self, job_id: str) -> JobWithDependencies:
        """Get job dependencies."""
        data = await self._http.get(f"/jobs/{job_id}/dependencies")
        return JobWithDependencies.model_validate(data)

    async def add_dependencies(
        self, job_id: str, params: AddDependenciesParams | dict[str, Any]
    ) -> AddDependenciesResponse:
        """Add dependencies to a job."""
        if isinstance(params, dict):
            params = AddDependenciesParams.model_validate(params)
        data = await self._http.post(
            f"/jobs/{job_id}/dependencies", params.model_dump(exclude_none=True)
        )
        return AddDependenciesResponse.model_validate(data)


class WorkflowsResource(BaseResource):
    """Workflows resource (sync)."""

    def __init__(self, http: HttpClient) -> None:
        super().__init__(http)
        self._jobs = WorkflowJobsResource(http)

    @property
    def jobs(self) -> WorkflowJobsResource:
        """Workflow jobs operations."""
        return self._jobs

    def list(
        self, params: ListWorkflowsParams | dict[str, Any] | None = None
    ) -> list[WorkflowResponse]:
        """List workflows."""
        if isinstance(params, dict):
            params = ListWorkflowsParams.model_validate(params)
        query_params = params.model_dump(exclude_none=True) if params else None
        data = self._http.get("/workflows", params=query_params)
        return [WorkflowResponse.model_validate(item) for item in data]

    def create(
        self, params: CreateWorkflowParams | dict[str, Any]
    ) -> CreateWorkflowResponse:
        """Create a new workflow."""
        if isinstance(params, dict):
            params = CreateWorkflowParams.model_validate(params)
        data = self._http.post("/workflows", params.model_dump(exclude_none=True, mode="json"))
        return CreateWorkflowResponse.model_validate(data)

    def get(self, workflow_id: str) -> WorkflowResponse:
        """Get a workflow by ID."""
        data = self._http.get(f"/workflows/{workflow_id}")
        return WorkflowResponse.model_validate(data)

    def cancel(self, workflow_id: str) -> WorkflowResponse:
        """Cancel a workflow."""
        data = self._http.post(f"/workflows/{workflow_id}/cancel")
        return WorkflowResponse.model_validate(data)

    def retry(self, workflow_id: str) -> WorkflowResponse:
        """Retry a failed workflow."""
        data = self._http.post(f"/workflows/{workflow_id}/retry")
        return WorkflowResponse.model_validate(data)


class AsyncWorkflowsResource(AsyncBaseResource):
    """Workflows resource (async)."""

    def __init__(self, http: AsyncHttpClient) -> None:
        super().__init__(http)
        self._jobs = AsyncWorkflowJobsResource(http)

    @property
    def jobs(self) -> AsyncWorkflowJobsResource:
        """Workflow jobs operations."""
        return self._jobs

    async def list(
        self, params: ListWorkflowsParams | dict[str, Any] | None = None
    ) -> list[WorkflowResponse]:
        """List workflows."""
        if isinstance(params, dict):
            params = ListWorkflowsParams.model_validate(params)
        query_params = params.model_dump(exclude_none=True) if params else None
        data = await self._http.get("/workflows", params=query_params)
        return [WorkflowResponse.model_validate(item) for item in data]

    async def create(
        self, params: CreateWorkflowParams | dict[str, Any]
    ) -> CreateWorkflowResponse:
        """Create a new workflow."""
        if isinstance(params, dict):
            params = CreateWorkflowParams.model_validate(params)
        data = await self._http.post(
            "/workflows", params.model_dump(exclude_none=True, mode="json")
        )
        return CreateWorkflowResponse.model_validate(data)

    async def get(self, workflow_id: str) -> WorkflowResponse:
        """Get a workflow by ID."""
        data = await self._http.get(f"/workflows/{workflow_id}")
        return WorkflowResponse.model_validate(data)

    async def cancel(self, workflow_id: str) -> WorkflowResponse:
        """Cancel a workflow."""
        data = await self._http.post(f"/workflows/{workflow_id}/cancel")
        return WorkflowResponse.model_validate(data)

    async def retry(self, workflow_id: str) -> WorkflowResponse:
        """Retry a failed workflow."""
        data = await self._http.post(f"/workflows/{workflow_id}/retry")
        return WorkflowResponse.model_validate(data)
