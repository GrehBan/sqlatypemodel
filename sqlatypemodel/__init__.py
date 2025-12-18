"""sqlatypemodel - SQLAlchemy TypeDecorator for Pydantic models.

This package provides tools for storing Pydantic models in SQLAlchemy
JSON columns with automatic serialization, deserialization, and
mutation tracking.

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
    ...     
    ...     # MutableMixin automatically registers with ModelType via __init_subclass__
    ...     settings: Mapped[UserSettings] = mapped_column(
    ...         ModelType(UserSettings)
    ...     )
    >>> 
    >>> # Usage
    >>> user = User(settings=UserSettings())
    >>> user.settings.theme = "dark"  # Automatically tracked!
    >>> user.settings.tags.append("premium")  # Also tracked!

"""
from __future__ import annotations

from . import sqlalchemy_utils, exceptions


from .mixin import MutableMixin
from .model_type import ModelType
from .protocols import PT, PydanticModelProtocol

__all__ = (
    "ModelType",
    "MutableMixin",
    "PydanticModelProtocol",
    "PT",
    "sqlalchemy_utils",
    "exceptions",
)

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("sqlatypemodel")
except PackageNotFoundError:
    __version__ = "0.4.0"
