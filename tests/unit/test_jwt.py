"""Unit tests for the JWT expiry helpers used by realtime token caching."""

from __future__ import annotations

import base64
import json

from spooled.utils.jwt import (
    EXPIRY_LEEWAY_SECONDS,
    decode_jwt_exp,
    jwt_needs_refresh,
)


def _make_jwt(payload: dict[str, object]) -> str:
    """Build an unsigned JWT-shaped string with the given payload claims."""
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    body = (
        base64.urlsafe_b64encode(json.dumps(payload).encode())
        .rstrip(b"=")
        .decode()
    )
    return f"{header}.{body}.sig"


class TestDecodeJwtExp:
    """Tests for decode_jwt_exp."""

    def test_decodes_numeric_exp(self) -> None:
        token = _make_jwt({"exp": 1_900_000_000, "sub": "org_1"})
        assert decode_jwt_exp(token) == 1_900_000_000.0

    def test_decodes_exp_without_padding(self) -> None:
        # A payload whose base64 length is not a multiple of 4 exercises the
        # padding-restoration path.
        token = _make_jwt({"exp": 1})
        assert decode_jwt_exp(token) == 1.0

    def test_returns_none_when_not_three_parts(self) -> None:
        assert decode_jwt_exp("not-a-jwt") is None
        assert decode_jwt_exp("only.two") is None

    def test_returns_none_when_exp_missing(self) -> None:
        token = _make_jwt({"sub": "org_1"})
        assert decode_jwt_exp(token) is None

    def test_returns_none_when_exp_not_numeric(self) -> None:
        token = _make_jwt({"exp": "soon"})
        assert decode_jwt_exp(token) is None

    def test_returns_none_when_exp_is_bool(self) -> None:
        # bool is a subclass of int; it must not be read as an expiry.
        token = _make_jwt({"exp": True})
        assert decode_jwt_exp(token) is None

    def test_returns_none_on_invalid_base64(self) -> None:
        assert decode_jwt_exp("header.!!!invalid!!!.sig") is None

    def test_returns_none_on_non_object_payload(self) -> None:
        body = base64.urlsafe_b64encode(b"[1, 2, 3]").rstrip(b"=").decode()
        assert decode_jwt_exp(f"h.{body}.s") is None


class TestJwtNeedsRefresh:
    """Tests for jwt_needs_refresh."""

    def test_unknown_expiry_always_refreshes(self) -> None:
        assert jwt_needs_refresh(None, now=1000.0) is True

    def test_valid_far_future_token_is_kept(self) -> None:
        assert jwt_needs_refresh(exp=10_000.0, now=1000.0) is False

    def test_expired_token_refreshes(self) -> None:
        assert jwt_needs_refresh(exp=500.0, now=1000.0) is True

    def test_within_leeway_refreshes(self) -> None:
        # exp is in the future but inside the leeway window.
        now = 1000.0
        exp = now + (EXPIRY_LEEWAY_SECONDS / 2)
        assert jwt_needs_refresh(exp=exp, now=now) is True

    def test_just_outside_leeway_is_kept(self) -> None:
        now = 1000.0
        exp = now + EXPIRY_LEEWAY_SECONDS + 1
        assert jwt_needs_refresh(exp=exp, now=now) is False
