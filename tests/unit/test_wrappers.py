"""Unit tests for dataclass and attrs wrappers."""

from __future__ import annotations

import pytest

from sqlatypemodel.util import dataclasses as sa_dataclasses


class TestUtilWrappers:
    """Test utility wrappers for dataclasses and attrs."""

    def test_dataclass_wrapper(self) -> None:
        """Verify dataclass wrapper applies safe defaults."""

        @sa_dataclasses.dataclass
        class SafeDC:
            x: int

        assert not hasattr(SafeDC, "__slots__")
        d1 = SafeDC(1)
        d2 = SafeDC(1)
        assert d1 != d2  # Identity check (eq=False)

    def test_attrs_wrapper(self) -> None:
        """Verify attrs wrapper applies safe defaults."""
        try:
            import importlib.util

            if importlib.util.find_spec("attrs") is None:
                pytest.skip("attrs not installed")
        except (ImportError, ValueError):
            pytest.skip("attrs not installed")

        from sqlatypemodel.util.attrs import define as my_define

        @my_define
        class MyAttrs:
            x: int

        i1 = MyAttrs(1)
        i2 = MyAttrs(1)
        assert i1 != i2  # Identity equality enforced
