"""sqlatypemodel - SQLAlchemy TypeDecorator for Pydantic models.

This package provides tools for storing Pydantic models in SQLAlchemy
JSON columns with automatic serialization, deserialization, and
mutation tracking.

Main Components:
    - ModelType: TypeDecorator for JSON serialization of Pydantic models
    - MutableMixin: Mixin for automatic change tracking
    - PydanticModelProtocol: Protocol for Pydantic-compatible classes

Example:
    >>> from pydantic import BaseModel
    >>> from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
    >>> from sqlatypemodel import ModelType, MutableMixin
    >>> 
    >>> class Base(DeclarativeBase):
    ...     pass
    >>> 
    >>> class UserSettings(MutableMixin, BaseModel):
    ...     theme: str = "light"
    ...     notifications: bool = True
    ...     tags: list[str] = []
    >>> 
    >>> class User(Base):
    ...     __tablename__ = "users"
    ...     id: Mapped[int] = mapped_column(primary_key=True)
    ...     settings: Mapped[UserSettings] = mapped_column(
    ...         UserSettings.as_mutable(ModelType(UserSettings)),
    ...         default=UserSettings
    ...     )
    >>> 
    >>> # Usage
    >>> user = User()
    >>> user.settings.theme = "dark"  # Automatically tracked!
    >>> user.settings.tags.append("premium")  # Also tracked!
"""

from __future__ import annotations

from .exceptions import (
    DeserializationError,
    SerializationError,
    SQLATypeModelError,
)
from .mixin import MutableMixin
from .model_type import ModelType
from .protocols import PT, PydanticModelProtocol

__all__ = (
    "ModelType",
    "MutableMixin",
    "PydanticModelProtocol",
    "PT",
    "SQLATypeModelError",
    "SerializationError",
    "DeserializationError",
)

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("sqlatypemodel")
except PackageNotFoundError:
    __version__ = "0.4.0"
