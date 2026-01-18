"""Unit tests for inspection utilities."""

from __future__ import annotations

from sqlatypemodel.mixin import inspection


class TestInspectionCoverage:
    """Test inspection edge cases."""

    def test_extract_attrs_slots_only(self) -> None:
        """Test extraction from object with only slots."""

        class Slotted:
            __slots__ = ("a", "b")

            def __init__(self):
                self.a = 1

        obj = Slotted()
        attrs = inspection.extract_attrs_to_scan(obj)
        assert attrs["a"] == 1
        assert "b" not in attrs

    def test_descriptor_property_check(self) -> None:
        """Test descriptor property detection."""

        class Desc:
            @property
            def prop(self):
                return 1

            # Functions are descriptors in Python, so they return True here
            def method(self):
                pass

            # Plain attribute is NOT a descriptor
            attr = 1

        assert inspection.is_descriptor_property(Desc.prop)
        assert inspection.is_descriptor_property(Desc.method)
        assert not inspection.is_descriptor_property(Desc.attr)
        assert not inspection.is_descriptor_property(None)
