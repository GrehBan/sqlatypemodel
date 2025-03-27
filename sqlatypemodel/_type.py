from typing import Callable

import sqlalchemy as sa
from sqlalchemy.engine.default import DefaultDialect

from .protocols import PydanticModelProto, T


class ModelType(sa.types.TypeDecorator):
    """
    A SQLAlchemy custom type decorator for handling JSON serialization and
    deserialization of Pydantic models or other Python objects.
    This type allows storing Python objects (e.g., Pydantic models) as JSON
    in the database and retrieving them back as Python objects.
    Attributes:
        impl (Type): The underlying SQLAlchemy type used for storage (JSON).
        hashable (bool): Indicates whether the type is hashable (default: False).
        cache_ok (bool): Indicates whether the type is safe for caching (default: True).
        model (T): The Python object or Pydantic model to be serialized/deserialized.
        json_dumps (Callable[[T], str] | str | None, optional): A callable or method name
            for serializing the object to JSON. If the model is a Pydantic model,
            defaults to `model_dump`.
        json_loads (Callable[[str], T] | str | None, optional): A callable or method name
            for deserializing JSON back to the object. If the model is a Pydantic model,
            defaults to `model_validate`.
        ValueError: If `json_dumps` or `json_loads` is not provided for non-Pydantic models.
        TypeError: If `json_dumps` is not callable or a valid method.
        TypeError: If `json_loads` is not callable or a valid method.
    Methods:
        process_bind_param(value: T, dialect: DefaultDialect) -> str:
            Serializes the Python object to a JSON string for storage in the database.
        process_result_value(value: str, dialect: DefaultDialect) -> T:
            Deserializes the JSON string from the database back to the Python object.
    """

    impl = sa.JSON

    hashable = False
    cache_ok = True

    def __init__(
        self,
        model: type[T],
        json_dumps: Callable[[T], str] | str | None = None,
        json_loads: Callable[[str], T] | str | None = None,
        *args,
        **kwargs,
    ):
        """
        Initialize a ModelType instance.
        Args:
            model (T): The model instance or class to be used.
            json_dumps (Callable[[T], str] | str | None, optional): A callable or method name for serializing the model
                to a JSON string. If the model is a Pydantic model and this is not provided, the `model_dump` method
                will be used by default. Defaults to None.
            json_loads (Callable[[str], T] | str | None, optional): A callable or method name for deserializing a JSON
                string back to the model. If the model is a Pydantic model and this is not provided, the `model_validate`
                method will be used by default. Defaults to None.
            *args: Additional positional arguments to pass to the superclass initializer.
            **kwargs: Additional keyword arguments to pass to the superclass initializer.
        Raises:
            ValueError: If `json_dumps` or `json_loads` are not provided and the model is not a Pydantic model.
            TypeError: If `json_dumps` or `json_loads` is not callable or a valid method name.
        Attributes:
            model (T): The model instance or class.
            dumps (Callable[[T], str]): The callable used for serializing the model to a JSON string.
            loads (Callable[[str], T]): The callable used for deserializing a JSON string back to the model.
        """
        super(ModelType, self).__init__(*args, **kwargs)

        self.model = model

        if isinstance(model, PydanticModelProto):
            if json_dumps is None:
                json_dumps = model.model_dump
            if json_loads is None:
                json_loads = model.model_validate
        elif json_loads is None or json_dumps is None:
            raise ValueError(
                f"json_dumps and json_loads must be provided for the model of type {type(model).__name__}. Ensure that both serialization and deserialization methods are specified."
            )

        else:
            if isinstance(json_dumps, str):
                if not hasattr(self.model, json_dumps):
                    raise AttributeError(
                        f"'{type(self.model).__name__}' object has no attribute '{json_dumps}'"
                    )

                json_dumps = getattr(self.model, json_dumps)

            if isinstance(json_loads, str):
                if not hasattr(self.model, json_loads):
                    raise AttributeError(
                        f"The model of type {type(self.model).__name__} does not have a method or attribute named '{json_loads}'."
                    )

                json_loads = getattr(self.model, json_loads)

        if not callable(json_loads):
            raise TypeError(
                f"{json_loads} is not a valid method. Expected a callable, but got {type(json_loads).__name__}."
            )
        if not callable(json_dumps):
            raise TypeError(
                f"The model of type {type(self.model).__name__} does not have a valid callable for serialization: '{json_dumps}'."
            )

        self.loads: Callable[[str], T] = json_loads
        self.dumps: Callable[[T], str] = json_dumps

    def process_bind_param(self, value: T, dialect: DefaultDialect) -> str:
        """
        Processes the given value before it is bound to a database parameter.
        This method is typically used to serialize or transform the value into
        a format suitable for storage in the database.
        Args:
            value (T): The value to be processed and bound to the database parameter.
            dialect (DefaultDialect): The SQLAlchemy dialect in use, which may
                influence how the value is processed.
        Returns:
            str: The processed value, typically serialized into a string format.
        """

        return self.dumps(value)

    def process_result_value(self, value: str, dialect: DefaultDialect) -> T:
        """
        Processes the value retrieved from the database and converts it into the desired Python object.
        Args:
            value (str): The value retrieved from the database as a string.
            dialect (DefaultDialect): The SQLAlchemy dialect in use.
        Returns:
            T: The converted Python object after applying the `loads` method.
        """

        return self.loads(value)
