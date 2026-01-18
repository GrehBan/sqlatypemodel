"""JSON serialization utilities with orjson support and automatic fallback.

This module provides optimized JSON serialization and deserialization
functions. It prefers `orjson` for performance but gracefully falls back to
the standard `json` library when `orjson` is unavailable or encounters
unsupported types (e.g., integers larger than 64-bit).
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from typing import Any, cast

logger = logging.getLogger(__name__)

orjson: Any

HAS_ORJSON = False
if os.getenv("SQLATYPEMODEL_NO_ORJSON", "0") != "1":
    try:
        import orjson as _orjson

        orjson = _orjson
        HAS_ORJSON = True
    except ImportError:
        orjson = None
else:
    orjson = None

if not HAS_ORJSON and os.getenv("SQLATYPEMODEL_FORCE_ORJSON", "0") == "1":
    raise ImportError(
        "orjson is required but not found or disabled via "
        "SQLATYPEMODEL_NO_ORJSON while SQLATYPEMODEL_FORCE_ORJSON=1."
    )

__all__ = ("get_serializers",)


def _std_dumps(obj: Any) -> str:
    """Standard JSON serialization.

    Uses `default=str` to safely handle types like Decimal or datetime
    if standard json doesn't support them out of the box.

    Args:
        obj: The object to serialize.

    Returns:
        The JSON string representation.
    """
    return json.dumps(obj, default=str)


def _orjson_dumps_wrapper(obj: Any) -> str:
    """Attempt orjson serialization, fallback to standard json on failure.

    Handles specific edge cases where orjson is stricter than standard json:
    1. Integer overflow (int > 64 bit) -> Fallback to standard json.
    2. Unknown types (TypeError) -> Fallback to standard json.

    Args:
        obj: The object to serialize.

    Returns:
        The JSON string representation.
    """
    try:
        return cast(str, orjson.dumps(obj).decode("utf-8"))
    except (orjson.JSONEncodeError, TypeError, OverflowError):
        return _std_dumps(obj)


def _orjson_loads_wrapper(data: str | bytes) -> Any:
    """Attempt orjson deserialization, fallback to standard json on failure.

    Useful compatibility layer if data in the DB was saved via standard json
    (e.g., huge integers) or if the input encoding is not supported by orjson.

    Args:
        data: The JSON string or bytes to deserialize.

    Returns:
        The Python object.
    """
    try:
        return orjson.loads(data)
    except (orjson.JSONDecodeError, TypeError, ValueError):
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return json.loads(data)


def get_serializers(
    use_orjson: bool = True,
) -> tuple[Callable[[Any], str], Callable[[str | bytes], Any]]:
    """Get the most robust JSON serialization/deserialization pair available.

    Selects the best available serializers based on configuration and library
    availability.

    Args:
        use_orjson: If True, attempts to use orjson with fallback to json.
                    If False (or orjson is missing), uses strict standard json.

    Returns:
        A tuple of (dumps_function, loads_function).
    """
    if use_orjson and HAS_ORJSON:
        return _orjson_dumps_wrapper, _orjson_loads_wrapper

    return _std_dumps, json.loads
