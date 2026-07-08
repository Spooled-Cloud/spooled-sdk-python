"""Minimal JWT helpers for realtime token caching.

The SDK exchanges an API key for a short-lived JWT before opening a realtime
(WebSocket/SSE) connection. To avoid re-running ``POST /auth/login`` on every
(re)connect -- which trips the login rate limiter during reconnect storms -- the
client caches the JWT and only re-logs-in when the cached token is missing or
close to expiry.

Deciding "close to expiry" only requires the ``exp`` claim, so these helpers
base64url-decode the JWT payload and read ``exp`` **without verifying the
signature**. That is safe here: the token was just issued to us by the API over
TLS, so we trust it and merely inspect the expiry to schedule the next login.
"""

from __future__ import annotations

import base64
import binascii
import json

# Re-login this many seconds before the JWT actually expires so an in-flight
# (re)connect never races the server-side expiry and gets rejected.
EXPIRY_LEEWAY_SECONDS = 60.0


def decode_jwt_exp(token: str) -> float | None:
    """Return the ``exp`` claim (epoch seconds) from a JWT, or ``None``.

    The signature is **not** verified. ``None`` is returned when ``token`` is not
    a well-formed JWT or carries no numeric ``exp`` claim; callers should treat
    that token as non-cacheable and always refresh it.
    """
    parts = token.split(".")
    if len(parts) != 3:
        return None

    payload_segment = parts[1]
    # JWTs use base64url without padding; restore it before decoding.
    padding = "=" * (-len(payload_segment) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload_segment + padding)
        claims = json.loads(decoded)
    except (binascii.Error, ValueError):
        return None

    if not isinstance(claims, dict):
        return None
    exp = claims.get("exp")
    # bool is a subclass of int; guard against it being read as an expiry.
    if isinstance(exp, (int, float)) and not isinstance(exp, bool):
        return float(exp)
    return None


def jwt_needs_refresh(
    exp: float | None,
    now: float,
    leeway: float = EXPIRY_LEEWAY_SECONDS,
) -> bool:
    """Whether a cached JWT expiring at ``exp`` should be refreshed at ``now``.

    An unknown expiry (``None``) always refreshes: we cannot prove the token is
    still valid, so we err on the side of a fresh login.
    """
    if exp is None:
        return True
    return now >= (exp - leeway)
