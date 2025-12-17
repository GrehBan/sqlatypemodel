"""Tests for protocol definitions."""

import pytest
from pydantic import BaseModel

from sqlatypemodel.protocols import PydanticModelProtocol


class TestPydanticModelProtocol:
    """Tests for PydanticModelProtocol."""

    def test_pydantic_basemodel_conforms(self):
        """Pydantic BaseModel should conform to protocol."""
        class Config(BaseModel):
            theme: str

        config = Config(theme="dark")
        assert isinstance(config, PydanticModelProtocol)

    def test_custom_class_with_methods_conforms(self):
        """Custom class with required methods should conform."""
        class CustomModel:
            def __init__(self, value: str = ""):
                self.value = value

            def model_dump(self, mode: str = "python") -> dict:
                return {"value": self.value}

            @classmethod
            def model_validate(cls, obj):
                return cls(obj["value"])

        model = CustomModel("test")
        assert isinstance(model, PydanticModelProtocol)

    def test_class_without_methods_not_conforms(self):
        """Class without methods should not conform."""
        class PlainClass:
            pass

        obj = PlainClass()
        assert not isinstance(obj, PydanticModelProtocol)

    def test_class_with_partial_methods_not_conforms(self):
        """Class with only one method should not conform."""
        class PartialClass:
            def model_dump(self):
                return {}

        obj = PartialClass()
        assert not isinstance(obj, PydanticModelProtocol)


class TestProtocolUsage:
    """Tests for protocol usage in type hints."""

    def test_protocol_as_type_hint(self):
        """Protocol should work as type hint."""
        def serialize(model: PydanticModelProtocol) -> dict:
            return model.model_dump()

        class Config(BaseModel):
            name: str

        config = Config(name="test")
        result = serialize(config)
        assert result == {"name": "test"}
