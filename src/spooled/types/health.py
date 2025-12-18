"""
Health-related types.
"""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response."""

    status: str  # 'healthy' | 'unhealthy'
    version: str | None = None
    database: bool | None = None
    cache: bool | None = None
    uptime_seconds: int | None = None
