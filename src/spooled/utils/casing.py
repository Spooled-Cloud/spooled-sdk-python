"""
Case conversion utilities for snake_case <-> camelCase.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from typing import Any

# Keys whose values are opaque user-defined JSON and must be sent/received
# byte-for-byte, without deep key-case conversion. Mirrors the Node SDK's
# SKIP_CONVERSION_KEYS so all SDKs preserve user payloads identically.
SKIP_CONVERSION_KEYS: frozenset[str] = frozenset(
    {
        "payload",
        "result",
        "metadata",
        "tags",
        "settings",
        "details",
        "extra",
        "payloadTemplate",
        "payload_template",
        "customLimits",
        "custom_limits",
    }
)


def to_snake_case(s: str) -> str:
    """Convert camelCase or PascalCase to snake_case."""
    # Insert underscore before uppercase letters and convert to lowercase
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return s.lower()


def to_camel_case(s: str) -> str:
    """Convert snake_case to camelCase."""
    components = s.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def convert_keys(
    data: Any,
    converter: Callable[[str], str],
    skip_keys: Iterable[str] | None = None,
) -> Any:
    """Recursively convert dictionary keys using the given converter function.

    When ``skip_keys`` is provided, any key that matches (before or after
    conversion) has its value preserved verbatim without recursing into it.
    This keeps opaque user JSON (job payloads, results, metadata, ...)
    byte-for-byte identical to what the caller supplied.
    """
    skip: frozenset[str] = (
        skip_keys if isinstance(skip_keys, frozenset) else frozenset(skip_keys or ())
    )

    if isinstance(data, dict):
        result: dict[str, Any] = {}
        for key, value in data.items():
            new_key = converter(key)
            if skip and (key in skip or new_key in skip):
                # Opaque user data: preserve value exactly as provided.
                result[new_key] = value
            else:
                result[new_key] = convert_keys(value, converter, skip)
        return result
    if isinstance(data, list):
        return [convert_keys(item, converter, skip) for item in data]
    return data


def convert_request(data: Any) -> Any:
    """
    Convert request body keys to snake_case for API.

    Note: The Spooled API uses snake_case, so we convert from camelCase
    (if the user provides it) to snake_case. Values under
    ``SKIP_CONVERSION_KEYS`` (opaque user JSON such as job payloads) are
    sent verbatim and never key-case-converted.
    """
    # API uses snake_case, so we ensure keys are snake_case
    return convert_keys(data, to_snake_case, SKIP_CONVERSION_KEYS)


def convert_response(data: Any) -> Any:
    """
    Convert response body keys from API.

    Note: The Spooled API uses snake_case, so responses are already
    in snake_case format. This function is mostly a pass-through
    but handles any edge cases.
    """
    # API returns snake_case, which is what Python expects
    # Just pass through, but ensure consistency
    return data


def convert_query_params(params: dict[str, Any]) -> dict[str, str]:
    """Convert query params to snake_case strings."""
    result: dict[str, str] = {}
    for key, value in params.items():
        if value is None:
            continue
        snake_key = to_snake_case(key)
        if isinstance(value, bool):
            result[snake_key] = str(value).lower()
        else:
            result[snake_key] = str(value)
    return result
