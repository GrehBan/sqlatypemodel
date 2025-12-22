"""Tests for standard MutableMixin functionality."""

from sqlalchemy.ext.mutable import MutableDict, MutableList

from tests.conftest import EagerModel


class TestMutableMixinIdentity:
    """Tests for object identity and hashing."""

    def test_hash_is_identity_based(self) -> None:
        """Verify that hash relies on object ID, ensuring stability."""
        m1 = EagerModel(data=["a"])
        m2 = EagerModel(data=["a"])

        assert m1 != m2
        assert hash(m1) != hash(m2)

        original_hash = hash(m1)
        m1.data.append("b")
        assert hash(m1) == original_hash


class TestMutableWrapping:
    """Tests for automatic collection wrapping."""

    def test_wraps_lists_and_dicts(self) -> None:
        """Verify that standard collections are converted to mutable ones."""
        model = EagerModel(data=["item"], meta={"key": "val"})

        assert isinstance(model.data, MutableList)
        assert isinstance(model.meta, MutableDict)

        assert model in model.data._parents
        assert model in model.meta._parents

    def test_optimization_short_circuit(self) -> None:
        """Verify that already wrapped objects are not re-wrapped."""
        model = EagerModel()
        existing_list = MutableList(["a", "b"])

        model.data = existing_list

        assert model.data is existing_list
        assert model in existing_list._parents