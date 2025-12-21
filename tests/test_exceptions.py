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
        assert issubclass(SerializationError, SQLATypeModelError)
        assert issubclass(DeserializationError, SQLATypeModelError)

    def test_catch_all(self) -> None:
        with pytest.raises(SQLATypeModelError):
            raise SerializationError("Model")


class TestSerializationError:
    def test_message_formatting(self) -> None:
        error = SerializationError("MyModel")
        assert "Failed to serialize MyModel" in str(error)

    def test_with_original_error(self) -> None:
        original = ValueError("bad value")
        error = SerializationError("MyModel", original)
        assert error.original_error is original
        assert "bad value" in str(error)


class TestDeserializationError:
    def test_message_formatting(self) -> None:
        data = {"key": "val"}
        error = DeserializationError("MyModel", data)
        assert "Failed to deserialize MyModel" in str(error)
        assert error.data == data