"""SQLAlchemy TypeDecorator for storing Pydantic models as JSON.

This module provides the ModelType class, which enables transparent
serialization and deserialization of Pydantic models to and from
SQLAlchemy JSON columns.

Example:
    >>> from pydantic import BaseModel
    >>> from sqlalchemy import Column
    >>> from sqlalchemy.orm import Mapped, mapped_column
    >>> from sqlatypemodel import ModelType, MutableMixin
    >>> 
    >>> class Settings(MutableMixin, BaseModel):
    ...     theme: str
    ...     notifications: bool = True
    >>> 
    >>> class User(Base):
    ...     __tablename__ = "users"
    ...     id: Mapped[int] = mapped_column(primary_key=True)
    ...     settings: Mapped[Settings] = mapped_column(
    ...         Settings.as_mutable(ModelType(Settings))
    ...     )
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Callable, Generic, TypeVar

import sqlalchemy as sa
from sqlalchemy.engine import Dialect

from .exceptions import DeserializationError, SerializationError
from .protocols import PT, PydanticModelProtocol

if TYPE_CHECKING:
    from .mixin import MutableMixin

__all__ = (
    "ModelType",
)

_T = TypeVar("_T")


class ModelType(sa.types.TypeDecorator, Generic[PT]):
    """SQLAlchemy TypeDecorator for storing Pydantic models as JSON.

    This TypeDecorator handles:
    - Serialization: Pydantic model -> JSON dict (on write)
    - Deserialization: JSON dict -> Pydantic model (on read)

    Supports both Pydantic BaseModel subclasses and any class that
    implements the PydanticModelProtocol interface.

    Attributes:
        impl: The underlying SQLAlchemy type (JSON).
        cache_ok: Whether the type is safe to cache (True).
        model: The Pydantic model class being serialized.
        dumps: The serialization callable.
        loads: The deserialization callable.

    Args:
        model: The Pydantic model class to serialize/deserialize.
        json_dumps: Optional custom serialization callable.
                   Defaults to model.model_dump(mode='json') for Pydantic models.
        json_loads: Optional custom deserialization callable.
                   Defaults to model.model_validate() for Pydantic models.

    Example:
        >>> # Automatic serialization for Pydantic models
        >>> class Config(BaseModel):
        ...     theme: str
        ...     debug: bool = False
        >>> 
        >>> config_column = mapped_column(ModelType(Config))
        >>> 
        >>> # Custom serialization for non-Pydantic classes
        >>> class CustomData:
        ...     def to_dict(self) -> dict: ...
        ...     @classmethod
        ...     def from_dict(cls, data: dict) -> 'CustomData': ...
        >>> 
        >>> custom_column = mapped_column(ModelType(
        ...     CustomData,
        ...     json_dumps=lambda x: x.to_dict(),
        ...     json_loads=CustomData.from_dict
        ... ))
    """

    impl = sa.JSON
    cache_ok = True

    def __init__(
        self,
        model: type[PT],
        json_dumps: Callable[[PT], dict[str, Any]] | None = None,
        json_loads: Callable[[dict[str, Any]], PT] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize the ModelType decorator.

        Args:
            model: The Pydantic model class to serialize/deserialize.
            json_dumps: Optional custom serialization callable.
            json_loads: Optional custom deserialization callable.
            *args: Additional positional arguments for TypeDecorator.
            **kwargs: Additional keyword arguments for TypeDecorator.

        Raises:
            ValueError: If serialization/deserialization methods cannot
                       be resolved for non-Pydantic models.
        """
        super().__init__(*args, **kwargs)
        self.model = model

        is_pydantic = self._is_pydantic_compatible(model)

        if json_dumps is not None:
            self.dumps = json_dumps
        elif is_pydantic:
            self.dumps = self._create_pydantic_dumps()
        else:
            raise ValueError(
                f"Cannot resolve serialization for {model.__name__}. "
                f"Inherit from Pydantic BaseModel or provide 'json_dumps'."
            )

        if json_loads is not None:
            self.loads = json_loads
        elif is_pydantic:
            self.loads = model.model_validate  # type: ignore[attr-defined]
        else:
            raise ValueError(
                f"Cannot resolve deserialization for {model.__name__}. "
                f"Inherit from Pydantic BaseModel or provide 'json_loads'."
            )

    def _create_pydantic_dumps(self) -> Callable[[PT], dict[str, Any]]:
        """Create a serialization function for Pydantic models.

        Returns:
            A callable that serializes a Pydantic model to a JSON dict.
        """
        def dumps(obj: PT) -> dict[str, Any]:
            return obj.model_dump(mode="json")  # type: ignore[attr-defined]
        return dumps

    @staticmethod
    def _is_pydantic_compatible(model: type) -> bool:
        """Check if a model class is Pydantic-compatible.

        A model is Pydantic-compatible if it:
        1. Is an instance of PydanticModelProtocol, or
        2. Has callable model_dump and model_validate methods.

        Args:
            model: The model class to check.

        Returns:
            True if the model is Pydantic-compatible, False otherwise.
        """
        try:
            if issubclass(model, PydanticModelProtocol):
                return True
        except TypeError:
            pass

        model_dump = getattr(model, "model_dump", None)
        model_validate = getattr(model, "model_validate", None)

        return callable(model_dump) and callable(model_validate)

    @classmethod
    def register_mutable(cls, mutable: type[MutableMixin]) -> None:
        """Register a MutableMixin subclass with this ModelType.

        This method associates a mutable class with the ModelType,
        enabling automatic change tracking.

        Args:
            mutable: A MutableMixin subclass to register.

        Raises:
            TypeError: If mutable is not a class or not a MutableMixin subclass.
        """
        from .mixin import MutableMixin

        if not inspect.isclass(mutable) or not issubclass(mutable, MutableMixin):
            raise TypeError(
                "mutable must be a class that inherits from MutableMixin"
            )
        mutable.associate_with(cls)

    def process_bind_param(
        self,
        value: PT | None,
        dialect: Dialect,
    ) -> dict[str, Any] | None:
        """Serialize a Pydantic model for database storage.

        This method is called by SQLAlchemy when writing to the database.

        Args:
            value: The Pydantic model instance to serialize, or None.
            dialect: The SQLAlchemy dialect being used.

        Returns:
            A JSON-compatible dictionary, or None if value is None.

        Raises:
            SerializationError: If serialization fails.
        """
        if value is None:
            return None

        try:
            return self.dumps(value)
        except Exception as e:
            raise SerializationError(self.model.__name__, e) from e

    def process_result_value(
        self,
        value: dict[str, Any] | None,
        dialect: Dialect,
    ) -> PT | None:
        """Deserialize database JSON into a Pydantic model.

        This method is called by SQLAlchemy when reading from the database.

        Args:
            value: The JSON dictionary from the database, or None.
            dialect: The SQLAlchemy dialect being used.

        Returns:
            A Pydantic model instance, or None if value is None.

        Raises:
            DeserializationError: If deserialization fails.
        """
        if value is None:
            return None

        try:
            return self.loads(value)
        except Exception as e:
            raise DeserializationError(self.model.__name__, value, e) from e
