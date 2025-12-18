"""
Queues resource for Spooled SDK.
"""

from __future__ import annotations

from typing import Any

from spooled.resources.base import AsyncBaseResource, BaseResource
from spooled.types.queues import (
    PauseQueueResponse,
    QueueConfig,
    QueueConfigSummary,
    QueueStats,
    ResumeQueueResponse,
    UpdateQueueConfigParams,
)


class QueuesResource(BaseResource):
    """Queues resource (sync)."""

    def list(self) -> list[QueueConfigSummary]:
        """List all queues."""
        data = self._http.get("/queues")
        return [QueueConfigSummary.model_validate(item) for item in data]

    def get(self, name: str) -> QueueConfig:
        """Get queue configuration by name."""
        data = self._http.get(f"/queues/{name}")
        return QueueConfig.model_validate(data)

    def update_config(
        self, name: str, config: UpdateQueueConfigParams | dict[str, Any]
    ) -> QueueConfig:
        """Update queue configuration."""
        if isinstance(config, dict):
            config = UpdateQueueConfigParams.model_validate(config)
        data = self._http.put(f"/queues/{name}/config", config.model_dump(exclude_none=True))
        return QueueConfig.model_validate(data)

    def get_stats(self, name: str) -> QueueStats:
        """Get queue statistics."""
        data = self._http.get(f"/queues/{name}/stats")
        return QueueStats.model_validate(data)

    def pause(self, name: str, reason: str | None = None) -> PauseQueueResponse:
        """Pause a queue."""
        body = {"reason": reason} if reason else None
        data = self._http.post(f"/queues/{name}/pause", body)
        return PauseQueueResponse.model_validate(data)

    def resume(self, name: str) -> ResumeQueueResponse:
        """Resume a paused queue."""
        data = self._http.post(f"/queues/{name}/resume")
        return ResumeQueueResponse.model_validate(data)

    def delete(self, name: str) -> None:
        """Delete a queue."""
        self._http.delete(f"/queues/{name}")


class AsyncQueuesResource(AsyncBaseResource):
    """Queues resource (async)."""

    async def list(self) -> list[QueueConfigSummary]:
        """List all queues."""
        data = await self._http.get("/queues")
        return [QueueConfigSummary.model_validate(item) for item in data]

    async def get(self, name: str) -> QueueConfig:
        """Get queue configuration by name."""
        data = await self._http.get(f"/queues/{name}")
        return QueueConfig.model_validate(data)

    async def update_config(
        self, name: str, config: UpdateQueueConfigParams | dict[str, Any]
    ) -> QueueConfig:
        """Update queue configuration."""
        if isinstance(config, dict):
            config = UpdateQueueConfigParams.model_validate(config)
        data = await self._http.put(
            f"/queues/{name}/config", config.model_dump(exclude_none=True)
        )
        return QueueConfig.model_validate(data)

    async def get_stats(self, name: str) -> QueueStats:
        """Get queue statistics."""
        data = await self._http.get(f"/queues/{name}/stats")
        return QueueStats.model_validate(data)

    async def pause(self, name: str, reason: str | None = None) -> PauseQueueResponse:
        """Pause a queue."""
        body = {"reason": reason} if reason else None
        data = await self._http.post(f"/queues/{name}/pause", body)
        return PauseQueueResponse.model_validate(data)

    async def resume(self, name: str) -> ResumeQueueResponse:
        """Resume a paused queue."""
        data = await self._http.post(f"/queues/{name}/resume")
        return ResumeQueueResponse.model_validate(data)

    async def delete(self, name: str) -> None:
        """Delete a queue."""
        await self._http.delete(f"/queues/{name}")
