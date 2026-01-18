"""Unit tests for sentinel objects."""

from __future__ import annotations

from sqlatypemodel.util._sentinel import MISSING, _MissingSentinel


class TestSentinels:
    """Test sentinel objects."""

    def test_sentinel_singleton(self) -> None:
        """Test that MISSING is a singleton and behaves correctly."""
        assert MISSING is not None
        assert bool(MISSING) is False
        assert repr(MISSING) == "MISSING"

        # Should be the correct type
        assert isinstance(MISSING, _MissingSentinel)
