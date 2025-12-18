"""
Case conversion utilities for snake_case <-> camelCase.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any


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


def convert_keys(data: Any, converter: Callable[[str], str]) -> Any:
    """Recursively convert dictionary keys using the given converter function."""
    if isinstance(data, dict):
        return {converter(k): convert_keys(v, converter) for k, v in data.items()}
    if isinstance(data, list):
        return [convert_keys(item, converter) for item in data]
    return data


def convert_request(data: Any) -> Any:
    """
    Convert request body keys to snake_case for API.

    Note: The Spooled API uses snake_case, so we convert from camelCase
    (if the user provides it) to snake_case.
    """
    # API uses snake_case, so we ensure keys are snake_case
    return convert_keys(data, to_snake_case)


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
