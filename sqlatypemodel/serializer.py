"""JSON serialization utilities with orjson support."""
from __future__ import annotations

import json
from typing import Any, Callable

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False
    orjson = None  # type: ignore


def get_serializers(
    use_orjson: bool = True,
) -> tuple[Callable[[Any], str], Callable[[str | bytes], Any]]:
    """
    Get the fastest available JSON serialization/deserialization pair.
    
    Args:
        use_orjson: Helper to force enable/disable orjson. 
                    Has no effect if orjson is not installed.
    """
    if use_orjson and HAS_ORJSON:
        
        def fast_dumps(obj: Any) -> str:
            return orjson.dumps(obj).decode("utf-8")

        def fast_loads(s: str | bytes) -> Any:
            return orjson.loads(s)

        return fast_dumps, fast_loads

    return json.dumps, json.loads