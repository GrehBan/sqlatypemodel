"""Unit tests for wrapping logic."""

from __future__ import annotations

from sqlatypemodel.mixin import wrapping


class TestWrappingLogic:
    """Test wrapping edge cases."""

    def test_wrap_set(self) -> None:
        """Test wrapping of sets."""

        class MockParent:
            pass

        parent = MockParent()

        s = {1, 2, 3}
        wrapped = wrapping.wrap_mutable(parent, s)
        from sqlalchemy.ext.mutable import MutableSet

        assert isinstance(wrapped, MutableSet)
        assert wrapped == s

    def test_recursion_depth_limit(self) -> None:
        """Test that wrapping stops at max depth."""

        class MockParent:
            _max_nesting_depth = 1

        parent = MockParent()
        data = [[["too_deep"]]]
        # Depth 0: list (wrapped) -> passes max_depth=1
        # Depth 1: list (wrapped) -> passes max_depth=1
        # Depth 2: list (raw) -> exceeds max_depth=1

        wrapped = wrapping.wrap_mutable(parent, data)
        assert hasattr(wrapped, "_parents")  # Top level wrapped
        assert hasattr(wrapped[0], "_parents")  # Level 1 wrapped

        # Level 2 should be raw list because depth > max (1)
        # Verify it is NOT wrapped
        assert not hasattr(wrapped[0][0], "_parents")
        assert isinstance(wrapped[0][0], list)

    def test_wrap_already_tracked_but_unlinked(self) -> None:
        """Test logic when object has _parents but needs wrapping check."""

        # Create a mock trackable
        class TrackableObj:
            _parents = {}

        obj = TrackableObj()

        class MockParent:
            pass

        parent = MockParent()

        # wrap_mutable should return it as is but link it
        res = wrapping.wrap_mutable(parent, obj)
        assert res is obj
        # Should be linked
        state = getattr(parent, "_state", None)
        assert state in obj._parents
