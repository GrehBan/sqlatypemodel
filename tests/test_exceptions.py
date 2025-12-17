"""Tests for custom exceptions."""

import pytest

from sqlatypemodel.exceptions import (
    DeserializationError,
    SerializationError,
    SQLATypeModelError,
)


class TestExceptionHierarchy:
    """Tests for exception inheritance."""

    def test_serialization_error_inherits_base(self):
        """SerializationError should inherit from SQLATypeModelError."""
        assert issubclass(SerializationError, SQLATypeModelError)

    def test_deserialization_error_inherits_base(self):
        """DeserializationError should inherit from SQLATypeModelError."""
        assert issubclass(DeserializationError, SQLATypeModelError)

    def test_catch_all_library_errors(self):
        """All errors should be catchable with base class."""
        with pytest.raises(SQLATypeModelError):
            raise SerializationError("Model")

        with pytest.raises(SQLATypeModelError):
            raise DeserializationError("Model")


class TestSerializationError:
    """Tests for SerializationError."""

    def test_basic_message(self):
        """Should format basic message correctly."""
        error = SerializationError("MyModel")
        assert "Failed to serialize MyModel" in str(error)

    def test_with_original_error(self):
        """Should include original error in message."""
        original = ValueError("bad value")
        error = SerializationError("MyModel", original)
        assert "MyModel" in str(error)
        assert "bad value" in str(error)
        assert error.original_error is original

    def test_attributes(self):
        """Should store attributes correctly."""
        error = SerializationError("TestModel")
        assert error.model_name == "TestModel"
        assert error.original_error is None


class TestDeserializationError:
    """Tests for DeserializationError."""

    def test_basic_message(self):
        """Should format basic message correctly."""
        error = DeserializationError("MyModel")
        assert "Failed to deserialize MyModel" in str(error)

    def test_with_data(self):
        """Should include data in message."""
        data = {"key": "value"}
        error = DeserializationError("MyModel", data)
        assert "MyModel" in str(error)
        assert "key" in str(error)
        assert error.data == data

    def test_with_all_params(self):
        """Should handle all parameters."""
        data = {"field": "value"}
        original = TypeError("type error")
        error = DeserializationError("MyModel", data, original)
        assert error.model_name == "MyModel"
        assert error.data == data
        assert error.original_error is original
        assert "type error" in str(error)
