"""Custom exceptions for sqlatypemodel serialization operations.

This module defines domain-specific exceptions for handling serialization
and deserialization errors when working with Pydantic models in SQLAlchemy.

Example:
    >>> from sqlatypemodel.exceptions import SerializationError
    >>> try:
    ...     # serialization operation
    ...     pass
    ... except SerializationError as e:
    ...     print(f"Failed to serialize: {e}")
"""

from __future__ import annotations

from typing import Any

__all__ = (
    "SQLATypeModelError",
    "SerializationError",
    "DeserializationError",
)


class SQLATypeModelError(Exception):
    """Base exception for all sqlatypemodel errors.

    All custom exceptions in this library inherit from this class,
    allowing users to catch all library-specific errors with a single
    except clause.

    Example:
        >>> try:
        ...     # any sqlatypemodel operation
        ...     pass
        ... except SQLATypeModelError:
        ...     print("A sqlatypemodel error occurred")
    """


class SerializationError(SQLATypeModelError):
    """Raised when model serialization to database format fails.

    This exception is raised when a Pydantic model instance cannot be
    converted to a JSON-compatible dictionary for database storage.

    Attributes:
        model_name (str): Name of the model class that failed to serialize.
        original_error (Exception | None): The underlying exception that caused the failure.

    Example:
        >>> raise SerializationError(
        ...     "MyModel",
        ...     ValueError("Invalid field value")
        ... )
    """

    def __init__(
        self,
        model_name: str,
        original_error: Exception | None = None,
    ) -> None:
        """Initialize SerializationError.

        Args:
            model_name: Name of the model class that failed to serialize.
            original_error: The underlying exception that caused the failure.
                Defaults to None.
        """
        self.model_name = model_name
        self.original_error = original_error
        message = f"Failed to serialize {model_name} instance"
        if original_error:
            message = f"{message}: {original_error}"
        super().__init__(message)


class DeserializationError(SQLATypeModelError):
    """Raised when model deserialization from database format fails.

    This exception is raised when database JSON data cannot be converted
    back into a Pydantic model instance.

    Attributes:
        model_name (str): Name of the model class that failed to deserialize.
        data (dict[str, Any] | None): The raw database data that could not be deserialized.
        original_error (Exception | None): The underlying exception that caused the failure.

    Example:
        >>> raise DeserializationError(
        ...     "MyModel",
        ...     {"invalid": "data"},
        ...     ValidationError("Missing required field")
        ... )
    """

    def __init__(
        self,
        model_name: str,
        data: Any = None,
        original_error: Exception | None = None,
    ) -> None:
        """Initialize DeserializationError.

        Args:
            model_name: Name of the model class that failed to deserialize.
            data: The raw database data that could not be deserialized.
                Defaults to None.
            original_error: The underlying exception that caused the failure.
                Defaults to None.
        """
        self.model_name = model_name
        self.data = data
        self.original_error = original_error
        message = f"Failed to deserialize {model_name} from database"
        if data is not None:
            message = f"{message}. Data: {data!r}"
        if original_error:
            message = f"{message}. Error: {original_error}"
        super().__init__(message)
