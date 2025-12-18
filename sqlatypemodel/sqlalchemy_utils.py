from typing import Any

from sqlalchemy import create_engine, Engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

from .serializer import get_serializers

__all__ = ("create_sync_engine", "create_async_engine")


def create_sync_engine(*args: Any, **kwargs: Any) -> Engine:
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
    return create_engine(*args, **kwargs)


async def create_async_engine(*args: Any, **kwargs: Any) -> AsyncEngine:
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
    return await create_async_engine(*args, **kwargs)