"""Protocol definitions for Pydantic-compatible models.

This module defines the structural typing protocols that allow sqlatypemodel
to work with any class that implements the Pydantic model interface, not just
actual Pydantic BaseModel subclasses.

Example:
    >>> from sqlatypemodel.protocols import PydanticModelProtocol
    >>> 
    >>> class CustomModel:
    ...     def model_dump(self, mode: str = "python") -> dict:
    ...         return {"field": self.field}
    ...     
    ...     @classmethod
    ...     def model_validate(cls, obj):
    ...         instance = cls()
    ...         instance.field = obj["field"]
    ...         return instance
    >>> 
    >>> # CustomModel now conforms to PydanticModelProtocol
    >>> isinstance(CustomModel(), PydanticModelProtocol)
    True
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

__all__ = (
    "PydanticModelProtocol",
    "PT",
)


@runtime_checkable
class PydanticModelProtocol(Protocol):
    """Protocol defining the minimal interface for Pydantic-compatible models.

    This protocol enables type-safe serialization and deserialization
    in SQLAlchemy for any class that implements:
    - `model_dump()` for serialization to dictionary
    - `model_validate()` for deserialization from dictionary

    The protocol is runtime-checkable, allowing isinstance() checks.

    Attributes:
        This protocol does not define any attributes, only methods.

    Example:
        >>> from pydantic import BaseModel
        >>> 
        >>> class Config(BaseModel):
        ...     theme: str
        ...     debug: bool = False
        >>> 
        >>> # Pydantic models automatically conform
        >>> isinstance(Config(theme="dark"), PydanticModelProtocol)
        True
    """

    def model_dump(self, *, mode: str = "python") -> dict[str, Any]:
        """Serialize the model into a dictionary.

        Args:
            mode: Serialization mode. Common values are "python" (default)
                  and "json" for JSON-compatible output.

        Returns:
            A dictionary representation of the model data.

        Example:
            >>> config = Config(theme="dark", debug=True)
            >>> config.model_dump()
            {'theme': 'dark', 'debug': True}
            >>> config.model_dump(mode="json")
            {'theme': 'dark', 'debug': True}
        """
        ...

    @classmethod
    def model_validate(cls, obj: Any) -> "PydanticModelProtocol":
        """Create a model instance from input data.

        This class method validates and converts input data (typically
        a dictionary) into an instance of the model.

        Args:
            obj: The input data to validate. Usually a dictionary,
                 but implementations may accept other types.

        Returns:
            A validated instance of the model.

        Raises:
            ValidationError: If the input data is invalid.

        Example:
            >>> data = {"theme": "light", "debug": False}
            >>> config = Config.model_validate(data)
            >>> config.theme
            'light'
        """
        ...


PT = TypeVar("PT", bound=PydanticModelProtocol)
