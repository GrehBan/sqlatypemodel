"""Unit tests for Pickle protocol support."""

import pickle

from pydantic import BaseModel, Field

from sqlatypemodel import MutableMixin
from sqlatypemodel.mixin import serialization


class PickleModel(MutableMixin, BaseModel):
    """Test model for pickling."""
    tags: list[str] = Field(default_factory=list)


class TestPickleSupport:
    """Tests for __getstate__ and __setstate__ logic."""

    def test_pickle_roundtrip(self) -> None:
        """Verify object survives round-trip serialization."""
        original = PickleModel(tags=["a"])
        dumped = pickle.dumps(original)
        restored = pickle.loads(dumped)

        assert restored.tags == ["a"]
        assert restored is not original

        assert hasattr(restored, "_parents")
        assert len(restored._parents) == 0

    def test_tracking_after_unpickle(self) -> None:
        """Verify change tracking works on restored objects."""
        original = PickleModel()
        restored = pickle.loads(pickle.dumps(original))

        restored.tags.append("new")

        assert restored in restored.tags._parents

    def test_manual_setstate(self) -> None:
        """Verify fallback mechanism for state restoration."""
        model = PickleModel.__new__(PickleModel)
        state = {"tags": ["manual"]}

        serialization.manual_setstate(model, state)

        assert model.tags == ["manual"]