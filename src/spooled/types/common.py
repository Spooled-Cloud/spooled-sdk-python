"""
Common types shared across the SDK.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# JSON types
JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject = dict[str, Any]


class PaginationParams(BaseModel):
    """Common pagination parameters."""

    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    order_by: str | None = None
    order_dir: str | None = Field(default=None, pattern="^(asc|desc)$")

    model_config = {"extra": "forbid"}
