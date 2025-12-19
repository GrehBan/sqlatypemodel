"""Tests for MutableMixin functionality and identity logic."""

import pytest
from pydantic import BaseModel
from sqlalchemy.ext.mutable import MutableList, MutableDict
from sqlatypemodel import MutableMixin

class MutableModel(MutableMixin, BaseModel):
    """Local test model implementing MutableMixin."""
    data: list[str] = []
    meta: dict[str, str] = {}

class TestMutableMixinIdentity:
    """Tests for object identity and hashing."""

    def test_hash_is_identity_based(self) -> None:
        """Verify that hash relies on object ID, not content.
        
        This is critical for WeakKeyDictionary to function correctly as
        content-based hashing would break tracking when content changes.
        """
        m1 = MutableModel(data=["a"])
        m2 = MutableModel(data=["a"])
        
        # Pydantic считает их равными по значению
        assert m1 == m2
        
        # Хеши должны быть разными (разные объекты)
        assert hash(m1) != hash(m2)
        
        # FIX: hash(x) не всегда равен id(x) или hash(id(x)).
        # Правильная проверка на identity hash:
        assert hash(m1) == object.__hash__(m1)

class TestMutableWrapping:
    """Tests for automatic collection wrapping."""

    def test_wraps_lists_and_dicts(self) -> None:
        """Verify that standard collections are converted to mutable ones."""
        model = MutableModel()
        model.data = ["item"]
        model.meta = {"key": "val"}

        assert isinstance(model.data, MutableList)
        assert isinstance(model.meta, MutableDict)
        
        assert model in model.data._parents
        assert model in model.meta._parents

    def test_optimization_short_circuit(self) -> None:
        """Verify that already wrapped objects are not re-wrapped."""
        model = MutableModel()
        existing_list = MutableList(["a", "b"])
        
        model.data = existing_list
        
        assert model.data is existing_list
        assert model in existing_list._parents