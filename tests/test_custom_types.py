"""Tests for third-party types (attrs, dataclasses)."""

import sys
from dataclasses import dataclass, field
from typing import Any, cast

import pytest

from sqlatypemodel import MutableMixin
from sqlatypemodel.mixin.protocols import Trackable

try:
    from attrs import define as attrs_define
except ImportError:
    attrs_define = None


@dataclass
class DataClassModel(MutableMixin):
    """Standard dataclass."""
    data: list[int]
    meta: dict[str, Any]


class TestDataclassSupport:
    """Tests for standard python dataclasses."""

    def test_change_tracking(self) -> None:
        model = DataClassModel(data=[1], meta={})
        
        # Access via state
        assert model._state in cast(Trackable, model.data)._parents

    def test_mutation_triggers_change(self) -> None:
        model = DataClassModel(data=[1], meta={})
        from unittest.mock import patch
        
        with patch.object(model, "changed") as mock_changed:
            model.data.append(2)
            mock_changed.assert_called()


class TestAttrsSupport:
    """Tests for 'attrs' library support."""

    def test_attrs_change_tracking(self) -> None:
        if attrs_define is None:
            return

        @attrs_define
        class AttrsModel(MutableMixin):
            tags: list[str]

        model = AttrsModel(tags=["a"])
        assert model._state in cast(Trackable, model.tags)._parents

    def test_attrs_unhashable_is_fine(self) -> None:
        """Verify that unhashable attrs classes still work."""
        if attrs_define is None:
            return

        @attrs_define(eq=True, frozen=False, slots=False)
        class AttrsEqModel(MutableMixin):
            id: int

        model = AttrsEqModel(id=1)
        
        # Model itself raises TypeError on hash (standard behavior for eq=True frozen=False)
        with pytest.raises(TypeError):
            hash(model)
            
        # But its state MUST be hashable
        assert isinstance(hash(model._state), int)