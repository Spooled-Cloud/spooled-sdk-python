"""Client-level contracts: REST auth vs realtime JWT, gRPC address, with_options, small API fixes.

SDKNP-02: ``get_jwt_token()`` (used by ``realtime()``) replaced the REST bearer.
SDKNP-11: ``client.grpc`` ignored ``grpc_address``.
SDKNP-12: ``with_options()`` dropped headers, retry, breaker, user agent, timeouts, URLs.
SDKNP-08: ``queues.pause(name)`` without a reason sent an empty JSON body (400).
SDKNP-13: ``dlq.purge({})`` purged without confirmation.
SDKNP-18: workflow jobs carried an invented ``key: ""``.
Brief item 8: ``clear_webhook_token`` can never succeed.
"""

from __future__ import annotations

import asyncio
import base64
import json
import threading
import time
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
import respx
from pydantic import ValidationError as PydanticValidationError

from spooled import AsyncSpooledClient, SpooledClient
from spooled.config import CircuitBreakerConfig, RetryConfig
from spooled.errors import SpooledError, UnsupportedOperationError
from spooled.types.jobs import PurgeDlqParams
from spooled.types.schedules import CreateScheduleParams
from spooled.types.workflows import WorkflowJobStatus

BASE_URL = "http://localhost:8080"
API = f"{BASE_URL}/api/v1"
API_KEY = "sp_test_xxxxxxxxxxxxxxxxxxxx"


def _jwt(exp: float) -> str:
    def b64(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return f"{b64(b'{}')}.{b64(json.dumps({'exp': int(exp)}).encode())}.sig"


def _login(token: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "access_token": token,
            "refresh_token": "refresh-token-1",
            "token_type": "Bearer",
            "expires_in": 86400,
            "refresh_expires_in": 604800,
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# SDKNP-02: the realtime JWT never becomes the REST bearer
# ─────────────────────────────────────────────────────────────────────────────


class TestRealtimeTokenDoesNotReplaceRestAuth:
    @respx.mock
    def test_get_jwt_token_keeps_the_api_key_as_rest_bearer(self) -> None:
        token = _jwt(time.time() + 86400)
        respx.post(f"{API}/auth/login").mock(return_value=_login(token))
        jobs = respx.get(f"{API}/jobs").mock(return_value=httpx.Response(200, json=[]))

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            assert client.get_jwt_token() == token
            client.jobs.list()

        assert jobs.calls.last.request.headers["Authorization"] == f"Bearer {API_KEY}"

    @respx.mock
    def test_realtime_factory_keeps_the_api_key_as_rest_bearer(self) -> None:
        token = _jwt(time.time() + 86400)
        respx.post(f"{API}/auth/login").mock(return_value=_login(token))
        jobs = respx.get(f"{API}/jobs").mock(return_value=httpx.Response(200, json=[]))

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            realtime = client.realtime(type="sse")
            assert realtime._options.token == token
            assert realtime._options.token_provider is not None
            client.jobs.list()

        assert jobs.calls.last.request.headers["Authorization"] == f"Bearer {API_KEY}"

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_get_jwt_token_keeps_the_api_key_as_rest_bearer(self) -> None:
        token = _jwt(time.time() + 86400)
        respx.post(f"{API}/auth/login").mock(return_value=_login(token))
        jobs = respx.get(f"{API}/jobs").mock(return_value=httpx.Response(200, json=[]))

        async with AsyncSpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            assert await client.get_jwt_token() == token
            await client.jobs.list()

        assert jobs.calls.last.request.headers["Authorization"] == f"Bearer {API_KEY}"

    @respx.mock
    def test_realtime_uses_its_own_refreshed_token_not_the_rest_one(self) -> None:
        # First JWT is about to expire, so the provider must mint a new one.
        old, new = _jwt(time.time() + 30), _jwt(time.time() + 86400)
        login = respx.post(f"{API}/auth/login").mock(side_effect=[_login(old), _login(new)])
        respx.get(f"{API}/jobs").mock(return_value=httpx.Response(200, json=[]))

        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            realtime = client.realtime(type="sse")
            assert realtime._options.token == old
            realtime._refresh_token()  # what every (re)connect does
            assert realtime._options.token == new
            client.jobs.list()

        assert login.call_count == 2
        assert respx.calls.last.request.headers["Authorization"] == f"Bearer {API_KEY}"

    @respx.mock
    def test_static_access_token_is_renewed_before_it_expires(self) -> None:
        expiring, renewed = _jwt(time.time() + 20), _jwt(time.time() + 3600)
        refresh = respx.post(f"{API}/auth/refresh").mock(
            return_value=httpx.Response(
                200,
                json={"access_token": renewed, "token_type": "Bearer", "expires_in": 3600},
            )
        )
        with SpooledClient(
            access_token=expiring, refresh_token="refresh-token-1", base_url=BASE_URL
        ) as client:
            assert client.get_jwt_token() == renewed
            assert client.get_jwt_token() == renewed  # now valid: no second refresh
        assert refresh.call_count == 1

    @respx.mock
    def test_static_access_token_without_refresh_token_is_returned_as_is(self) -> None:
        expiring = _jwt(time.time() + 20)
        with SpooledClient(access_token=expiring, base_url=BASE_URL) as client:
            assert client.get_jwt_token() == expiring

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_realtime_provider_refreshes_from_a_background_thread(self) -> None:
        old, new = _jwt(time.time() + 30), _jwt(time.time() + 86400)
        respx.post(f"{API}/auth/login").mock(side_effect=[_login(old), _login(new)])

        async with AsyncSpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            realtime = await client.realtime(type="sse")
            provider = realtime._options.token_provider
            assert provider is not None

            # On the event loop itself the provider must not block on its own loop.
            assert provider() == old

            # A reconnect runs on a thread: it asks the loop for a fresh token.
            found: list[str] = []
            thread = threading.Thread(target=lambda: found.append(provider()))
            thread.start()
            while thread.is_alive():
                await asyncio.sleep(0.01)
            thread.join()
            assert found == [new]


# ─────────────────────────────────────────────────────────────────────────────
# SDKNP-11: gRPC address
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def channels(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Replace gRPC channel creation so no socket or DNS lookup is ever attempted."""
    import spooled.grpc.client as grpc_client

    created: list[tuple[str, str]] = []

    def secure(address: str, *_args: Any, **_kwargs: Any) -> MagicMock:
        created.append(("tls", address))
        return MagicMock()

    def insecure(address: str, *_args: Any, **_kwargs: Any) -> MagicMock:
        created.append(("plaintext", address))
        return MagicMock()

    monkeypatch.setattr(grpc_client.grpc, "secure_channel", secure)
    monkeypatch.setattr(grpc_client.grpc, "insecure_channel", insecure)
    return created


class TestGrpcAddress:
    def test_defaults_to_the_documented_cloud_address_with_tls(
        self, channels: list[tuple[str, str]]
    ) -> None:
        with SpooledClient(api_key=API_KEY) as client:
            assert client.grpc._address == "grpc.spooled.cloud:443"
        assert channels == [("tls", "grpc.spooled.cloud:443")]

    def test_honours_grpc_address(self, channels: list[tuple[str, str]]) -> None:
        with SpooledClient(api_key=API_KEY, grpc_address="my-grpc.internal:9000") as client:
            assert client.grpc._address == "my-grpc.internal:9000"
        assert channels == [("tls", "my-grpc.internal:9000")]

    def test_is_independent_of_the_rest_base_url(self, channels: list[tuple[str, str]]) -> None:
        with SpooledClient(api_key=API_KEY, base_url="https://api.example.com") as client:
            assert client.grpc._address == "grpc.spooled.cloud:443"
        assert channels == [("tls", "grpc.spooled.cloud:443")]

    @pytest.mark.parametrize("address", ["localhost:50051", "127.0.0.1:50051", "[::1]:50051"])
    def test_local_addresses_default_to_plaintext(
        self, channels: list[tuple[str, str]], address: str
    ) -> None:
        with SpooledClient(api_key=API_KEY, grpc_address=address) as client:
            assert client.grpc._address == address
        assert channels == [("plaintext", address)]

    @pytest.mark.asyncio
    async def test_async_client_honours_grpc_address(self, channels: list[tuple[str, str]]) -> None:
        async with AsyncSpooledClient(api_key=API_KEY, grpc_address="my-grpc.internal:9000") as c:
            assert c.grpc._address == "my-grpc.internal:9000"
        assert channels == [("tls", "my-grpc.internal:9000")]


# ─────────────────────────────────────────────────────────────────────────────
# SDKNP-12: with_options keeps the whole configuration
# ─────────────────────────────────────────────────────────────────────────────


class TestWithOptions:
    def _base(self) -> SpooledClient:
        return SpooledClient(
            api_key=API_KEY,
            base_url=BASE_URL,
            headers={"X-Tenant": "acme"},
            retry=RetryConfig(max_retries=0),
            circuit_breaker=CircuitBreakerConfig(enabled=False),
            user_agent="my-app/9.9",
            connect_timeout=3.0,
            grpc_address="my-grpc.internal:9000",
            ws_url="wss://realtime.example.com",
            auto_refresh_token=False,
        )

    def test_overriding_one_option_keeps_everything_else(self) -> None:
        client = self._base()
        derived = client.with_options(timeout=5)
        config = derived.get_config()

        assert config.timeout == 5
        assert config.headers == {"X-Tenant": "acme"}
        assert config.retry.max_retries == 0
        assert config.circuit_breaker.enabled is False
        assert config.user_agent == "my-app/9.9"
        assert config.connect_timeout == 3.0
        assert config.grpc_address == "my-grpc.internal:9000"
        assert config.ws_url == "wss://realtime.example.com"
        assert config.auto_refresh_token is False
        assert config.api_key == API_KEY
        assert config.base_url == BASE_URL
        client.close()
        derived.close()

    def test_headers_reach_the_wire(self) -> None:
        client = self._base()
        derived = client.with_options(timeout=5)
        with respx.mock:
            route = respx.get(f"{API}/jobs").mock(return_value=httpx.Response(200, json=[]))
            derived.jobs.list()
        sent = route.calls.last.request.headers
        assert sent["X-Tenant"] == "acme"
        assert sent["User-Agent"] == "my-app/9.9"
        client.close()
        derived.close()

    def test_kwargs_override_nested_settings(self) -> None:
        client = self._base()
        derived = client.with_options(
            headers={"X-Other": "1"}, retry={"max_retries": 7}, grpc_address="other:1"
        )
        config = derived.get_config()
        assert config.headers == {"X-Other": "1"}
        assert config.retry.max_retries == 7
        assert config.grpc_address == "other:1"
        client.close()
        derived.close()

    def test_derived_ws_url_follows_a_new_base_url(self) -> None:
        client = SpooledClient(api_key=API_KEY, base_url="https://api.example.com")
        assert client.get_config().ws_url == "wss://api.example.com"
        derived = client.with_options(base_url="https://api.other.example")
        assert derived.get_config().ws_url == "wss://api.other.example"
        client.close()
        derived.close()

    def test_debug_flag_is_kept_and_overridable(self) -> None:
        client = SpooledClient(api_key=API_KEY, base_url=BASE_URL, debug=True)
        assert client.with_options(timeout=5).get_config().debug_fn is not None
        assert client.with_options(debug=False).get_config().debug_fn is None
        client.close()

    @pytest.mark.asyncio
    async def test_async_with_options_keeps_everything_else(self) -> None:
        client = AsyncSpooledClient(
            api_key=API_KEY,
            base_url=BASE_URL,
            headers={"X-Tenant": "acme"},
            retry=RetryConfig(max_retries=0),
            grpc_address="my-grpc.internal:9000",
        )
        derived = client.with_options(timeout=5)
        config = derived.get_config()
        assert config.timeout == 5
        assert config.headers == {"X-Tenant": "acme"}
        assert config.retry.max_retries == 0
        assert config.grpc_address == "my-grpc.internal:9000"
        await client.close()
        await derived.close()


# ─────────────────────────────────────────────────────────────────────────────
# SDKNP-08: pause body
# ─────────────────────────────────────────────────────────────────────────────


class TestPauseBody:
    @respx.mock
    def test_pause_without_reason_sends_an_empty_json_object(self) -> None:
        route = respx.post(f"{API}/queues/emails/pause").mock(
            return_value=httpx.Response(
                200,
                json={"queue_name": "emails", "paused": True, "paused_at": "2026-10-10T00:00:00Z"},
            )
        )
        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            client.queues.pause("emails")
        request = route.calls.last.request
        assert request.headers["Content-Type"] == "application/json"
        # Content-Type: application/json + an empty body is a 400 on the server.
        assert json.loads(request.content) == {}

    @respx.mock
    def test_pause_with_reason_sends_it(self) -> None:
        route = respx.post(f"{API}/queues/emails/pause").mock(
            return_value=httpx.Response(
                200,
                json={"queue_name": "emails", "paused": True, "paused_at": "2026-10-10T00:00:00Z"},
            )
        )
        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            client.queues.pause("emails", "maintenance")
        assert json.loads(route.calls.last.request.content) == {"reason": "maintenance"}

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_pause_without_reason_sends_an_empty_json_object(self) -> None:
        route = respx.post(f"{API}/queues/emails/pause").mock(
            return_value=httpx.Response(
                200,
                json={"queue_name": "emails", "paused": True, "paused_at": "2026-10-10T00:00:00Z"},
            )
        )
        async with AsyncSpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            await client.queues.pause("emails")
        assert json.loads(route.calls.last.request.content) == {}


# ─────────────────────────────────────────────────────────────────────────────
# SDKNP-13: DLQ purge needs an explicit confirm
# ─────────────────────────────────────────────────────────────────────────────


class TestDlqPurgeConfirmation:
    @respx.mock
    def test_purge_with_empty_params_raises_and_sends_nothing(self) -> None:
        route = respx.post(f"{API}/jobs/dlq/purge").mock(
            return_value=httpx.Response(200, json={"purged_count": 99})
        )
        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            with pytest.raises(PydanticValidationError):
                client.jobs.dlq.purge({})
            with pytest.raises(PydanticValidationError):
                client.jobs.dlq.purge({"queue_name": "emails"})
        assert route.call_count == 0

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_purge_with_empty_params_raises(self) -> None:
        route = respx.post(f"{API}/jobs/dlq/purge").mock(
            return_value=httpx.Response(200, json={"purged_count": 99})
        )
        async with AsyncSpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            with pytest.raises(PydanticValidationError):
                await client.jobs.dlq.purge({})
        assert route.call_count == 0

    def test_confirm_false_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="confirm=True"):
            PurgeDlqParams(confirm=False).to_payload()

    @respx.mock
    def test_explicit_confirm_purges(self) -> None:
        route = respx.post(f"{API}/jobs/dlq/purge").mock(
            return_value=httpx.Response(200, json={"purged_count": 2})
        )
        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = client.jobs.dlq.purge({"queue_name": "emails", "confirm": True})
        assert result.purged_count == 2
        assert json.loads(route.calls.last.request.content) == {
            "confirm": True,
            "queue_name": "emails",
        }


# ─────────────────────────────────────────────────────────────────────────────
# SDKNP-18: workflow job key
# ─────────────────────────────────────────────────────────────────────────────


class TestWorkflowJobKey:
    DETAIL: dict[str, Any] = {
        "id": "wf_1",
        "name": "pipeline",
        "status": "running",
        "jobs": [
            {
                "id": "job_1",
                "queue": "q",
                "status": "completed",
                "payload": {},
                "priority": 0,
                "attempt": 0,
                "max_retries": 3,
                "created_at": "2026-10-10T00:00:00Z",
            }
        ],
        "dependencies": [],
    }

    @respx.mock
    def test_key_is_unknown_not_an_empty_string(self) -> None:
        respx.get(f"{API}/workflows/wf_1").mock(return_value=httpx.Response(200, json=self.DETAIL))
        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            jobs = client.workflows.jobs.list("wf_1")
            statuses = client.workflows.jobs.get_status("wf_1")
        assert jobs[0].key is None
        assert statuses[0].key is None
        assert statuses[0].job_id == "job_1"

    def test_a_key_sent_by_the_server_is_kept(self) -> None:
        from spooled.resources.workflows import jobs_from_workflow_detail

        detail = {**self.DETAIL, "jobs": [{**self.DETAIL["jobs"][0], "key": "extract"}]}
        assert jobs_from_workflow_detail(detail)[0].key == "extract"

    def test_status_model_defaults_to_no_key(self) -> None:
        assert WorkflowJobStatus(job_id="j", status="pending").key is None


# ─────────────────────────────────────────────────────────────────────────────
# Brief item 8: calls to a route that cannot succeed
# ─────────────────────────────────────────────────────────────────────────────


class TestClearWebhookTokenUnsupported:
    @respx.mock
    def test_raises_a_clear_error_without_a_network_call(self) -> None:
        route = respx.post(f"{API}/organizations/webhook-token/clear").mock(
            return_value=httpx.Response(422)
        )
        with SpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            with pytest.raises(UnsupportedOperationError, match="regenerate_webhook_token"):
                client.organizations.clear_webhook_token()
        assert route.call_count == 0
        assert issubclass(UnsupportedOperationError, SpooledError)

    @respx.mock
    @pytest.mark.asyncio
    async def test_async_raises_without_a_network_call(self) -> None:
        route = respx.post(f"{API}/organizations/webhook-token/clear").mock(
            return_value=httpx.Response(422)
        )
        async with AsyncSpooledClient(api_key=API_KEY, base_url=BASE_URL) as client:
            with pytest.raises(UnsupportedOperationError):
                await client.organizations.clear_webhook_token()
        assert route.call_count == 0


# ─────────────────────────────────────────────────────────────────────────────
# SDKNP-25 / SDKNP-28 / SDKNP-24 small parity fixes
# ─────────────────────────────────────────────────────────────────────────────


class TestSmallParityFixes:
    def test_schedule_names_up_to_the_backend_limit_are_accepted(self) -> None:
        params = CreateScheduleParams(
            name="n" * 255,
            cron_expression="0 * * * *",
            queue_name="q" * 255,
            payload_template={},
        )
        assert len(params.name) == 255

    def test_admin_only_client_can_be_constructed(self) -> None:
        with SpooledClient(admin_key="admin-secret-key", base_url=BASE_URL) as client:
            assert client.get_config().api_key is None

    def test_client_without_any_credential_is_still_rejected(self) -> None:
        with pytest.raises(ValueError, match="Either api_key or access_token"):
            SpooledClient(base_url=BASE_URL)
