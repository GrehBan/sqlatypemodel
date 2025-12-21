"""Tests for compatibility with Dataclasses, Attrs, and Plain classes."""

from dataclasses import dataclass
from typing import Any, List

import pytest
from sqlalchemy.ext.mutable import MutableDict, MutableList

from sqlatypemodel import MutableMixin

try:
    from attrs import define
except ImportError:
    define = None


@dataclass
class DataClassModel(MutableMixin):
    """A standard Python Dataclass inheriting from MutableMixin."""
    data: List[int]
    meta: dict[str, Any]


class PlainModel(MutableMixin):
    """A plain Python class inheriting from MutableMixin."""

    def __init__(self, data: list[int], meta: dict[str, Any]) -> None:
        """Initialize the plain model manually."""
        self.data = data
        self.meta = meta


class TestDataclassSupport:
    """Tests for Python Dataclasses compatibility."""

    def test_initialization_wraps_collections(self) -> None:
        """Verify that collections are wrapped upon dataclass initialization."""
        model = DataClassModel(data=[1, 2], meta={"key": "val"})

        assert isinstance(model.data, MutableList)
        assert isinstance(model.meta, MutableDict)
        assert model.data == [1, 2]

    def test_identity_hashing(self) -> None:
        """Verify that dataclasses rely on identity hashing, not content."""
        m1 = DataClassModel(data=[1], meta={})
        m2 = DataClassModel(data=[1], meta={})

        assert m1 == m2
        assert hash(m1) != hash(m2)
        
        assert isinstance(hash(m1), int)

    def test_change_tracking(self) -> None:
        """Verify that mutations inside dataclasses trigger tracking."""
        model = DataClassModel(data=[1], meta={})

        assert model in model.data._parents
        assert model.data._parents[model] == "data"


class TestPlainClassSupport:
    """Tests for standard Python classes compatibility."""

    def test_initialization_wraps_collections(self) -> None:
        """Verify that collections are wrapped upon plain class initialization."""
        model = PlainModel(data=[10, 20], meta={"a": 1})

        assert isinstance(model.data, MutableList)
        assert isinstance(model.meta, MutableDict)

    def test_setattr_hooks(self) -> None:
        """Verify that __setattr__ hook works for plain assignments."""
        model = PlainModel(data=[], meta={})
        new_list = [1, 2, 3]

        model.data = new_list

        assert isinstance(model.data, MutableList)
        assert model.data._parents[model] == "data"

    def test_identity_hashing(self) -> None:
        """Verify identity hashing for plain classes."""
        m1 = PlainModel(data=[], meta={})
        m2 = PlainModel(data=[], meta={})

        assert hash(m1) != hash(m2)


@pytest.mark.skipif(define is None, reason="attrs library is not installed")
class TestAttrsSupport:
    """Tests for Attrs library compatibility."""

    def test_attrs_initialization(self) -> None:
        """Verify that attrs classes function correctly with MutableMixin."""
        
        @define(slots=False, eq=False)
        class AttrsModel(MutableMixin):
            """An attrs class inheriting from MutableMixin."""
            data: List[int]
            meta: dict[str, Any]

        model = AttrsModel(data=[1, 2], meta={"k": "v"})

        assert isinstance(model.data, MutableList)
        assert isinstance(model.meta, MutableDict)
        assert model.data == [1, 2]

    def test_attrs_hashing_restoration(self) -> None:
        """Verify that MutableMixin restores __hash__ removed by attrs."""
        
        @define(eq=True, frozen=False, slots=False)
        class AttrsEqModel(MutableMixin):
            """An attrs class with equality enabled."""
            id: int

        model = AttrsEqModel(id=1)

        h = hash(model)
        assert isinstance(h, int)
        
        model2 = AttrsEqModel(id=1)
        assert hash(model) != hash(model2)