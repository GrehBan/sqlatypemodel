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
from .serializer import get_serializers

if TYPE_CHECKING:
    from .mixin import MutableMixin

__all__ = ("ModelType",)

_T = TypeVar("_T")
logger = logging.getLogger(__name__)


class ModelType(sa.types.TypeDecorator[PT], Generic[PT]):
    """SQLAlchemy TypeDecorator for storing Pydantic models as JSON."""

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
        """
        Initialize the ModelType with a Pydantic model and optional serializers.
        Args:
            model: A Pydantic model class to be stored.
            json_dumps: Optional custom serialization function (Model -> Dict).
            json_loads: Optional custom deserialization function (Dict -> Model).
        Raises:
            ValueError: If serialization or deserialization cannot be resolved.
        """
        super().__init__(*args, **kwargs)
        self.model = model
        self._json_dumps, self._json_loads = get_serializers()

        is_pydantic = self._is_pydantic_compatible(model)

        # Настройка сериализации (Model -> Dict)
        if json_dumps is not None:
            self.dumps = json_dumps
        elif is_pydantic:
            self.dumps = self._create_pydantic_dumps()
        else:
            raise ValueError(
                f"Cannot resolve serialization for {model.__name__}. "
                f"Inherit from Pydantic BaseModel or provide 'json_dumps'."
            )

        # Настройка десериализации (Dict -> Model)
        if json_loads is not None:
            self.loads = json_loads
        elif is_pydantic:
            self.loads = cast(
                Callable[[dict[str, Any]], PT], model.model_validate
            )
        else:
            raise ValueError(
                f"Cannot resolve deserialization for {model.__name__}. "
                f"Inherit from Pydantic BaseModel or provide 'json_loads'."
            )

    @property
    def python_type(self) -> type[PT]:
        """"Return the Python type handled by this TypeDecorator."""
        return self.model

    def _create_pydantic_dumps(self) -> Callable[[PT], dict[str, Any]]:
        """Create a dumps function for Pydantic models."""
        def dumps(obj: PT) -> dict[str, Any]:
            return obj.model_dump(mode="json")
        return dumps

    @staticmethod
    def _is_pydantic_compatible(model: type) -> bool:
        """Check if the model is compatible with Pydantic protocol."""
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
        """
        Register a MutableMixin subclass to track mutations.
        Args:
            mutable: A subclass of MutableMixin to register.
            Raises: TypeError: If `mutable` is not a subclass of MutableMixin.
        """
        from .mixin import MutableMixin

        if not inspect.isclass(mutable) or not issubclass(
            mutable, MutableMixin
        ):
            raise TypeError("mutable must be a subclass of MutableMixin")
        mutable.associate_with(cls)

    def process_bind_param(
        self,
        value: PT | dict[str, Any] | None,
        dialect: Dialect,
    ) -> dict[str, Any] | None:
        """Serialize the Python object into a database-compatible format."""
        if value is None:
            return None
        
        # Если пришел словарь - отдаем как есть, драйвер сам его сериализует
        if isinstance(value, dict):
            return value

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

    def process_literal_param(
        self, value: PT | None, dialect: Dialect
    ) -> str:
        """Serialize the value for literal SQL rendering."""
        bind_value = self.process_bind_param(value, dialect)
        if bind_value is None:
            return "NULL"
        
        return self._json_dumps(bind_value)

    def process_result_value(
        self,
        value: dict[str, Any] | str | bytes | None,
        dialect: Dialect,
    ) -> PT | None:
        """Deserialize the database value into a Python object."""
        if value is None:
            return None

        try:
            if isinstance(value, (str, bytes)):
                value = self._json_loads(value)

            result = self.loads(cast("dict[str, Any]", value))

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