"""Tests for LazyMutableMixin behavior."""

import pickle

import pytest
from sqlalchemy.ext.mutable import MutableDict, MutableList
from tests.conftest import LazyModel


class TestLazyMixin:
    """Tests for LazyMutableMixin Just-In-Time wrapping logic."""

    def test_init_is_truly_lazy(self) -> None:
        """Verify that initialization does not wrap raw data immediately."""
        raw_data = {"key": "value"}
        model = LazyModel(data=raw_data)

        internal_storage = model.__dict__["data"]

        assert type(internal_storage) is dict  # noqa: E721
        assert internal_storage == raw_data
        assert not hasattr(internal_storage, "_parents")

    def test_jit_wrapping_on_read(self) -> None:
        """Verify JIT wrapping occurs when an attribute is accessed."""
        model = LazyModel(data={"a": 1})

        wrapped = model.data

        assert isinstance(wrapped, MutableDict)
        assert wrapped == {"a": 1}

        assert wrapped._parents[model._state] == "data"

        assert isinstance(model.__dict__["data"], MutableDict)

    def test_write_wraps_immediately(self) -> None:
        """Verify that setters wrap data immediately (eager write)."""
        model = LazyModel()
        new_list = [1, 2, 3]

        model.items = new_list

        assert isinstance(model.items, MutableList)
        assert isinstance(model.__dict__["items"], MutableList)
        assert model.items._parents[model._state] == "items"

    def test_change_notification_works_lazy(self) -> None:
        """Verify that modifying lazily loaded data triggers mutations."""
        model = LazyModel(data={"nested": {"x": 100}})

        # Access the data to trigger wrapping
        initial_x = model.data["nested"]["x"]

        # Modify the nested value
        model.data["nested"]["x"] = 200

        # Verify the change was applied
        assert model.data["nested"]["x"] == 200
        assert model.data["nested"]["x"] != initial_x

    def test_system_attrs_ignored(self) -> None:
        """Verify that access to system attributes does not trigger recursion."""
        model = LazyModel()

        assert isinstance(LazyModel.model_fields, dict)
        assert isinstance(model.__dict__, dict)

        with pytest.raises(AttributeError):
            _ = model.non_existent_field

    def test_lazy_list_behavior(self) -> None:
        """Verify JIT wrapping works specifically for lists."""
        model = LazyModel(items=[1, 2])

        assert type(model.__dict__["items"]) is list  # noqa: E721

        model.items.append(3)

        assert model.items == [1, 2, 3]
        assert isinstance(model.items, MutableList)

    def test_pickle_restore_tracking(self) -> None:
        """Verify that tracking persists after pickling/unpickling."""
        original = LazyModel(data={"k": "v"})
        _ = original.data

        restored = pickle.loads(pickle.dumps(original))

        assert restored.data == {"k": "v"}

        # Verify that mutations still work on restored model
        restored.data["k"] = "new_v"
        assert restored.data["k"] == "new_v"
