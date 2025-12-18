"""
Synchronous HTTP client using httpx.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

import httpx

from spooled.config import API_BASE_PATH, ResolvedConfig
from spooled.errors import NetworkError, TimeoutError, create_error_from_response
from spooled.utils.casing import convert_query_params, convert_request, convert_response
from spooled.utils.circuit_breaker import CircuitBreaker
from spooled.utils.retry import with_retry

T = TypeVar("T")


class HttpClient:
    """
    Synchronous HTTP client.

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
        self._refresh_token_fn: Callable[[], str] | None = None

        # Create httpx client
        self._client = httpx.Client(
            timeout=httpx.Timeout(
                timeout=config.timeout,
                connect=config.connect_timeout,
            ),
            headers=self._build_default_headers(),
        )

    def _build_default_headers(self) -> dict[str, str]:
        """Build default headers for all requests."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": self.config.user_agent,
            **self.config.headers,
        }
        return headers

    def set_auth_token(self, token: str) -> None:
        """Set the authentication token."""
        self._auth_token = token

    def set_refresh_token_fn(self, fn: Callable[[], str]) -> None:
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
                query_string = "&".join(f"{k}={v}" for k, v in converted_params.items())
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

    def _execute_request(
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
    ) -> Any:
        """Execute a single HTTP request (no retry)."""
        request_headers = self._build_headers(headers)

        # Prepare request body
        content: bytes | str | None = None
        json_body: Any = None

        if raw_body is not None:
            content = raw_body
        elif body is not None:
            if not skip_request_conversion:
                body = convert_request(body)
            json_body = body

        if self.config.debug_fn:
            self.config.debug_fn(f"{method} {url}", {"has_body": body is not None})

        try:
            response = self._client.request(
                method=method,
                url=url,
                headers=request_headers,
                json=json_body if json_body is not None else None,
                content=content if content is not None else None,
                timeout=timeout,
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
            try:
                error_body = response.json()
            except Exception:
                error_body = None

            request_id = response.headers.get("X-Request-Id")
            raise create_error_from_response(response.status_code, error_body, request_id)

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

    def request(
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

        def execute() -> Any:
            return self.circuit_breaker.execute(
                lambda: self._execute_request(
                    method,
                    url,
                    body=body,
                    raw_body=raw_body,
                    headers=headers,
                    timeout=timeout,
                    skip_request_conversion=skip_request_conversion,
                    skip_response_conversion=skip_response_conversion,
                )
            )

        if skip_retry:
            return execute()

        def on_retry(attempt: int, error: Exception, delay: float) -> None:
            if self.config.debug_fn:
                self.config.debug_fn(
                    f"Retry attempt {attempt} after {delay:.0f}ms",
                    {"error": str(error)},
                )

        return with_retry(execute, self.config.retry, on_retry)

    def get(
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
        return self.request(
            "GET",
            path,
            params=params,
            headers=headers,
            timeout=timeout,
            skip_api_prefix=skip_api_prefix,
            skip_response_conversion=skip_response_conversion,
            skip_retry=skip_retry,
        )

    def post(
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
        return self.request(
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

    def put(
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
        return self.request(
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

    def patch(
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
        return self.request(
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

    def delete(
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
        return self.request(
            "DELETE",
            path,
            params=params,
            headers=headers,
            timeout=timeout,
            skip_api_prefix=skip_api_prefix,
            skip_response_conversion=skip_response_conversion,
            skip_retry=skip_retry,
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


def create_http_client(config: ResolvedConfig, circuit_breaker: CircuitBreaker) -> HttpClient:
    """Create an HTTP client instance."""
    return HttpClient(config, circuit_breaker)
