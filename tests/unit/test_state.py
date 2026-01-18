"""Unit tests for MutableState."""

from __future__ import annotations

from sqlatypemodel.mixin.state import MutableState


class TestStateLogic:
    """Test MutableState logic."""

    def test_unlink_missing_child(self) -> None:
        """Test unlink when child has no _parents attribute."""

        class PlainObj:
            pass

        parent = PlainObj()
        state = MutableState(parent)

        # Should not raise
        state.unlink(PlainObj())

    def test_link_missing_parents(self) -> None:
        """Test link when child has no _parents attribute."""

        class PlainObj:
            pass

        parent = PlainObj()
        state = MutableState(parent)

        # Should not raise/do anything
        state.link(PlainObj(), "key")
