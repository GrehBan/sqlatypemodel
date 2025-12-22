"""Tests for compatibility with Dataclasses, Attrs, and Plain classes."""

from dataclasses import dataclass
from typing import Any, cast

import pytest
from sqlalchemy.ext.mutable import MutableDict, MutableList

from sqlatypemodel import MutableMixin
from sqlatypemodel.mixin.protocols import Trackable

try:
    from attrs import define as attrs_define
except ImportError:
    attrs_define = None # type: ignore [assignment]

@dataclass
class DataClassModel(MutableMixin):
    """A standard Python Dataclass inheriting from MutableMixin."""
    data: list[int]
    meta: dict[str, Any]


class TestDataclassSupport:
    """Tests for Python Dataclasses compatibility."""

    def test_initialization_wraps_collections(self) -> None:
        model = DataClassModel(data=[1, 2], meta={"key": "val"})

        assert isinstance(model.data, MutableList)
        assert isinstance(model.meta, MutableDict)
        assert model.data == [1, 2]

    def test_identity_hashing(self) -> None:
        m1 = DataClassModel(data=[1], meta={})
        m2 = DataClassModel(data=[1], meta={})
        assert m1 == m2
        assert hash(m1) != hash(m2)
        assert isinstance(hash(m1), int)

    def test_change_tracking(self) -> None:
        model = DataClassModel(data=[1], meta={})

        tracked_data = cast(Trackable, model.data)
        
        assert hasattr(tracked_data, "_parents")
        assert model in tracked_data._parents
        assert tracked_data._parents[model] == "data"


@pytest.mark.skipif(attrs_define is None, reason="attrs library is not installed")
class TestAttrsSupport:
    """Tests for Attrs library compatibility."""

    def test_attrs_initialization(self) -> None:
        if attrs_define is None:
            return

        @attrs_define(slots=False, eq=False)
        class AttrsModel(MutableMixin):
            data: list[int]
            meta: dict[str, Any]

        model = AttrsModel(data=[1, 2], meta={"k": "v"})
        assert isinstance(model.data, MutableList)

    def test_attrs_hashing_restoration(self) -> None:
        if attrs_define is None:
            return

        @attrs_define(eq=True, frozen=False, slots=False)
        class AttrsEqModel(MutableMixin):
            id: int

        model = AttrsEqModel(id=1)
        assert isinstance(hash(model), int)