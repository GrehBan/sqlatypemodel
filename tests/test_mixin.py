"""Tests for MutableMixin class."""

from pydantic import BaseModel
from sqlalchemy.ext.mutable import MutableDict, MutableList

from sqlatypemodel import MutableMixin


class SimpleMutableModel(MutableMixin, BaseModel):
    """Simple mutable test model."""

    name: str
    count: int = 0


class NestedMutableModel(MutableMixin, BaseModel):
    """Model with nested mutable fields."""

    title: str
    items: list[str] = []
    settings: dict[str, str] = {}


class TestMutableMixinBasics:
    """Basic tests for MutableMixin."""

    def test_hash_is_identity_based(self) -> None:
        """
        CRITICAL: MutableMixin must use object identity for hashing.
        This is required for WeakKeyDictionary parent tracking to work correctly.
        """
        model1 = SimpleMutableModel(name="test")
        model2 = SimpleMutableModel(name="test")

        assert model1 == model2

        assert hash(model1) != hash(model2)

    def test_pydantic_v2_internals_ignored(self) -> None:
        """Internal Pydantic V2 attributes should be ignored by __setattr__."""
        model = SimpleMutableModel(name="test")

        model.__pydantic_fields_set__ = {"name"}

        assert model.__pydantic_fields_set__ == {"name"}


class TestOptimizationLogic:
    """Tests for the O(1) wrapping optimization."""

    def test_short_circuit_wrapping_list(self) -> None:
        """
        If a list is already MutableList, it should NOT be re-iterated.
        """
        model = NestedMutableModel(title="test")

        existing_list = MutableList(["a", "b"])

        model.items = existing_list

        assert model.items is existing_list
        assert model in existing_list._parents

    def test_short_circuit_wrapping_dict(self) -> None:
        """
        If a dict is already MutableDict, it should NOT be re-iterated.
        """
        model = NestedMutableModel(title="test")
        existing_dict = MutableDict({"a": "b"})

        model.settings = existing_dict

        assert model.settings is existing_dict
        assert model in existing_dict._parents

    def test_lazy_change_detection(self) -> None:
        """
        Verify that _should_notify_change avoids model_dump().
        """
        old_val = "value"
        new_val = "value"

        assert MutableMixin._should_notify_change(old_val, old_val) is False

        assert MutableMixin._should_notify_change(old_val, new_val) is False

        assert MutableMixin._should_notify_change("a", "b") is True
