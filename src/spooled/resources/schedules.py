"""
Schedules resource for Spooled SDK.
"""

from __future__ import annotations

import builtins
from typing import Any

from spooled.resources.base import AsyncBaseResource, BaseResource
from spooled.types.schedules import (
    CreateScheduleParams,
    CreateScheduleResponse,
    ListSchedulesParams,
    Schedule,
    ScheduleRun,
    TriggerScheduleResponse,
    UpdateScheduleParams,
)


class SchedulesResource(BaseResource):
    """Schedules resource (sync)."""

    def list(self, params: ListSchedulesParams | dict[str, Any] | None = None) -> builtins.list[Schedule]:
        """List schedules."""
        if isinstance(params, dict):
            params = ListSchedulesParams.model_validate(params)
        query_params = params.model_dump(exclude_none=True) if params else None
        data = self._http.get("/schedules", params=query_params)
        return [Schedule.model_validate(item) for item in data]

    def create(
        self, params: CreateScheduleParams | dict[str, Any]
    ) -> CreateScheduleResponse:
        """Create a new schedule."""
        if isinstance(params, dict):
            params = CreateScheduleParams.model_validate(params)
        data = self._http.post("/schedules", params.model_dump(exclude_none=True, mode="json"))
        return CreateScheduleResponse.model_validate(data)

    def get(self, schedule_id: str) -> Schedule:
        """Get a schedule by ID."""
        data = self._http.get(f"/schedules/{schedule_id}")
        return Schedule.model_validate(data)

    def update(
        self, schedule_id: str, params: UpdateScheduleParams | dict[str, Any]
    ) -> Schedule:
        """Update a schedule."""
        if isinstance(params, dict):
            params = UpdateScheduleParams.model_validate(params)
        data = self._http.put(
            f"/schedules/{schedule_id}", params.model_dump(exclude_none=True, mode="json")
        )
        return Schedule.model_validate(data)

    def delete(self, schedule_id: str) -> None:
        """Delete a schedule."""
        self._http.delete(f"/schedules/{schedule_id}")

    def pause(self, schedule_id: str) -> Schedule:
        """Pause a schedule."""
        data = self._http.post(f"/schedules/{schedule_id}/pause")
        return Schedule.model_validate(data)

    def resume(self, schedule_id: str) -> Schedule:
        """Resume a paused schedule."""
        data = self._http.post(f"/schedules/{schedule_id}/resume")
        return Schedule.model_validate(data)

    def trigger(self, schedule_id: str) -> TriggerScheduleResponse:
        """Manually trigger a schedule."""
        data = self._http.post(f"/schedules/{schedule_id}/trigger")
        return TriggerScheduleResponse.model_validate(data)

    def get_history(self, schedule_id: str, limit: int = 10) -> builtins.list[ScheduleRun]:
        """Get schedule execution history."""
        data = self._http.get(f"/schedules/{schedule_id}/history", params={"limit": limit})
        return [ScheduleRun.model_validate(item) for item in data]


class AsyncSchedulesResource(AsyncBaseResource):
    """Schedules resource (async)."""

    async def list(
        self, params: ListSchedulesParams | dict[str, Any] | None = None
    ) -> builtins.list[Schedule]:
        """List schedules."""
        if isinstance(params, dict):
            params = ListSchedulesParams.model_validate(params)
        query_params = params.model_dump(exclude_none=True) if params else None
        data = await self._http.get("/schedules", params=query_params)
        return [Schedule.model_validate(item) for item in data]

    async def create(
        self, params: CreateScheduleParams | dict[str, Any]
    ) -> CreateScheduleResponse:
        """Create a new schedule."""
        if isinstance(params, dict):
            params = CreateScheduleParams.model_validate(params)
        data = await self._http.post(
            "/schedules", params.model_dump(exclude_none=True, mode="json")
        )
        return CreateScheduleResponse.model_validate(data)

    async def get(self, schedule_id: str) -> Schedule:
        """Get a schedule by ID."""
        data = await self._http.get(f"/schedules/{schedule_id}")
        return Schedule.model_validate(data)

    async def update(
        self, schedule_id: str, params: UpdateScheduleParams | dict[str, Any]
    ) -> Schedule:
        """Update a schedule."""
        if isinstance(params, dict):
            params = UpdateScheduleParams.model_validate(params)
        data = await self._http.put(
            f"/schedules/{schedule_id}", params.model_dump(exclude_none=True, mode="json")
        )
        return Schedule.model_validate(data)

    async def delete(self, schedule_id: str) -> None:
        """Delete a schedule."""
        await self._http.delete(f"/schedules/{schedule_id}")

    async def pause(self, schedule_id: str) -> Schedule:
        """Pause a schedule."""
        data = await self._http.post(f"/schedules/{schedule_id}/pause")
        return Schedule.model_validate(data)

    async def resume(self, schedule_id: str) -> Schedule:
        """Resume a paused schedule."""
        data = await self._http.post(f"/schedules/{schedule_id}/resume")
        return Schedule.model_validate(data)

    async def trigger(self, schedule_id: str) -> TriggerScheduleResponse:
        """Manually trigger a schedule."""
        data = await self._http.post(f"/schedules/{schedule_id}/trigger")
        return TriggerScheduleResponse.model_validate(data)

    async def get_history(self, schedule_id: str, limit: int = 10) -> builtins.list[ScheduleRun]:
        """Get schedule execution history."""
        data = await self._http.get(
            f"/schedules/{schedule_id}/history", params={"limit": limit}
        )
        return [ScheduleRun.model_validate(item) for item in data]
