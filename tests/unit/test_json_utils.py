"""Unit tests for JSON utilities."""

from __future__ import annotations

from unittest.mock import patch

from sqlatypemodel.util.json import (
    _orjson_dumps_wrapper,
    _orjson_loads_wrapper,
)


class TestJsonFallback:
    """Test JSON serialization fallback mechanisms."""

    def test_orjson_dumps_fallback(self) -> None:
        """Test fallback to standard json when orjson fails."""
        with patch("sqlatypemodel.util.json.orjson") as mock_orjson:
            mock_orjson.dumps.side_effect = TypeError("Unsupported type")
            mock_orjson.JSONEncodeError = TypeError

            data = {"key": "value"}
            result = _orjson_dumps_wrapper(data)
            assert result == '{"key": "value"}'

    def test_orjson_loads_fallback(self) -> None:
        """Test fallback to standard json when orjson fails to load."""
        with patch("sqlatypemodel.util.json.orjson") as mock_orjson:
            mock_orjson.loads.side_effect = ValueError("Invalid JSON")
            mock_orjson.JSONDecodeError = ValueError

            data = '{"key": "value"}'
            result = _orjson_loads_wrapper(data)
            assert result == {"key": "value"}

    def test_orjson_loads_bytes_fallback(self) -> None:
        """Test fallback with bytes input."""
        with patch("sqlatypemodel.util.json.orjson") as mock_orjson:
            mock_orjson.loads.side_effect = ValueError("Invalid JSON")
            mock_orjson.JSONDecodeError = ValueError

            data = b'{"key": "value"}'
            result = _orjson_loads_wrapper(data)
            assert result == {"key": "value"}
