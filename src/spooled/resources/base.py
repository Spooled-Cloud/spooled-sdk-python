"""
Base resource classes for Spooled SDK.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spooled.utils.async_http import AsyncHttpClient
    from spooled.utils.http import HttpClient


class BaseResource:
    """Base class for synchronous API resources."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http


class AsyncBaseResource:
    """Base class for asynchronous API resources."""

    def __init__(self, http: AsyncHttpClient) -> None:
        self._http = http
