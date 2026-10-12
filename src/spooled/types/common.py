"""
Common types shared across the SDK.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

# JSON types
JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject = dict[str, Any]

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Common pagination parameters."""

    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    order_by: str | None = None
    order_dir: str | None = Field(default=None, pattern="^(asc|desc)$")

    model_config = {"extra": "forbid"}


class Page(list[T], Generic[T]):
    """One page of a list response: a plain ``list`` plus the server's paging hint.

    ``has_more`` comes from the ``X-Has-More`` response header: ``True`` when
    another page follows (fetch it with ``offset + limit``), ``False`` when this
    is the last page, ``None`` when the server did not send the header (older
    servers, or endpoints that do not page this way). Everything else behaves
    exactly like the list it is, so code that treats the result as a list keeps
    working.
    """

    has_more: bool | None

    def __init__(self, items: Iterable[T] = (), has_more: bool | None = None) -> None:
        super().__init__(items)
        self.has_more = has_more


def _header(headers: Mapping[str, str] | None, name: str) -> str | None:
    """Case-insensitive header lookup that works on plain dicts too."""
    if not headers:
        return None
    value = headers.get(name)
    if value is not None:
        return value
    lowered = name.lower()
    for key, val in headers.items():
        if key.lower() == lowered:
            return val
    return None


def parse_has_more(headers: Mapping[str, str] | None) -> bool | None:
    """Read ``X-Has-More`` (``true``/``false``); ``None`` when absent or unreadable."""
    value = _header(headers, "X-Has-More")
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None


def _int_header(headers: Mapping[str, str] | None, name: str) -> int | None:
    value = _header(headers, name)
    if value is None:
        return None
    try:
        return int(value.strip())
    except (TypeError, ValueError):
        return None


class RateLimitInfo(BaseModel):
    """The rate-limit state the API reported on its most recent response.

    The API sends these headers on every response, not only on 429:

    * ``X-RateLimit-Limit`` - requests allowed in the current window
    * ``X-RateLimit-Remaining`` - requests left in the current window
    * ``X-RateLimit-Reset`` - when the window resets, as Unix seconds
      (``reset`` here is that instant as an aware UTC ``datetime``;
      ``reset_epoch`` keeps the raw value)
    * ``X-RateLimit-Scope`` - what the limit is counted against
      (for example ``organization``)

    Read it from ``client.rate_limit``. A 429 additionally carries
    ``Retry-After`` and raises :class:`~spooled.errors.RateLimitError`.
    """

    limit: int | None = None
    remaining: int | None = None
    reset_epoch: int | None = None
    reset: datetime | None = None
    scope: str | None = None

    @classmethod
    def from_headers(cls, headers: Mapping[str, str] | None) -> RateLimitInfo | None:
        """Parse the ``X-RateLimit-*`` headers; ``None`` when none are present."""
        limit = _int_header(headers, "X-RateLimit-Limit")
        remaining = _int_header(headers, "X-RateLimit-Remaining")
        reset_epoch = _int_header(headers, "X-RateLimit-Reset")
        scope = _header(headers, "X-RateLimit-Scope")
        if limit is None and remaining is None and reset_epoch is None and scope is None:
            return None
        reset: datetime | None = None
        if reset_epoch is not None:
            try:
                reset = datetime.fromtimestamp(reset_epoch, tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                reset = None
        return cls(
            limit=limit,
            remaining=remaining,
            reset_epoch=reset_epoch,
            reset=reset,
            scope=scope.strip() if scope else None,
        )


def to_rfc3339(value: datetime) -> str:
    """Format a datetime for a query filter; a naive value is taken as UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
