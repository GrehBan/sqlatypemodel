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
        """Create a synchronous SQLAlchemy engine with orjson serializers.

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
        """Create an asynchronous SQLAlchemy engine with orjson serializers.

        Args:
            *args: Positional arguments passed to `sqlalchemy.create_async_engine`.
            **kwargs: Keyword arguments passed to `sqlalchemy.create_async_engine`.

        Returns:
            An instance of `sqlalchemy.AsyncEngine`.
        """
        dumps, loads = get_serializers()
        kwargs.setdefault("json_serializer", dumps)
        kwargs.setdefault("json_deserializer", loads)
        return sa_create_async_engine(*args, **kwargs)
