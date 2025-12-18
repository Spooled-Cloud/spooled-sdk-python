"""
Workers resource for Spooled SDK.
"""

from __future__ import annotations

from typing import Any

from spooled.resources.base import AsyncBaseResource, BaseResource
from spooled.types.workers import (
    RegisterWorkerParams,
    RegisterWorkerResponse,
    Worker,
    WorkerHeartbeatParams,
    WorkerSummary,
)


class WorkersResource(BaseResource):
    """Workers resource (sync)."""

    def list(self) -> list[WorkerSummary]:
        """List all workers."""
        data = self._http.get("/workers")
        return [WorkerSummary.model_validate(item) for item in data]

    def get(self, worker_id: str) -> Worker:
        """Get a worker by ID."""
        data = self._http.get(f"/workers/{worker_id}")
        return Worker.model_validate(data)

    def register(
        self, params: RegisterWorkerParams | dict[str, Any]
    ) -> RegisterWorkerResponse:
        """Register a worker."""
        if isinstance(params, dict):
            params = RegisterWorkerParams.model_validate(params)
        data = self._http.post("/workers/register", params.model_dump(exclude_none=True))
        return RegisterWorkerResponse.model_validate(data)

    def heartbeat(
        self, worker_id: str, params: WorkerHeartbeatParams | dict[str, Any]
    ) -> None:
        """Send worker heartbeat."""
        if isinstance(params, dict):
            params = WorkerHeartbeatParams.model_validate(params)
        self._http.post(f"/workers/{worker_id}/heartbeat", params.model_dump(exclude_none=True))

    def deregister(self, worker_id: str) -> None:
        """Deregister a worker."""
        self._http.post(f"/workers/{worker_id}/deregister")


class AsyncWorkersResource(AsyncBaseResource):
    """Workers resource (async)."""

    async def list(self) -> list[WorkerSummary]:
        """List all workers."""
        data = await self._http.get("/workers")
        return [WorkerSummary.model_validate(item) for item in data]

    async def get(self, worker_id: str) -> Worker:
        """Get a worker by ID."""
        data = await self._http.get(f"/workers/{worker_id}")
        return Worker.model_validate(data)

    async def register(
        self, params: RegisterWorkerParams | dict[str, Any]
    ) -> RegisterWorkerResponse:
        """Register a worker."""
        if isinstance(params, dict):
            params = RegisterWorkerParams.model_validate(params)
        data = await self._http.post("/workers/register", params.model_dump(exclude_none=True))
        return RegisterWorkerResponse.model_validate(data)

    async def heartbeat(
        self, worker_id: str, params: WorkerHeartbeatParams | dict[str, Any]
    ) -> None:
        """Send worker heartbeat."""
        if isinstance(params, dict):
            params = WorkerHeartbeatParams.model_validate(params)
        await self._http.post(
            f"/workers/{worker_id}/heartbeat", params.model_dump(exclude_none=True)
        )

    async def deregister(self, worker_id: str) -> None:
        """Deregister a worker."""
        await self._http.post(f"/workers/{worker_id}/deregister")
