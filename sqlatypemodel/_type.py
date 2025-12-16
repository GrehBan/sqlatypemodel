import inspect
from typing import Any, Callable, Optional, Generic, Type, TypeVar
import sqlalchemy as sa
from sqlalchemy.engine import Dialect
from .protocols import PydanticModelProto, T


class ModelType(sa.types.TypeDecorator, Generic[T]):
    """
    SQLAlchemy TypeDecorator for storing Pydantic models as JSON.

    This TypeDecorator serializes a Pydantic model into a JSON-compatible dictionary
    when writing to the database, and deserializes it back into a Pydantic model
    when reading from the database.

    Args:
        model: The Pydantic model class to serialize/deserialize.
        json_dumps: Optional callable or method name for serialization.
        json_loads: Optional callable or method name for deserialization.
    """
    impl = sa.JSON
    cache_ok = True

    def __init__(
        self,
        model: Type[T],
        json_dumps: Optional[Callable[[T], dict[str, Any]] | str] = None,
        json_loads: Optional[Callable[[dict[str, Any]], T] | str] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.model = model

        raw_dumps = None
        raw_loads = None
        is_pydantic = False

        try:
            is_pydantic = issubclass(model, PydanticModelProto)
        except TypeError:
            pass

        if is_pydantic and not json_dumps and hasattr(model, "model_dump"):
            raw_dumps = model.model_dump
        elif json_dumps:
            raw_dumps = self._get_callable(json_dumps)

        if is_pydantic and not json_loads and hasattr(model, "model_validate"):
            raw_loads = model.model_validate
        elif json_loads:
            raw_loads = self._get_callable(json_loads)

        if not raw_dumps or not raw_loads:
            raise ValueError(
                f"Could not resolve serialization methods for {model}. "
                f"Provide `json_dumps` and `json_loads` explicitly."
            )

        self.dumps = self._wrap_dumps_if_needed(raw_dumps)
        self.loads = raw_loads

    def _get_callable(self, method_name: Optional[str | Callable]) -> Callable:
        """
        Retrieve a callable from a method name string or return the callable itself.

        Args:
            method_name: A callable or the name of a method of the model.

        Returns:
            A callable object.

        Raises:
            TypeError: If the argument is not callable or a valid method name.
        """
        if callable(method_name):
            return method_name
        if isinstance(method_name, str) and hasattr(self.model, method_name):
            return getattr(self.model, method_name)
        raise TypeError(
            f"Expected a callable or a valid method name, got {type(method_name).__name__}."
        )

    def _wrap_dumps_if_needed(self, func: Callable) -> Callable:
        """
        Wrap the serialization function to add 'mode' argument if supported.

        Some Pydantic versions support `mode="json"` in model_dump.
        This inspects the function signature and wraps it if needed.

        Args:
            func: The serialization function.

        Returns:
            A callable that can serialize the model into a JSON-compatible dict.
        """
        try:
            sig = inspect.signature(func)
            if "mode" in sig.parameters:
                return lambda x: func(x, mode="json")
        except (ValueError, TypeError):
            pass
        
        return func

    def process_bind_param(
        self, value: Optional[T], dialect: Dialect
    ) -> Optional[dict[str, Any]]:
        """
        Convert a Pydantic model to a dictionary for storing in the database.

        Args:
            value: The Pydantic model instance or None.
            dialect: The SQLAlchemy database dialect.

        Returns:
            A JSON-compatible dictionary or None if value is None.
        """
        if value is None:
            return None
        return self.dumps(value)

    def process_result_value(
        self, value: Optional[dict[str, Any]], dialect: Dialect
    ) -> Optional[T]:
        """
        Convert a dictionary from the database back into a Pydantic model.

        Args:
            value: A JSON-compatible dictionary from the database.
            dialect: The SQLAlchemy database dialect.

        Returns:
            A Pydantic model instance or None if value is None.
        """
        if value is None:
            return None
        return self.loads(value)
