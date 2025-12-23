"""SQLAlchemy TypeDecorator for storing Pydantic models as JSON."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast

import sqlalchemy as sa
from sqlalchemy.engine import Dialect

from sqlatypemodel.exceptions import DeserializationError, SerializationError
from sqlatypemodel.model_type.protocols import PydanticModelProtocol
from sqlatypemodel.util.json import get_serializers

if TYPE_CHECKING:
    from sqlatypemodel.mixin import BaseMutableMixin

__all__ = ("ModelType",)

T = TypeVar("T", bound=PydanticModelProtocol)
logger = logging.getLogger(__name__)


class ModelType(sa.types.TypeDecorator[T], Generic[T]):
    """SQLAlchemy TypeDecorator for storing Pydantic models as JSON.

    Automatically handles:
    1. Serialization: Pydantic Model -> Dict (for DB JSON type)
    2. Deserialization: DB Value -> Pydantic Model
    3. Change Tracking Restoration: Re-activates MutableMixin tracking on load.
    """

    impl = sa.JSON
    cache_ok = True

    def __init__(
        self,
        model: type[T],
        dumper: Callable[[T], dict[str, Any]] | None = None,
        loader: Callable[[dict[str, Any]], T] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize the ModelType.

        Args:
            model: A Pydantic model class (or compatible) to be stored.
            dumper: Custom serialization function (Model -> Dict).
            loader: Custom deserialization function (Dict -> Model).
            *args: Additional arguments for TypeDecorator.
            **kwargs: Additional keyword arguments for TypeDecorator.

        Raises:
            ValueError: If serialization or deserialization functions
                        cannot be resolved.
        """
        super().__init__(*args, **kwargs)
        self.model: type[T] = model

        self._json_dumps_str, self._json_loads_str = get_serializers()

        is_pydantic = self._is_pydantic_compatible(model)

        if dumper is not None:
            self.dumper: Callable[[T], dict[str, Any]] = dumper
        elif is_pydantic:
            self.dumper = self._create_pydantic_dumps()
        else:
            raise ValueError(
                f"Cannot resolve serialization for {model.__name__}. "
                f"Inherit from Pydantic BaseModel or provide 'json_dumps'."
            )

        if loader is not None:
            self.loader: Callable[[dict[str, Any]], T] = loader
        elif is_pydantic:
            self.loader = cast(
                Callable[[dict[str, Any]], T], model.model_validate
            )
        else:
            raise ValueError(
                f"Cannot resolve deserialization for {model.__name__}. "
                f"Inherit from Pydantic BaseModel or provide 'json_loads'."
            )

    @property
    def python_type(self) -> type[T]:
        """Return the Python type associated with this type."""
        return self.model

    def _create_pydantic_dumps(self) -> Callable[[T], dict[str, Any]]:
        """Create a generic dumps function for Pydantic models.

        Returns:
            A callable converting the model to a dict.
        """

        def dumps(obj: T) -> dict[str, Any]:
            return obj.model_dump(mode="json")

        return dumps

    @staticmethod
    def _is_pydantic_compatible(model: type) -> bool:
        """Check compatibility with Pydantic V2 protocol.

        Args:
            model: The class to check.

        Returns:
            True if the model is compatible.
        """
        return issubclass(model, PydanticModelProtocol) or (
            hasattr(model, "model_dump") and hasattr(model, "model_validate")
        )

    @classmethod
    def register_mutable(cls, mutable: type[BaseMutableMixin]) -> None:
        """Associates a MutableMixin subclass with this type.

        Args:
            mutable: The MutableMixin subclass to register.

        Raises:
            TypeError: If mutable is not a subclass of BaseMutableMixin.
        """
        from sqlatypemodel.mixin import BaseMutableMixin

        if not inspect.isclass(mutable) or not issubclass(
            mutable, BaseMutableMixin
        ):
            raise TypeError("mutable must be a subclass of BaseMutableMixin")

        mutable.associate_with(cls)

    def process_bind_param(
        self,
        value: T | dict[str, Any] | None,
        dialect: Dialect,
    ) -> dict[str, Any] | None:
        """Convert Model to Dict for SQLAlchemy's JSON type.

        Args:
            value: The model instance or dict to bind.
            dialect: The database dialect.

        Returns:
            The serialized dictionary or None.

        Raises:
            SerializationError: If serialization fails.
        """
        if value is None:
            return None

        if isinstance(value, dict):
            return value

        try:
            return self.dumper(value)
        except Exception as e:
            logger.error(
                "Serialization failed for model %s: %s",
                self.model.__name__,
                e,
                exc_info=True,
            )
            raise SerializationError(self.model.__name__, e) from e

    def process_literal_param(
        self, value: T | None, dialect: Dialect
    ) -> str:
        """Render value as a literal SQL string (for logs/debugging).

        Args:
            value: The value to render.
            dialect: The database dialect.

        Returns:
            The SQL string representation.
        """
        bind_value = self.process_bind_param(value, dialect)
        if bind_value is None:
            return "NULL"

        return self._json_dumps_str(bind_value)

    def process_result_value(
        self,
        value: dict[str, Any] | str | bytes | None,
        dialect: Dialect,
    ) -> T | None:
        """Convert DB value back to Model and restore tracking.

        Args:
            value: The raw value from the database.
            dialect: The database dialect.

        Returns:
            The deserialized model instance or None.

        Raises:
            DeserializationError: If deserialization fails.
        """
        if value is None:
            return None

        try:
            if isinstance(value, str | bytes):
                value = self._json_loads_str(value)

            result = self.loader(cast("dict[str, Any]", value))

            if hasattr(result, "_restore_tracking") and callable(
                result._restore_tracking
            ):
                result._restore_tracking()

            return result
        except Exception as e:
            logger.error(
                "Deserialization failed for model %s. Value type: %s. "
                "Error: %s",
                self.model.__name__,
                type(value),
                e,
                exc_info=True,
            )
            raise DeserializationError(self.model.__name__, value, e) from e