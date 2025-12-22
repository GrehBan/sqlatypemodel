"""Tests for SQLAlchemy TypeDecorator implementation."""

from typing import cast

import pytest
from pydantic import BaseModel
from sqlalchemy.engine import Dialect

from sqlatypemodel import ModelType
from sqlatypemodel.exceptions import DeserializationError


class Config(BaseModel):
    """Simple Pydantic model for testing."""
    theme: str
    debug: bool = False


class TestModelType:
    """Tests for ModelType serialization logic."""

    @pytest.fixture
    def model_type(self) -> ModelType[Config]:
        return ModelType(Config)

    def test_init(self, model_type: ModelType[Config]) -> None:
        """Verify initialization sets attributes correctly."""
        assert model_type.model is Config
        assert model_type.python_type is Config

    def test_process_bind_param(self, model_type: ModelType[Config]) -> None:
        """Verify serialization from object to dictionary."""
        obj = Config(theme="dark")
        dummy_dialect = cast(Dialect, None)

        result = model_type.process_bind_param(obj, dummy_dialect)
        assert result == {"theme": "dark", "debug": False}

        assert model_type.process_bind_param(None, dummy_dialect) is None

        raw_dict = {"theme": "light", "debug": True}
        assert model_type.process_bind_param(raw_dict, dummy_dialect) == raw_dict

    def test_process_result_value(self, model_type: ModelType[Config]) -> None:
        """Verify deserialization from dictionary/string to object."""
        dummy_dialect = cast(Dialect, None)

        res = model_type.process_result_value({"theme": "dark"}, dummy_dialect)
        assert isinstance(res, Config)
        assert res.theme == "dark"

        res_str = model_type.process_result_value('{"theme": "light"}', dummy_dialect)
        assert isinstance(res_str, Config)
        assert res_str.theme == "light"

    def test_errors(self, model_type: ModelType[Config]) -> None:
        """Verify that invalid data triggers custom exceptions."""
        with pytest.raises(DeserializationError):
            model_type.process_result_value("invalid json", cast(Dialect, None))