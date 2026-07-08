"""
Asynchronous HTTP client using httpx.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar
from urllib.parse import urlencode

import httpx

from spooled.config import API_BASE_PATH, ResolvedConfig
from spooled.errors import NetworkError, TimeoutError, create_error_from_response
from spooled.utils.casing import convert_query_params, convert_request, convert_response
from spooled.utils.circuit_breaker import CircuitBreaker
from spooled.utils.http import _is_idempotent
from spooled.utils.retry import with_retry_async

T = TypeVar("T")


class AsyncHttpClient:
    """
    Asynchronous HTTP client.

    Handles all HTTP communication with the Spooled API including:
    - URL building and query string encoding
    - JSON request/response handling
    - Timeout support
    - Automatic retry with exponential backoff
    - Circuit breaker protection
    - Case conversion
    """

    def __init__(
        self,
        config: ResolvedConfig,
        circuit_breaker: CircuitBreaker,
    ) -> None:
        self.config = config
        self.circuit_breaker = circuit_breaker
        self._auth_token: str | None = config.access_token or config.api_key
        self._refresh_token_fn: Callable[[], Awaitable[str]] | None = None
        # Serializes token refreshes so concurrent 401s trigger a single refresh.
        self._refresh_lock = asyncio.Lock()
        self._is_refreshing = False
        self._client: httpx.AsyncClient | None = None

    def _build_default_headers(self) -> dict[str, str]:
        """Build default headers for all requests."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": self.config.user_agent,
            **self.config.headers,
        }
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    timeout=self.config.timeout,
                    connect=self.config.connect_timeout,
                ),
                headers=self._build_default_headers(),
            )
        return self._client

    def set_auth_token(self, token: str) -> None:
        """Set the authentication token."""
        self._auth_token = token

    def set_refresh_token_fn(self, fn: Callable[[], Awaitable[str]]) -> None:
        """Set the token refresh function."""
        self._refresh_token_fn = fn

    def _build_url(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        skip_api_prefix: bool = False,
    ) -> str:
        """Build full URL with query parameters."""
        # Ensure path starts with /api/v1 unless explicitly skipped
        if skip_api_prefix or path.startswith("/api/"):
            full_path = path
        else:
            full_path = f"{API_BASE_PATH}{path}"

        url = f"{self.config.base_url}{full_path}"

        if params:
            converted_params = convert_query_params(params)
            if converted_params:
                # urlencode percent-escapes reserved characters so values
                # containing '=', '&', '+', spaces, etc. survive intact.
                query_string = urlencode(converted_params)
                url = f"{url}?{query_string}"

        return url

    def _build_headers(self, custom_headers: dict[str, str] | None = None) -> dict[str, str]:
        """Build request headers."""
        headers: dict[str, str] = {}

        # Add auth token if available
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"

        # Add custom headers
        if custom_headers:
            headers.update(custom_headers)

        return headers

    async def _try_refresh_token(self, token_before: str | None) -> bool:
        """Refresh the auth token once, guarding against concurrent refreshes.

        Returns True if a usable (possibly already-refreshed) token is
        available afterwards, False if refresh failed.
        """
        if self._refresh_token_fn is None:
            return False
        async with self._refresh_lock:
            # Another task may have refreshed while we waited for the lock.
            if self._auth_token != token_before:
                return True
            try:
                self._is_refreshing = True
                await self._refresh_token_fn()
                return True
            except Exception:
                return False
            finally:
                self._is_refreshing = False

    async def _execute_request(
        self,
        method: str,
        url: str,
        *,
        body: Any = None,
        raw_body: bytes | str | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        skip_request_conversion: bool = False,
        skip_response_conversion: bool = False,
        _allow_refresh: bool = True,
    ) -> Any:
        """Execute a single HTTP request (no retry)."""
        client = await self._get_client()
        auth_before = self._auth_token
        request_headers = self._build_headers(headers)

        # Prepare request body
        content: bytes | str | None = None
        json_body: Any = None

        if raw_body is not None:
            content = raw_body
        elif body is not None:
            json_body = convert_request(body) if not skip_request_conversion else body

        if self.config.debug_fn:
            self.config.debug_fn(f"{method} {url}", {"has_body": body is not None})

        try:
            response = await client.request(
                method=method,
                url=url,
                headers=request_headers,
                json=json_body if json_body is not None else None,
                content=content if content is not None else None,
                # Passing timeout=None to httpx disables timeouts entirely; use
                # the client-level default instead so requests can never hang.
                timeout=timeout if timeout is not None else httpx.USE_CLIENT_DEFAULT,
            )
        except httpx.TimeoutException as e:
            raise TimeoutError(
                f"Request timed out after {timeout or self.config.timeout}s",
                timeout_seconds=timeout or self.config.timeout,
            ) from e
        except httpx.RequestError as e:
            raise NetworkError(f"Network request failed: {e}", cause=e) from e

        if self.config.debug_fn:
            self.config.debug_fn(f"Response: {response.status_code}", {"url": url})

        # Handle non-OK responses
        if not response.is_success:
            # On 401, attempt a one-time token refresh and replay the request.
            if (
                response.status_code == 401
                and _allow_refresh
                and self._refresh_token_fn is not None
                and not self._is_refreshing
                and await self._try_refresh_token(auth_before)
            ):
                return await self._execute_request(
                    method,
                    url,
                    body=body,
                    raw_body=raw_body,
                    headers=headers,
                    timeout=timeout,
                    skip_request_conversion=skip_request_conversion,
                    skip_response_conversion=skip_response_conversion,
                    _allow_refresh=False,
                )

            try:
                error_body = response.json()
            except Exception:
                error_body = None

            request_id = response.headers.get("X-Request-Id")
            raise create_error_from_response(
                response.status_code, error_body, request_id, response.headers
            )

        # Parse response body
        if response.status_code == 204:
            return None

        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            data = response.json()
            if not skip_response_conversion:
                data = convert_response(data)
            return data

        # Non-JSON response (e.g., Prometheus metrics)
        return response.text

    async def request(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        raw_body: bytes | str | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        skip_api_prefix: bool = False,
        skip_request_conversion: bool = False,
        skip_response_conversion: bool = False,
        skip_retry: bool = False,
    ) -> Any:
        """Make an HTTP request with retry and circuit breaker."""
        url = self._build_url(path, params, skip_api_prefix)

        async def execute() -> Any:
            return self.circuit_breaker.execute(
                lambda: None  # Placeholder - we need sync wrapper
            )

        # For async, we handle circuit breaker differently
        async def execute_with_cb() -> Any:
            if not self.circuit_breaker.is_allowed():
                from spooled.errors import CircuitBreakerOpenError

                raise CircuitBreakerOpenError(
                    f"Circuit breaker is open. Will retry after {self.circuit_breaker.config.timeout}s"
                )
            try:
                result = await self._execute_request(
                    method,
                    url,
                    body=body,
                    raw_body=raw_body,
                    headers=headers,
                    timeout=timeout,
                    skip_request_conversion=skip_request_conversion,
                    skip_response_conversion=skip_response_conversion,
                )
                self.circuit_breaker.record_success()
                return result
            except Exception as e:
                self.circuit_breaker.record_failure(e)
                raise

        if skip_retry:
            return await execute_with_cb()

        def on_retry(attempt: int, error: Exception, delay: float) -> None:
            if self.config.debug_fn:
                self.config.debug_fn(
                    f"Retry attempt {attempt} after {delay:.0f}ms",
                    {"error": str(error)},
                )

        return await with_retry_async(
            execute_with_cb,
            self.config.retry,
            on_retry,
            idempotent=_is_idempotent(method, body, headers),
        )

    async def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        skip_api_prefix: bool = False,
        skip_response_conversion: bool = False,
        skip_retry: bool = False,
    ) -> Any:
        """Make a GET request."""
        return await self.request(
            "GET",
            path,
            params=params,
            headers=headers,
            timeout=timeout,
            skip_api_prefix=skip_api_prefix,
            skip_response_conversion=skip_response_conversion,
            skip_retry=skip_retry,
        )

    async def post(
        self,
        path: str,
        body: Any = None,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        skip_api_prefix: bool = False,
        skip_request_conversion: bool = False,
        skip_response_conversion: bool = False,
        skip_retry: bool = False,
    ) -> Any:
        """Make a POST request."""
        return await self.request(
            "POST",
            path,
            body=body,
            params=params,
            headers=headers,
            timeout=timeout,
            skip_api_prefix=skip_api_prefix,
            skip_request_conversion=skip_request_conversion,
            skip_response_conversion=skip_response_conversion,
            skip_retry=skip_retry,
        )

    async def put(
        self,
        path: str,
        body: Any = None,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        skip_api_prefix: bool = False,
        skip_request_conversion: bool = False,
        skip_response_conversion: bool = False,
        skip_retry: bool = False,
    ) -> Any:
        """Make a PUT request."""
        return await self.request(
            "PUT",
            path,
            body=body,
            params=params,
            headers=headers,
            timeout=timeout,
            skip_api_prefix=skip_api_prefix,
            skip_request_conversion=skip_request_conversion,
            skip_response_conversion=skip_response_conversion,
            skip_retry=skip_retry,
        )

    async def patch(
        self,
        path: str,
        body: Any = None,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        skip_api_prefix: bool = False,
        skip_request_conversion: bool = False,
        skip_response_conversion: bool = False,
        skip_retry: bool = False,
    ) -> Any:
        """Make a PATCH request."""
        return await self.request(
            "PATCH",
            path,
            body=body,
            params=params,
            headers=headers,
            timeout=timeout,
            skip_api_prefix=skip_api_prefix,
            skip_request_conversion=skip_request_conversion,
            skip_response_conversion=skip_response_conversion,
            skip_retry=skip_retry,
        )

    async def delete(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        skip_api_prefix: bool = False,
        skip_response_conversion: bool = False,
        skip_retry: bool = False,
    ) -> Any:
        """Make a DELETE request."""
        return await self.request(
            "DELETE",
            path,
            params=params,
            headers=headers,
            timeout=timeout,
            skip_api_prefix=skip_api_prefix,
            skip_response_conversion=skip_response_conversion,
            skip_retry=skip_retry,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> AsyncHttpClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()


def create_async_http_client(
    config: ResolvedConfig, circuit_breaker: CircuitBreaker
) -> AsyncHttpClient:
    """Create an async HTTP client instance."""
    return AsyncHttpClient(config, circuit_breaker)
