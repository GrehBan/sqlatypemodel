"""Property-based testing using Hypothesis for sqlatypemodel.

This module provides comprehensive property-based tests that verify the
correctness of sqlatypemodel under a wide range of input scenarios.
"""

from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.strategies import composite, integers, lists
from tests.factories import EagerTestModel, LazyTestModel


# Custom strategies for generating test data
@composite
def json_serializable_values(draw):
    """Generate values that are JSON serializable."""
    return draw(
        st.one_of(
            st.none(),
            st.booleans(),
            st.integers(
                min_value=-(2**63), max_value=2**63 - 1
            ),  # 64-bit range
            st.floats(allow_nan=False, allow_infinity=False),
            st.text(min_size=1, max_size=10),
            st.datetimes(min_value=datetime(2000, 1, 1)),
            st.uuids(),
        )
    )


def nested_json_strategy(max_depth=3):
    """Generate nested JSON structures with controlled depth."""
    return st.recursive(
        json_serializable_values(),
        lambda children: st.one_of(
            st.lists(children, min_size=0, max_size=3),
            st.dictionaries(
                keys=st.text(min_size=1, max_size=5),
                values=children,
                min_size=0,
                max_size=3,
            ),
        ),
        max_leaves=20,
    )


@composite
def user_model_data(draw):
    """Generate realistic user model data."""
    return {
        "user_id": str(draw(st.uuids())),
        "username": draw(
            st.text(
                min_size=1,
                max_size=20,
                alphabet=st.characters(whitelist_categories=["L", "N"]),
            )
        ),
        "email": draw(st.text(min_size=5, max_size=30)) + "@example.com",
        "is_active": draw(st.booleans()),
        "created_at": draw(
            st.datetimes(min_value=datetime(2000, 1, 1))
        ).isoformat(),
        "settings": draw(
            st.dictionaries(
                keys=st.text(min_size=1, max_size=5),
                values=json_serializable_values(),
                min_size=0,
                max_size=3,
            )
        ),
        "tags": draw(
            st.lists(st.text(min_size=1, max_size=10), min_size=0, max_size=5)
        ),
    }


@composite
def extreme_integer_data(draw):
    """Generate data with extreme integer values."""
    base_data = draw(user_model_data())

    # Add extreme integer values to test 64-bit overflow handling
    extreme_int = draw(
        st.one_of(
            st.integers(
                min_value=2**63, max_value=2**100
            ),  # Too large for 64-bit
            st.integers(
                min_value=-(2**100), max_value=-(2**63)
            ),  # Too small for 64-bit
            st.integers(
                min_value=2**63 - 1, max_value=2**63 - 1
            ),  # Max 64-bit
            st.integers(min_value=-(2**63), max_value=-(2**63)),  # Min 64-bit
        )
    )

    base_data["settings"]["extreme_int"] = extreme_int
    return base_data


@composite
def mutation_operations(draw):
    """Generate mutation operations for testing."""
    operations = []

    # Generate random mutations
    num_operations = draw(integers(min_value=1, max_value=5))

    for _ in range(num_operations):
        op_type = draw(
            st.sampled_from(
                [
                    "append_tag",
                    "update_setting",
                    "remove_tag",
                    "clear_settings",
                ]
            )
        )
        operations.append(op_type)

    return operations


class TestEagerModelPropertyBased:
    """Property-based tests for EagerTestModel."""

    @given(data=user_model_data())
    @settings(max_examples=100, deadline=1000)
    def test_model_creation_roundtrip(self, data):
        """Test that models can be created and serialized correctly."""
        # Create model
        model = EagerTestModel(
            user_id=data["user_id"],
            username=data["username"],
            email=data["email"],
            is_active=data["is_active"],
            created_at=data["created_at"],
            settings=data["settings"],
            tags=data["tags"],
        )

        # Verify model structure
        assert model.user_id == str(data["user_id"])
        assert model.username == data["username"]
        assert model.email == data["email"]
        assert model.is_active == data["is_active"]
        assert model.created_at == data["created_at"]
        assert model.settings == data["settings"]
        assert model.tags == data["tags"]

        # Test serialization
        model_dict = model.model_dump()
        assert isinstance(model_dict, dict)
        assert all(key in model_dict for key in data.keys())

    @given(data=user_model_data(), operations=mutation_operations())
    @settings(max_examples=50, deadline=1000)
    def test_mutation_tracking_properties(self, data, operations):
        """Test that mutation tracking works correctly for various operations."""
        model = EagerTestModel(**data)
        model.tags.copy()
        original_settings = model.settings.copy()

        # Apply mutations
        for op in operations:
            if op == "append_tag":
                new_tag = f"test_tag_{len(model.tags)}"
                model.tags.append(new_tag)
                assert new_tag in model.tags
            elif op == "update_setting":
                model.settings["test_key"] = "test_value"
                assert model.settings["test_key"] == "test_value"
            elif op == "remove_tag" and model.tags:
                original_len = len(model.tags)
                model.tags.pop(0)
                assert len(model.tags) == original_len - 1
            elif op == "clear_settings":
                model.settings.clear()
                assert len(model.settings) == 0

        # Verify that mutations were applied
        if "clear_settings" not in operations:
            assert len(model.settings) >= len(original_settings)

    @given(data=user_model_data())
    @settings(max_examples=50, deadline=1000)
    def test_state_identity_preservation(self, data):
        """Test that model state identity is preserved during operations."""
        model = EagerTestModel(**data)
        original_state = model._state

        # Perform various operations
        model.tags.append("new_tag")
        model.settings["new_key"] = "new_value"

        # State should remain the same
        assert model._state is original_state

    @given(data=extreme_integer_data())
    @settings(max_examples=30, deadline=2000)
    def test_extreme_integer_handling(self, data):
        """Test handling of extreme integer values."""
        try:
            model = EagerTestModel(
                user_id=data["user_id"],
                username=data["username"],
                email=data["email"],
                is_active=data["is_active"],
                created_at=data["created_at"],
                settings=data["settings"],
                tags=data["tags"],
            )
            # Model should be created successfully
            assert model.settings.get("extreme_int") is not None
        except Exception as e:
            # Should handle gracefully, not crash
            assert isinstance(e, ValueError | OverflowError | TypeError)


class TestLazyModelPropertyBased:
    """Property-based tests for LazyTestModel."""

    @given(data=user_model_data())
    @settings(max_examples=100, deadline=1000)
    def test_lazy_model_creation_roundtrip(self, data):
        """Test that lazy models can be created and work correctly."""
        model = LazyTestModel(
            user_id=data["user_id"],
            username=data["username"],
            email=data["email"],
            is_active=data["is_active"],
            created_at=data["created_at"],
            settings=data["settings"],
            tags=data["tags"],
        )

        # Verify model structure
        assert model.user_id == str(data["user_id"])
        assert model.username == data["username"]
        assert model.email == data["email"]

        # Access lazy-loaded fields
        _ = model.tags  # Trigger lazy loading
        _ = model.settings  # Trigger lazy loading

        # Verify after access
        assert model.tags == data["tags"]
        assert model.settings == data["settings"]

    @given(data=user_model_data(), operations=mutation_operations())
    @settings(max_examples=50, deadline=1000)
    def test_lazy_mutation_tracking_properties(self, data, operations):
        """Test that lazy mutation tracking works correctly."""
        model = LazyTestModel(
            user_id=data["user_id"],
            username=data["username"],
            email=data["email"],
            is_active=data["is_active"],
            created_at=data["created_at"],
            settings=data["settings"],
            tags=data["tags"],
        )

        # Access fields to trigger lazy loading
        _ = model.tags
        _ = model.settings

        original_state = model._state

        # Apply mutations
        for op in operations:
            if op == "append_tag":
                new_tag = f"lazy_tag_{len(model.tags)}"
                model.tags.append(new_tag)
                assert new_tag in model.tags
            elif op == "update_setting":
                model.settings["lazy_key"] = "lazy_value"
                assert model.settings["lazy_key"] == "lazy_value"

        # State should remain the same
        assert model._state is original_state


class TestSerializationProperties:
    """Property-based tests for serialization behavior."""

    @given(data=user_model_data())
    @settings(max_examples=100, deadline=1000)
    def test_json_serialization_properties(self, data):
        """Test that models serialize to valid JSON."""
        model = EagerTestModel(**data)

        # Test serialization
        serialized = model.model_dump_json()
        assert isinstance(serialized, str)

        # Test deserialization
        deserialized = json.loads(serialized)
        assert isinstance(deserialized, dict)

        # Verify key properties are preserved
        assert deserialized["user_id"] == model.user_id
        assert deserialized["username"] == model.username
        assert deserialized["email"] == model.email

    @given(data=user_model_data())
    @settings(max_examples=50, deadline=1000)
    def test_nested_structure_preservation(self, data):
        """Test that nested structures are preserved correctly."""
        model = EagerTestModel(**data)

        # Access nested structure
        settings = model.settings

        # Navigate nested structure
        if "nested" in settings:
            nested = settings["nested"]
            if isinstance(nested, dict) and "deep" in nested:
                deep = nested["deep"]
                if isinstance(deep, dict) and "value" in deep:
                    assert isinstance(
                        deep["value"],
                        str | int | float | bool | list | dict | type(None),
                    )


class TestPerformanceProperties:
    """Property-based tests for performance characteristics."""

    @given(data=lists(user_model_data(), min_size=10, max_size=100))
    @settings(max_examples=10, deadline=5000)
    def test_batch_creation_performance(self, data):
        """Test that batch creation is efficient."""
        import time

        start_time = time.perf_counter()
        models = [EagerTestModel(**model_data) for model_data in data]
        creation_time = time.perf_counter() - start_time

        # Should complete within reasonable time (adjust as needed)
        assert creation_time < 1.0  # 1 second for up to 100 models
        assert len(models) == len(data)

        # All models should be valid
        for model, original_data in zip(models, data):
            assert model.user_id == str(original_data["user_id"])
            assert model.username == original_data["username"]

    @given(
        data=user_model_data(),
        num_accesses=integers(min_value=10, max_value=100),
    )
    @settings(max_examples=20, deadline=2000)
    def test_repeated_access_performance(self, data, num_accesses):
        """Test that repeated access is performant."""
        import time

        model = EagerTestModel(**data)

        start_time = time.perf_counter()
        for _ in range(num_accesses):
            _ = model.tags
            _ = model.settings
        access_time = time.perf_counter() - start_time

        # Should be very fast for repeated access
        assert access_time < 0.1  # 100ms for 100 accesses


class TestEdgeCaseProperties:
    """Property-based tests for edge cases."""

    @given(
        username=st.one_of(
            st.just(""),
            st.text(max_size=0),
            st.text(min_size=100, max_size=200),
        ),
        email=st.one_of(
            st.just(""),
            st.text(max_size=0),
            st.text(min_size=100, max_size=300),
        ),
        tags=st.one_of(
            st.just([]),
            st.lists(st.just(""), min_size=0, max_size=10),
            st.lists(
                st.text(min_size=1000, max_size=2000), min_size=0, max_size=5
            ),
        ),
        settings=st.one_of(
            st.just({}),
            st.dictionaries(
                keys=st.just(""),
                values=st.just(""),
                min_size=0,
                max_size=10,
            ),
        ),
    )
    @settings(max_examples=50, deadline=1000)
    def test_edge_case_handling(self, username, email, tags, settings):
        """Test handling of various edge cases."""
        try:
            model = EagerTestModel(
                user_id=str(uuid4()),
                username=username,
                email=email,
                created_at="2024-01-01T00:00:00Z",
                tags=tags,
                settings=settings,
            )

            # Model should handle edge cases gracefully
            assert model.user_id is not None

            # Test mutation on edge cases
            if tags is not None:
                model.tags.append("test")
                assert "test" in model.tags

            if settings is not None:
                model.settings["test"] = "value"
                assert model.settings["test"] == "value"

        except Exception as e:
            # Should handle validation errors gracefully
            assert isinstance(e, ValueError | TypeError)
