"""Tests for custom exceptions hierarchy."""

import pytest
from sqlatypemodel.exceptions import (
    DeserializationError,
    SerializationError,
    SQLATypeModelError,
)

class TestExceptionHierarchy:
    """Tests to verify exception inheritance structure."""

    def test_inheritance(self) -> None:
        """Verify that specific errors inherit from the base library error."""
        assert issubclass(SerializationError, SQLATypeModelError)
        assert issubclass(DeserializationError, SQLATypeModelError)

    def test_catch_all(self) -> None:
        """Verify that the base exception catches all specific errors."""
        with pytest.raises(SQLATypeModelError):
            raise SerializationError("Model")

        with pytest.raises(SQLATypeModelError):
            raise DeserializationError("Model")

class TestSerializationError:
    """Tests for SerializationError behavior."""

    def test_message_formatting(self) -> None:
        """Verify the error message contains the model name."""
        error = SerializationError("MyModel")
        assert "Failed to serialize MyModel" in str(error)

    def test_with_original_error(self) -> None:
        """Verify that the original cause is preserved."""
        original = ValueError("bad value")
        error = SerializationError("MyModel", original)
        assert error.original_error is original
        assert "bad value" in str(error)

class TestDeserializationError:
    """Tests for DeserializationError behavior."""

    def test_message_formatting(self) -> None:
        """Verify the error message contains details."""
        data = {"key": "val"}
        error = DeserializationError("MyModel", data)
        assert "Failed to deserialize MyModel" in str(error)
        assert error.data == data