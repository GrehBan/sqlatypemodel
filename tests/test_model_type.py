"""Tests for ModelType TypeDecorator."""

from typing import Any, cast

import pytest
from pydantic import BaseModel
from sqlalchemy.engine import Dialect

from sqlatypemodel import ModelType
from sqlatypemodel.exceptions import DeserializationError, SerializationError


class SimpleConfig(BaseModel):
    """Simple test model."""

    theme: str
    debug: bool = False


class TestModelTypeInit:
    """Tests for ModelType initialization."""

    def test_init_with_pydantic_model(self) -> None:
        """ModelType should accept Pydantic models."""
        model_type = ModelType(SimpleConfig)
        assert model_type.model is SimpleConfig
        assert callable(model_type.dumps)
        assert callable(model_type.loads)

    def test_no_slots_defined(self) -> None:
        """
        CRITICAL: ModelType must NOT define __slots__.
        SQLAlchemy requires types to be compatible with its internal cloning mechanism.
        """
        assert (
            "__slots__" not in ModelType.__dict__
        ), "ModelType must not define __slots__"

    def test_sqlalchemy_clone_compatibility(self) -> None:
        """
        Simulate SQLAlchemy dialect compilation which clones the type.
        This verifies the fix for: AttributeError: '_SQliteJson' object has no attribute 'dumps'
        """
        original_type = ModelType(SimpleConfig)

        import copy

        cloned_type = copy.copy(original_type)

        assert cloned_type.model is SimpleConfig
        assert cloned_type.dumps is not None
        assert cloned_type.loads is not None

    def test_init_without_serializers_raises(self) -> None:
        """ModelType should raise for non-Pydantic without serializers."""

        class PlainClass:
            pass

        with pytest.raises(ValueError, match="Cannot resolve serialization"):
            ModelType(PlainClass)  # type: ignore[type-var]


class TestModelTypeSerialization:
    """Tests for serialization/deserialization."""

    def test_process_bind_param_model(self) -> None:
        """Pydantic model should serialize to dict."""
        model_type = ModelType(SimpleConfig)
        config = SimpleConfig(theme="dark", debug=True)
        # We pass None as dialect for testing, casting to ensure mypy happiness
        result = model_type.process_bind_param(config, cast(Dialect, None))
        assert result == {"theme": "dark", "debug": True}

    def test_process_result_value_dict(self) -> None:
        """Dict should deserialize to Pydantic model."""
        model_type = ModelType(SimpleConfig)
        result = model_type.process_result_value(
            {"theme": "light", "debug": False}, cast(Dialect, None)
        )
        assert isinstance(result, SimpleConfig)
        assert result.theme == "light"
        assert result.debug is False

    def test_process_bind_param_error(self) -> None:
        """Serialization errors should raise SerializationError."""

        class BadModel(BaseModel):
            value: str

            def model_dump(self, **kwargs: Any) -> dict[str, Any]:
                raise ValueError("Serialization failed")

        model_type = ModelType(
            BadModel,
            json_dumps=lambda x: x.model_dump(),
        )
        with pytest.raises(SerializationError, match="Failed to serialize"):
            model_type.process_bind_param(
                BadModel(value="test"), cast(Dialect, None)
            )

    def test_process_result_value_error(self) -> None:
        """Deserialization errors should raise DeserializationError."""
        model_type = ModelType(SimpleConfig)
        with pytest.raises(
            DeserializationError, match="Failed to deserialize"
        ):
            model_type.process_result_value(
                {"invalid": "data"}, cast(Dialect, None)
            )
