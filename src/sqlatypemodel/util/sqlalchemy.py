"""SQLAlchemy engine creation helpers with optimized JSON serializers.

This module provides wrappers around `sqlalchemy.create_engine` and
`sqlalchemy.ext.asyncio.create_async_engine` that automatically configure
`orjson` (if available) as the default JSON serializer and deserializer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import Engine
from sqlalchemy import create_engine as sa_create_engine
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import (
    create_async_engine as sa_create_async_engine,
)

from .json import get_serializers

__all__ = ("create_engine", "create_async_engine")


if TYPE_CHECKING:
    create_engine = sa_create_engine
    create_async_engine = sa_create_async_engine
else:

    def create_engine(*args: Any, **kwargs: Any) -> Engine:
        """Create a synchronous SQLAlchemy engine with optimized JSON
        serializers.

        This function wraps `sqlalchemy.create_engine` and injects `orjson`
        (via `get_serializers`) into `json_serializer` and `json_deserializer`
        arguments if they are not already provided.

        Args:
            *args: Positional arguments passed to `sqlalchemy.create_engine`.
            **kwargs: Keyword arguments passed to `sqlalchemy.create_engine`.

        Returns:
            An instance of `sqlalchemy.Engine`.
        """
        dumps, loads = get_serializers()
        kwargs.setdefault("json_serializer", dumps)
        kwargs.setdefault("json_deserializer", loads)
        return sa_create_engine(*args, **kwargs)

    def create_async_engine(*args: Any, **kwargs: Any) -> AsyncEngine:
        """Create an asynchronous SQLAlchemy engine with optimized JSON
        serializers.

        This function wraps `sqlalchemy.ext.asyncio.create_async_engine` and
        injects `orjson` (via `get_serializers`) into `json_serializer` and
        `json_deserializer` arguments if they are not already provided.

        Args:
            *args: Positional arguments passed to
                `sqlalchemy.create_async_engine`.
            **kwargs: Keyword arguments passed to
                `sqlalchemy.create_async_engine`.

        Returns:
            An instance of `sqlalchemy.ext.asyncio.AsyncEngine`.
        """
        dumps, loads = get_serializers()
        kwargs.setdefault("json_serializer", dumps)
        kwargs.setdefault("json_deserializer", loads)
        return sa_create_async_engine(*args, **kwargs)
