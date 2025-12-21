"""Tests for protocol conformance."""

from typing import Any

from pydantic import BaseModel

from sqlatypemodel.model_type.protocols import PydanticModelProtocol


class TestPydanticModelProtocol:
    """Tests for runtime protocol checking."""

    def test_pydantic_basemodel_conforms(self) -> None:
        """Verify that standard Pydantic models conform."""
        class Config(BaseModel):
            theme: str

        config = Config(theme="dark")
        assert isinstance(config, PydanticModelProtocol)

    def test_custom_class_conforms(self) -> None:
        """Verify that custom classes with correct methods conform."""
        class CustomModel:
            def model_dump(self, mode: str = "python") -> dict[str, Any]:
                return {}

            @classmethod
            def model_validate(cls, obj: dict[str, Any]) -> "CustomModel":
                return cls()

        model = CustomModel()
        assert isinstance(model, PydanticModelProtocol)

    def test_plain_class_not_conforms(self) -> None:
        """Verify that empty classes do not conform."""
        class PlainClass:
            pass

        assert not isinstance(PlainClass(), PydanticModelProtocol)