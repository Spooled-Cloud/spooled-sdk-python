"""Tests for realtime JWT caching in the sync and async clients.

The realtime layer used to exchange the API key for a JWT via ``/auth/login`` on
every (re)connect, tripping the login rate limiter under reconnect storms. These
tests pin the fixed behaviour: the exchanged JWT is cached and reused until it is
near expiry, so repeated ``get_jwt_token`` calls only log in once.
"""

from __future__ import annotations

import base64
import json
import time

import httpx
import pytest
import respx

from spooled import AsyncSpooledClient, SpooledClient

API_KEY = "sp_test_xxxxxxxxxxxxxxxxxxxx"
BASE_URL = "http://localhost:8080"
LOGIN_URL = f"{BASE_URL}/api/v1/auth/login"


def _make_jwt(exp: float) -> str:
    """Build an unsigned JWT-shaped token carrying the given ``exp`` claim."""
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps({"exp": int(exp)}).encode()).rstrip(b"=").decode()
    return f"{header}.{body}.sig"


def _login_response(token: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "access_token": token,
            "refresh_token": "refresh_xyz",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_expires_in": 86400,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Sync client
# ─────────────────────────────────────────────────────────────────────────────


class TestSyncJwtCache:
    """JWT caching on the synchronous client."""

    @respx.mock
    def test_caches_jwt_within_lifetime(self) -> None:
        """Two calls within the token lifetime perform exactly one login."""
        token = _make_jwt(time.time() + 3600)
        route = respx.post(LOGIN_URL).mock(return_value=_login_response(token))

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            first = client.get_jwt_token()
            second = client.get_jwt_token()

        assert route.call_count == 1
        assert first == second == token

    @respx.mock
    def test_relogins_when_cached_token_near_expiry(self) -> None:
        """A cached token inside the expiry leeway triggers a re-login."""
        token = _make_jwt(time.time() + 10)  # inside the 60s refresh leeway
        route = respx.post(LOGIN_URL).mock(return_value=_login_response(token))

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            client.get_jwt_token()
            client.get_jwt_token()

        assert route.call_count == 2

    @respx.mock
    def test_relogins_when_cached_token_expired(self) -> None:
        """A cached token that already expired triggers a re-login."""
        token = _make_jwt(time.time() - 100)
        route = respx.post(LOGIN_URL).mock(return_value=_login_response(token))

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            client.get_jwt_token()
            client.get_jwt_token()

        assert route.call_count == 2

    @respx.mock
    def test_force_refresh_bypasses_cache(self) -> None:
        """force_refresh re-logs-in even when the cached token is still valid."""
        token = _make_jwt(time.time() + 3600)
        route = respx.post(LOGIN_URL).mock(return_value=_login_response(token))

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            client.get_jwt_token()
            client.get_jwt_token(force_refresh=True)

        assert route.call_count == 2

    @respx.mock
    def test_static_access_token_used_verbatim(self) -> None:
        """A configured access token is returned as-is with no login call."""
        route = respx.post(LOGIN_URL).mock(
            return_value=_login_response(_make_jwt(time.time() + 3600))
        )

        with SpooledClient(api_key=API_KEY, access_token="static_tok", base_url=BASE_URL) as client:
            assert client.get_jwt_token() == "static_tok"
            assert client.get_jwt_token() == "static_tok"

        assert route.call_count == 0


# ─────────────────────────────────────────────────────────────────────────────
# Async client
# ─────────────────────────────────────────────────────────────────────────────


class TestAsyncJwtCache:
    """JWT caching on the asynchronous client."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_caches_jwt_within_lifetime(self) -> None:
        """Two calls within the token lifetime perform exactly one login."""
        token = _make_jwt(time.time() + 3600)
        route = respx.post(LOGIN_URL).mock(return_value=_login_response(token))

        async with AsyncSpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            first = await client.get_jwt_token()
            second = await client.get_jwt_token()

        assert route.call_count == 1
        assert first == second == token

    @pytest.mark.asyncio
    @respx.mock
    async def test_relogins_when_cached_token_near_expiry(self) -> None:
        """A cached token inside the expiry leeway triggers a re-login."""
        token = _make_jwt(time.time() + 10)  # inside the 60s refresh leeway
        route = respx.post(LOGIN_URL).mock(return_value=_login_response(token))

        async with AsyncSpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            await client.get_jwt_token()
            await client.get_jwt_token()

        assert route.call_count == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_force_refresh_bypasses_cache(self) -> None:
        """force_refresh re-logs-in even when the cached token is still valid."""
        token = _make_jwt(time.time() + 3600)
        route = respx.post(LOGIN_URL).mock(return_value=_login_response(token))

        async with AsyncSpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            await client.get_jwt_token()
            await client.get_jwt_token(force_refresh=True)

        assert route.call_count == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_static_access_token_used_verbatim(self) -> None:
        """A configured access token is returned as-is with no login call."""
        route = respx.post(LOGIN_URL).mock(
            return_value=_login_response(_make_jwt(time.time() + 3600))
        )

        async with AsyncSpooledClient(
            api_key=API_KEY, access_token="static_tok", base_url=BASE_URL
        ) as client:
            assert await client.get_jwt_token() == "static_tok"

        assert route.call_count == 0


# ─────────────────────────────────────────────────────────────────────────────
# Realtime token provider wiring
# ─────────────────────────────────────────────────────────────────────────────


class TestRealtimeTokenProvider:
    """The unified realtime client refreshes its token before each connect."""

    def test_refresh_token_uses_provider(self) -> None:
        from spooled.realtime.unified import (
            SpooledRealtime,
            SpooledRealtimeOptions,
        )

        calls: list[int] = []

        def provider() -> str:
            calls.append(1)
            return "fresh-token"

        realtime = SpooledRealtime(
            SpooledRealtimeOptions(base_url=BASE_URL, token="stale", token_provider=provider)
        )
        realtime._refresh_token()

        assert realtime._options.token == "fresh-token"
        assert len(calls) == 1

    def test_refresh_token_keeps_old_token_on_provider_error(self) -> None:
        from spooled.realtime.unified import (
            SpooledRealtime,
            SpooledRealtimeOptions,
        )

        def provider() -> str:
            raise RuntimeError("login 429")

        realtime = SpooledRealtime(
            SpooledRealtimeOptions(base_url=BASE_URL, token="stale", token_provider=provider)
        )
        realtime._refresh_token()

        # The last known token is preserved; the connect/backoff path retries.
        assert realtime._options.token == "stale"

    def test_refresh_token_noop_without_provider(self) -> None:
        from spooled.realtime.unified import (
            SpooledRealtime,
            SpooledRealtimeOptions,
        )

        realtime = SpooledRealtime(SpooledRealtimeOptions(base_url=BASE_URL, token="stale"))
        realtime._refresh_token()

        assert realtime._options.token == "stale"
