"""Tests for standard MutableMixin functionality."""

from sqlalchemy.ext.mutable import MutableDict, MutableList

from tests.conftest import EagerModel


class TestMutableMixinIdentity:
    """Tests for object identity and state tracking."""

    def test_state_identity_stability(self) -> None:
        """Verify that _state is stable and unique per instance."""
        m1 = EagerModel(data=["a"])
        m2 = EagerModel(data=["a"])

        assert m1 is not m2
        assert m1._state is not m2._state
        
        # State should be hashable and stable
        assert hash(m1._state) != hash(m2._state)
        
        s1 = m1._state
        m1.data.append("b")
        assert m1._state is s1  # State instance persists


class TestMutableWrapping:
    """Tests for automatic collection wrapping."""

    def test_wraps_lists_and_dicts(self) -> None:
        """Verify that standard collections are converted to mutable ones."""
        model = EagerModel(data=["item"], meta={"key": "val"})

        assert isinstance(model.data, MutableList)
        assert isinstance(model.meta, MutableDict)

        assert model._state in model.data._parents
        assert model.data._parents[model._state] == "data"
        
        assert model._state in model.meta._parents
        assert model.meta._parents[model._state] == "meta"

    def test_optimization_short_circuit(self) -> None:
        """Verify that already wrapped objects are not re-wrapped."""
        model = EagerModel()
        existing_list = MutableList(["a", "b"])

        model.data = existing_list

        assert model.data is existing_list
        assert model._state in existing_list._parents