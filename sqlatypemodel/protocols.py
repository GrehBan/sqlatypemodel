from typing import Protocol, TypeVar, runtime_checkable, Any, Self, Type

T = TypeVar("T", bound="PydanticModelProto")


@runtime_checkable
class PydanticModelProto(Protocol):
    """
    Protocol for Pydantic-like models to enable type-safe serialization
    and deserialization in SQLAlchemy.

    This protocol defines the minimal interface expected from a model:
    - `model_dump` to serialize the model into a dictionary.
    - `model_validate` to deserialize a dictionary into a model instance.
    """

    def model_dump(self) -> dict[str, Any]:
        """
        Serialize the model into a JSON-compatible dictionary.

        Returns:
            A dictionary representing the model data.
        """
        ...

    @classmethod
    def model_validate(cls: Type[Self], obj: Any) -> Self:
        """
        Create a model instance from a dictionary or other compatible input.

        Args:
            obj: The input data to validate and convert into a model.

        Returns:
            An instance of the model.
        """
        ...
