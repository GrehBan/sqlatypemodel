"""Unit tests for event propagation."""

from __future__ import annotations

from unittest.mock import patch

from sqlatypemodel.mixin import events
from sqlatypemodel.mixin.state import MutableState


class TestEventPropagation:
    """Test event propagation edge cases."""

    def test_race_condition_retry(self) -> None:
        """Test safe_changed retry logic on dictionary modification."""

        class MockParent:
            def changed(self):
                # Mock implementation for testing
                pass

        class MockTrackable:
            def __init__(self):
                self._parents = {MutableState(MockParent()): "key"}

        obj = MockTrackable()

        # Create a dict that fails iteration once
        class FailDict(dict):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.fail_count = 0

            def items(self):
                if self.fail_count == 0:
                    self.fail_count += 1
                    raise RuntimeError("dictionary changed size")
                return super().items()

        obj._parents = FailDict({MutableState(MockParent()): "key"})

        # Should succeed after retry
        events.safe_changed(obj)
        assert obj._parents.fail_count == 1

    def test_parent_garbage_collected(self) -> None:
        """Test when parent reference is dead."""

        class MockTrackable:
            _parents = {}

        obj = MockTrackable()

        # Create a state with a dead reference
        class DeadParent:
            pass

        p = DeadParent()
        state = MutableState(p)
        obj._parents[state] = "key"

        del p
        # Force GC not guaranteed here, but weakref should return None
        # Verify safe_changed handles None parent
        # We simulate it by mocking ref() -> None

        with patch.object(state, "ref", return_value=None):
            # Should simply ignore and continue
            events.safe_changed(obj)
