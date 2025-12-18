"""SQLAlchemy TypeDecorator for storing Pydantic models as JSON."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast

import sqlalchemy as sa
from sqlalchemy.engine import Dialect

from .exceptions import DeserializationError, SerializationError
from .protocols import PT, PydanticModelProtocol

if TYPE_CHECKING:
    from .mixin import MutableMixin

__all__ = ("ModelType",)

_T = TypeVar("_T")
logger = logging.getLogger(__name__)


class ModelType(sa.types.TypeDecorator[PT], Generic[PT]):
    """SQLAlchemy TypeDecorator for storing Pydantic models as JSON.

    This custom type handles the serialization of Pydantic models (or any class
    conforming to PydanticModelProtocol) into JSON for database storage,
    and deserialization back into Python objects upon retrieval.

    It also integrates with `MutableMixin` to ensure that nested changes
    within the JSON structure are tracked and persisted.

    Attributes:
        impl (Any): The underlying SQLAlchemy implementation type (JSON).
        cache_ok (bool): Indicates that this type is safe to cache.
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
        """Initialize the ModelType.

        Args:
            model: The Pydantic model class (or protocol-compatible class)
                to be stored in this column.
            json_dumps: Optional custom function to serialize the model
                to a dict/JSON. If None, uses `model.model_dump(mode='json')`.
            json_loads: Optional custom function to deserialize a dict/JSON
                to the model. If None, uses `model.model_validate()`.
            *args: Positional arguments passed to `sa.types.TypeDecorator`.
            **kwargs: Keyword arguments passed to `sa.types.TypeDecorator`.

        Raises:
            ValueError: If the provided `model` class does not implement the
                Pydantic protocol and no custom serializers are provided.
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
            # FIX: Removed unused type: ignore, as cast() handles it correctly
            self.loads = cast(
                Callable[[dict[str, Any]], PT], model.model_validate
            )
        else:
            raise ValueError(
                f"Cannot resolve deserialization for {model.__name__}. "
                f"Inherit from Pydantic BaseModel or provide 'json_loads'."
            )

    def _create_pydantic_dumps(self) -> Callable[[PT], dict[str, Any]]:
        """Create a default serialization function for Pydantic models.

        Returns:
            A callable that takes a model instance and returns a dict.
        """

        def dumps(obj: PT) -> dict[str, Any]:
            return obj.model_dump(mode="json")

        return dumps

    @staticmethod
    def _is_pydantic_compatible(model: type) -> bool:
        """Check if a class adheres to the PydanticModelProtocol.

        Args:
            model: The class to check.

        Returns:
            True if the class implements `model_dump` and `model_validate`,
            False otherwise.
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

        This method links a specific MutableMixin implementation (like the
        one used on the model) with this TypeDecorator, enabling automatic
        change tracking.

        Args:
            mutable: The MutableMixin subclass to register.

        Raises:
            TypeError: If the argument is not a subclass of MutableMixin.
        """
        from .mixin import MutableMixin

        if not inspect.isclass(mutable) or not issubclass(
            mutable, MutableMixin
        ):
            raise TypeError("mutable must be a subclass of MutableMixin")
        mutable.associate_with(cls)

    def process_bind_param(
        self,
        value: PT | None,
        dialect: Dialect,
    ) -> dict[str, Any] | None:
        """Serialize the Python object for storage in the database.

        Args:
            value: The Python object (Pydantic model) to serialize.
            dialect: The database dialect in use.

        Returns:
            A dictionary representation of the object, or None.

        Raises:
            SerializationError: If serialization fails.
        """
        if value is None:
            return None

        try:
            return self.dumps(value)
        except Exception as e:
            logger.error(
                "Serialization failed for model %s: %s",
                self.model.__name__,
                e,
                exc_info=True,
            )
            raise SerializationError(self.model.__name__, e) from e

    def process_result_value(
        self,
        value: dict[str, Any] | None,
        dialect: Dialect,
    ) -> PT | None:
        """Deserialize the database value into a Python object.

        This method also triggers the `_scan_and_wrap_fields` hook on the
        deserialized object to ensure that any nested mutable structures
        are immediately tracked for changes.

        Args:
            value: The JSON/Dict value from the database.
            dialect: The database dialect in use.

        Returns:
            The instantiated Pydantic model (or compatible object), or None.

        Raises:
            DeserializationError: If deserialization fails.
        """
        if value is None:
            return None
        try:
            result = self.loads(value)

            if hasattr(result, "_scan_and_wrap_fields") and callable(
                result._scan_and_wrap_fields
            ):
                result._scan_and_wrap_fields()
            return result
        except Exception as e:
            logger.error(
                "Deserialization failed for model %s: %s",
                self.model.__name__,
                e,
                exc_info=True,
            )
            raise DeserializationError(self.model.__name__, value, e) from e
