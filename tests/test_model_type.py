"""Tests for SQLAlchemy TypeDecorator implementation."""

import pytest
from typing import Any, cast
from pydantic import BaseModel
from sqlalchemy.engine import Dialect
from sqlatypemodel import ModelType
from sqlatypemodel.exceptions import SerializationError, DeserializationError

class Config(BaseModel):
    """Simple Pydantic model for testing."""
    theme: str
    debug: bool = False

class TestModelType:
    """Tests for ModelType serialization logic."""

    def test_init(self) -> None:
        """Verify initialization sets attributes correctly."""
        mt = ModelType(Config)
        assert mt.model is Config
        assert mt.python_type is Config

    def test_process_bind_param(self) -> None:
        """Verify serialization from object to dictionary."""
        mt = ModelType(Config)
        obj = Config(theme="dark")
        
        result = mt.process_bind_param(obj, cast(Dialect, None))
        assert result == {"theme": "dark", "debug": False}

        assert mt.process_bind_param(None, cast(Dialect, None)) is None

        raw_dict = {"theme": "light", "debug": True}
        assert mt.process_bind_param(raw_dict, cast(Dialect, None)) == raw_dict

    def test_process_result_value(self) -> None:
        """Verify deserialization from dictionary/string to object."""
        mt = ModelType(Config)
        
        res = mt.process_result_value({"theme": "dark"}, cast(Dialect, None))
        assert isinstance(res, Config)
        assert res.theme == "dark"

        res_str = mt.process_result_value('{"theme": "light"}', cast(Dialect, None))
        assert isinstance(res_str, Config)
        assert res_str.theme == "light"

    def test_errors(self) -> None:
        """Verify that invalid data triggers custom exceptions."""
        mt = ModelType(Config)
        
        with pytest.raises(DeserializationError):
            mt.process_result_value("invalid json", cast(Dialect, None))