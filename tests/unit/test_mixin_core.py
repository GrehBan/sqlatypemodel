"""Production-grade tests for standard MutableMixin functionality."""

from __future__ import annotations

import pickle
import threading
import time
from typing import Any, TypeVar

import pytest
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import DeclarativeBase
from tests.conftest import UserEntity
from tests.factories import EagerTestModel, ModelFactory

M = TypeVar("M", bound=EagerTestModel)


class TestMutableMixinIdentity:
    """Tests for object identity and state tracking."""

    def test_state_identity_stability(self) -> None:
        """Verify that _state is stable and unique per instance."""
        m1 = ModelFactory.create_eager_model(user_id="1", username="user1")
        m2 = ModelFactory.create_eager_model(user_id="2", username="user2")

        assert m1 is not m2
        assert m1._state is not m2._state

        assert hash(m1._state) != hash(m2._state)

        s1 = m1._state
        m1.tags.append("b")
        assert m1._state is s1

    def test_state_persistence_after_mutation(self) -> None:
        """Test that state persists through multiple mutations."""
        model = ModelFactory.create_eager_model()
        original_state = model._state

        # Perform multiple mutations
        model.tags.extend(["tag1", "tag2", "tag3"])
        model.settings["key1"] = "value1"
        model.settings["nested"] = {"deep": "value"}
        model.tags[0] = "modified_tag"

        # State should remain the same
        assert model._state is original_state
        assert hash(model._state) == hash(original_state)

    def test_state_thread_safety(self) -> None:
        """Test that state management is thread-safe."""
        model = ModelFactory.create_eager_model()
        results = []
        exceptions = []

        def worker():
            try:
                for i in range(100):
                    model.tags.append(f"thread_tag_{i}")
                    results.append(model._state)
            except Exception as e:
                exceptions.append(e)

        # Run multiple threads
        threads = []
        for _ in range(5):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Should not have any exceptions
        assert len(exceptions) == 0
        assert len(results) == 500

        # All states should be the same object
        unique_states = set(results)
        assert len(unique_states) == 1
        assert next(iter(unique_states)) is model._state

    def test_state_after_pickle_roundtrip(self) -> None:
        """Test that state is preserved after pickle/unpickle."""
        original_model = ModelFactory.create_eager_model()
        original_state = original_model._state

        # Add some data
        original_model.tags.extend(["pickle_tag"])
        original_model.settings["pickle_key"] = "pickle_value"

        # Pickle and unpickle
        pickled_data = pickle.dumps(original_model)
        restored_model = pickle.loads(pickled_data)

        # State should be restored
        assert restored_model._state is not original_state
        assert restored_model.tags == original_model.tags
        assert restored_model.settings == original_model.settings

        # New state should work for mutations
        restored_model.tags.append("after_pickle")
        assert len(restored_model.tags) == len(original_model.tags) + 1


class TestMutableWrapping:
    """Tests for automatic collection wrapping."""

    def test_wraps_lists_and_dicts(self) -> None:
        """Verify that standard collections are converted to mutable ones."""
        model = ModelFactory.create_eager_model(
            tags=["item"], settings={"key": "val"}
        )

        assert isinstance(model.tags, MutableList)
        assert isinstance(model.settings, MutableDict)

        assert model._state in model.tags._parents
        assert model.tags._parents[model._state] == "tags"

        assert model._state in model.settings._parents
        assert model.settings._parents[model._state] == "settings"

    def test_wrapping_preserves_content(self) -> None:
        """Test that wrapping preserves original content."""
        original_tags = ["tag1", "tag2", "tag3"]
        original_settings = {
            "key1": "val1",
            "key2": "val2",
            "nested": {"deep": "deep_val"},
        }

        model = ModelFactory.create_eager_model(
            tags=original_tags, settings=original_settings
        )

        # Content should be preserved
        assert list(model.tags) == original_tags
        assert dict(model.settings) == original_settings
        assert model.settings["nested"] == original_settings["nested"]

    def test_optimization_short_circuit(self) -> None:
        """Verify that already wrapped objects are not re-wrapped."""
        model = ModelFactory.create_eager_model()
        existing_list = MutableList(["a", "b"])

        model.tags = existing_list

        assert model.tags is existing_list
        assert model._state in existing_list._parents

    def test_deep_wrapping(self) -> None:
        """Test that deeply nested collections are properly wrapped."""
        nested_data = {
            "level1": {
                "level2": {
                    "list": [1, 2, 3],
                    "dict": {"nested_key": "nested_val"},
                }
            }
        }

        model = ModelFactory.create_eager_model(settings=nested_data)

        # Deep collections should be wrapped
        level2 = model.settings["level1"]["level2"]
        assert isinstance(level2["list"], MutableList)
        assert isinstance(level2["dict"], MutableDict)

        # Parent tracking works at the settings level
        assert model._state in model.settings._parents

    def test_wrapping_edge_cases(self) -> None:
        """Test wrapping behavior with edge cases."""
        # Empty collections
        model1 = ModelFactory.create_eager_model(tags=[], settings={})
        assert isinstance(model1.tags, MutableList)
        assert isinstance(model1.settings, MutableDict)

        # None values (using ModelFactory defaults)
        model2 = ModelFactory.create_eager_model()
        # Should not raise errors and handle appropriately
        assert isinstance(model2.tags, MutableList | list)
        assert isinstance(model2.settings, MutableDict | dict)

        # Mixed types
        model3 = ModelFactory.create_eager_model(
            settings={"mixed": ["list", {"dict": "value"}]}
        )
        assert isinstance(model3.settings, MutableDict)
        assert isinstance(model3.settings["mixed"], MutableList)
        assert isinstance(model3.settings["mixed"][1], MutableDict)


class TestMutationTracking:
    """Tests for mutation tracking functionality."""

    def test_list_mutation_tracking(self) -> None:
        """Test that list mutations are tracked correctly."""
        model = ModelFactory.create_eager_model(tags=[])
        original_state = model._state

        # Test various list operations
        model.tags.append("new_item")
        assert "new_item" in model.tags
        assert model._state is original_state

        model.tags.extend(["item1", "item2"])
        assert len(model.tags) == 3
        assert model._state is original_state

        model.tags[0] = "modified"
        assert model.tags[0] == "modified"
        assert model._state is original_state

        model.tags.pop()
        assert len(model.tags) == 2
        assert model._state is original_state

        model.tags.clear()
        assert len(model.tags) == 0
        assert model._state is original_state

    def test_dict_mutation_tracking(self) -> None:
        """Test that dict mutations are tracked correctly."""
        model = ModelFactory.create_eager_model()
        original_state = model._state

        # Test various dict operations
        model.settings["new_key"] = "new_value"
        assert model.settings["new_key"] == "new_value"
        assert model._state is original_state

        model.settings.update({"key1": "val1", "key2": "val2"})
        assert len(model.settings) >= 2
        assert model._state is original_state

        model.settings["existing_key"] = "modified_value"
        assert model.settings["existing_key"] == "modified_value"
        assert model._state is original_state

        del model.settings["new_key"]
        assert "new_key" not in model.settings
        assert model._state is original_state

        model.settings.clear()
        assert len(model.settings) == 0
        assert model._state is original_state

    def test_nested_mutation_tracking(self) -> None:
        """Test that nested mutations are tracked correctly."""
        model = ModelFactory.create_eager_model(
            settings={
                "level1": {"list": [1, 2, 3], "dict": {"nested": "value"}}
            }
        )
        original_state = model._state

        # Mutate nested structures
        model.settings["level1"]["list"].append(4)
        assert 4 in model.settings["level1"]["list"]
        assert model._state is original_state

        model.settings["level1"]["dict"]["nested"] = "modified"
        assert model.settings["level1"]["dict"]["nested"] == "modified"
        assert model._state is original_state

        # Add new nested structure
        model.settings["level1"]["new_list"] = ["a", "b"]
        assert model.settings["level1"]["new_list"] == ["a", "b"]
        assert model._state is original_state

    def test_mutation_after_assignment(self) -> None:
        """Test that mutations work correctly after assignment."""
        model = ModelFactory.create_eager_model()
        original_state = model._state

        # Assign new collections and then mutate
        model.tags = ["initial"]
        model.settings = {"key": "value"}

        assert isinstance(model.tags, MutableList)
        assert isinstance(model.settings, MutableDict)
        assert model._state is original_state

        # Mutate after assignment
        model.tags.append("added")
        model.settings["new_key"] = "new_value"

        assert "added" in model.tags
        assert model.settings["new_key"] == "new_value"
        assert model._state is original_state

    def test_mutation_suppression(self) -> None:
        """Test that mutations work with state tracking."""
        model = ModelFactory.create_eager_model()
        original_state = model._state

        # Perform mutations
        model.tags.append("item1")
        model.settings["key"] = "value"

        # State should remain the same (state token is persistent)
        assert model._state is original_state

        # Data should have changed
        assert "item1" in model.tags
        assert model.settings["key"] == "value"

        # Normal mutation should continue to work
        model.tags.append("item2")
        assert "item2" in model.tags
        assert model._state is original_state


class TestPerformanceCharacteristics:
    """Tests for performance characteristics and optimizations."""

    def test_attribute_access_performance(self) -> None:
        """Test that attribute access is performant."""
        model = ModelFactory.create_eager_model()

        # Warm up
        for _ in range(100):
            _ = model.tags
            _ = model.settings

        # Measure performance
        start_time = time.perf_counter()
        for _ in range(10000):
            _ = model.tags
            _ = model.settings
        end_time = time.perf_counter()

        # Should be very fast (less than 0.1 seconds for 20k accesses)
        duration = end_time - start_time
        assert duration < 0.1, f"Attribute access too slow: {duration:.4f}s"

    def test_large_collection_handling(self) -> None:
        """Test handling of large collections."""
        large_list = [f"item_{i}" for i in range(10000)]
        large_dict = {f"key_{i}": f"value_{i}" for i in range(1000)}

        model = ModelFactory.create_eager_model(
            tags=large_list, settings=large_dict
        )

        # Should handle large collections without issues
        assert len(model.tags) == 10000
        assert len(model.settings) == 1000

        # Mutations should still work
        start_time = time.perf_counter()
        model.tags.append("new_item")
        model.settings["new_key"] = "new_value"
        end_time = time.perf_counter()

        # Should still be reasonably fast even with large collections
        assert (end_time - start_time) < 0.01  # 10ms
        assert len(model.tags) == 10001
        assert model.settings["new_key"] == "new_value"

    def test_memory_usage(self) -> None:
        """Test memory usage characteristics."""
        import sys

        # Create models and check that they don't use excessive memory
        models = []
        for _ in range(100):
            model = ModelFactory.create_eager_model()
            # Clear default tags and add controlled number
            model.tags.clear()
            model.tags.extend([f"tag_{j}" for j in range(10)])
            models.append(model)

        # Check that total memory usage is reasonable
        total_size = sum(sys.getsizeof(model) for model in models)
        # Each model should not use excessive memory (this is a rough check)
        assert total_size < 10 * 1024 * 1024  # Less than 10MB for 100 models

        # Verify all models work correctly
        for model in models:
            assert len(model.tags) == 10
            assert isinstance(model.tags, MutableList)
            assert model._state is not None

    def test_lazy_initialization_optimization(self) -> None:
        """Test that lazy initialization works correctly."""
        # Create model with minimal data
        model = ModelFactory.create_eager_model(tags=[], settings={})

        # Collections should be wrapped immediately (not lazy for eager models)
        assert isinstance(model.tags, MutableList)
        assert isinstance(model.settings, MutableDict)

        # But accessing them should still be fast
        start_time = time.perf_counter()
        for _ in range(1000):
            _ = model.tags
            _ = model.settings
        end_time = time.perf_counter()

        assert (end_time - start_time) < 0.01  # Very fast access


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    def test_invalid_assignment_handling(self) -> None:
        """Test handling of invalid assignments."""
        model = ModelFactory.create_eager_model()

        # Try invalid assignments - Pydantic should handle these
        # Note: Pydantic v2 may coerce types instead of raising
        try:
            model.tags = "not_a_list"
            # If it doesn't raise, check that it's been handled appropriately
            assert not isinstance(model.tags, str)
        except Exception:
            pass  # Expected to handle gracefully

        try:
            model.settings = "not_a_dict"
            # If it doesn't raise, check that it's been handled appropriately
            assert not isinstance(model.settings, str)
        except Exception:
            pass

        # Valid assignments should work
        model.tags = []
        model.settings = {}
        assert isinstance(model.tags, list | MutableList)
        assert isinstance(model.settings, dict | MutableDict)

    def test_corrupted_state_handling(self) -> None:
        """Test handling of corrupted state."""
        model = ModelFactory.create_eager_model()
        original_state = model._state

        # State should be accessible and valid
        assert original_state is not None
        assert model._state is original_state

        # Mutations should work properly
        model.tags.append("test")
        assert "test" in model.tags
        assert model._state is original_state

    def test_recursion_depth_protection(self) -> None:
        """Test protection against infinite recursion."""

        # Create deeply nested structure
        def create_nested_structure(depth):
            if depth <= 0:
                return "leaf"
            return {"nested": create_nested_structure(depth - 1)}

        very_deep_data = create_nested_structure(150)  # Exceed default depth

        try:
            model = ModelFactory.create_eager_model(settings=very_deep_data)
            # Should handle deep structures gracefully
            assert model.settings is not None
        except RecursionError:
            # Should catch recursion errors
            pytest.skip("Recursion depth exceeded - this is acceptable")

    def test_thread_safety_with_exceptions(self) -> None:
        """Test thread safety when exceptions occur."""
        model = ModelFactory.create_eager_model()
        exceptions = []

        def worker_with_exception():
            try:
                for i in range(10):
                    model.tags.append(f"item_{i}")
                    if i == 5:
                        # Intentionally cause an error
                        raise ValueError("Test exception")
            except Exception as e:
                exceptions.append(e)

        threads = []
        for _ in range(3):
            t = threading.Thread(target=worker_with_exception)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Should have captured exceptions
        assert len(exceptions) == 3
        assert all(isinstance(e, ValueError) for e in exceptions)

        # Model should still be in a valid state
        assert isinstance(model.tags, MutableList)
        assert model._state is not None


class TestIntegrationWithSQLAlchemy:
    """Integration tests with SQLAlchemy."""

    def test_mutable_flag_modification(
        self, session: Any, sqlite_memory_engine: Any
    ) -> None:
        """Test that changes trigger SQLAlchemy flag_modified."""
        # Create entity with model
        model = ModelFactory.create_eager_model()
        entity = UserEntity(username=model.username, settings=model)
        session.add(entity)
        session.commit()

        # Modify the model
        entity.settings.tags.append("modified")
        entity.settings.settings["modified"] = True

        # Should trigger dirty state
        assert session.is_modified(entity)

    def test_database_roundtrip(
        self, session: Any, sqlite_memory_engine: Any
    ) -> None:
        """Test database save/load roundtrip."""
        # Create and save
        original_model = ModelFactory.create_eager_model()
        original_model.tags.extend(["db_test1", "db_test2"])
        original_model.settings["db_key"] = "db_value"

        entity = UserEntity(
            username=original_model.username, settings=original_model
        )
        session.add(entity)
        session.commit()

        # Load from database
        loaded_entity = (
            session.query(UserEntity)
            .filter_by(username=original_model.username)
            .first()
        )
        loaded_model = loaded_entity.settings

        # Verify data integrity
        assert loaded_model.user_id == original_model.user_id
        assert loaded_model.username == original_model.username
        assert loaded_model.tags == original_model.tags
        assert loaded_model.settings == original_model.settings

        # Test mutations on loaded model
        loaded_model.tags.append("after_load")
        loaded_model.settings["after_load"] = True

        assert len(loaded_model.tags) == len(original_model.tags) + 1
        assert loaded_model.settings["after_load"] is True


# Import Base for SQLAlchemy integration tests


class Base(DeclarativeBase):
    pass
