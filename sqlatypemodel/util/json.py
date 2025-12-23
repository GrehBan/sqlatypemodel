"""JSON serialization utilities with orjson support and automatic fallback."""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False
    orjson = None # type: ignore [assignment]

__all__ = (
    "get_serializers",
)


def _std_dumps(obj: Any) -> str:
    """
    Standard JSON serialization.
    Uses default=str to safely handle types like Decimal or datetime 
    if standard json doesn't support them out of the box.
    """
    return json.dumps(obj, default=str)


def _orjson_dumps_wrapper(obj: Any) -> str:
    """
    Attempt orjson serialization, fallback to standard json on failure.
    Handles:
    1. Integer overflow (int > 64 bit) -> Fallback
    2. Unknown types (TypeError) -> Fallback
    """
    try:
        return orjson.dumps(obj).decode("utf-8")
    except (orjson.JSONEncodeError, TypeError, OverflowError):
        return _std_dumps(obj)


def _orjson_loads_wrapper(data: str | bytes) -> Any:
    """
    Attempt orjson deserialization, fallback to standard json on failure.
    Useful if data in DB was saved via standard json (e.g. huge integers).
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
    """
    Get the most robust JSON serialization/deserialization pair available.

    Args:
        use_orjson: If True, attempts to use orjson with fallback to json.
                    If False (or orjson missing), uses strict standard json.

    Returns:
        A tuple of (dumps_function, loads_function).
    """
    if use_orjson and HAS_ORJSON:
        return _orjson_dumps_wrapper, _orjson_loads_wrapper

    return _std_dumps, json.loads