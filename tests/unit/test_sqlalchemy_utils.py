"""Unit tests for SQLAlchemy utilities."""

from __future__ import annotations

from unittest.mock import patch

from sqlatypemodel.util.sqlalchemy import create_async_engine, create_engine


class TestSqlAlchemyUtils:
    """Test SQLAlchemy helper utilities."""

    def test_create_engine_wrappers(self) -> None:
        """Test that wrappers call the real functions with json serializers."""
        with patch(
            "sqlatypemodel.util.sqlalchemy.sa_create_engine"
        ) as mock_create:
            create_engine("sqlite:///")
            _, kwargs = mock_create.call_args
            assert "json_serializer" in kwargs
            assert "json_deserializer" in kwargs

        with patch(
            "sqlatypemodel.util.sqlalchemy.sa_create_async_engine"
        ) as mock_async:
            create_async_engine("sqlite+aiosqlite:///")
            _, kwargs = mock_async.call_args
            assert "json_serializer" in kwargs
            assert "json_deserializer" in kwargs
