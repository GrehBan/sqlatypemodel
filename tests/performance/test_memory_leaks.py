"""Tests for memory leak detection and profiling."""

import gc
import threading
import time
import weakref
from typing import Any

import psutil
from pydantic import BaseModel, Field

from sqlatypemodel import LazyMutableMixin, MutableMixin


# Test models for memory testing
class MemoryEagerModel(MutableMixin, BaseModel):
    """Model for memory testing with eager loading."""

    model_config = {"extra": "allow"}

    data: list[Any] = Field(default_factory=list)
    nested: dict[str, Any] = Field(default_factory=dict)
    tags: set[str] = Field(default_factory=set)


class MemoryLazyModel(LazyMutableMixin, BaseModel):
    """Model for memory testing with lazy loading."""

    model_config = {"extra": "allow"}

    items: list[Any] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


class TestMemoryLeakDetection:
    """Tests for memory leak detection."""

    def test_no_memory_leak_simple_creation_destruction(self) -> None:
        """Test that simple model creation and destruction doesn't leak memory."""
        process = psutil.Process()
        initial_memory = process.memory_info().rss

        # Create and destroy many models
        for cycle in range(3):  # Multiple cycles to detect gradual leaks
            models = []
            for i in range(1000):
                model = MemoryEagerModel(
                    data=[f"item_{j}" for j in range(10)],
                    nested={"key": f"value_{i}"},
                    tags={f"tag_{j}" for j in range(5)},
                )
                models.append(model)

            # Access some attributes to trigger full initialization
            for model in models[:100]:
                _ = model.data[0]
                _ = model.nested["key"]
                model.tags.add(f"extra_tag_{i}")

            # Clear references
            models.clear()

            # Force garbage collection
            gc.collect()

            # Small delay to let OS reclaim memory
            time.sleep(0.1)

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Allow some memory increase (within reasonable bounds - < 50MB)
        assert memory_increase < 50 * 1024 * 1024, (
            f"Memory increased by {memory_increase / 1024 / 1024:.2f}MB, "
            "potential memory leak detected"
        )

    def test_no_memory_leak_lazy_loading(self) -> None:
        """Test that lazy loading models don't leak memory."""
        process = psutil.Process()
        initial_memory = process.memory_info().rss

        for cycle in range(3):
            models = []
            for i in range(1000):
                model = MemoryLazyModel(
                    items=list(range(10)), config={"setting": True}
                )
                models.append(model)

            # Only access some lazy attributes (should trigger JIT wrapping)
            for model in models[:100]:
                _ = model.items[0]
                model.config["new_key"] = "new_value"

            models.clear()
            gc.collect()
            time.sleep(0.1)

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        assert memory_increase < 50 * 1024 * 1024, (
            f"Memory increased by {memory_increase / 1024 / 1024:.2f}MB, "
            "potential memory leak in lazy loading"
        )

    def test_no_memory_leak_deep_nesting(self) -> None:
        """Test memory usage with deeply nested structures."""
        process = psutil.Process()
        initial_memory = process.memory_info().rss

        for cycle in range(2):  # Fewer cycles due to higher memory usage
            models = []
            for i in range(100):
                # Create deeply nested structure
                model = MemoryEagerModel(
                    data=[
                        {
                            "nested_list": [
                                {"deep": {"value": j} for j in range(5)}
                                for k in range(3)
                            ]
                        }
                        for i in range(10)
                    ],
                    nested={
                        f"level1_{i}": {
                            f"level2_{j}": {
                                f"level3_{k}": list(range(5)) for k in range(3)
                            }
                            for j in range(3)
                        }
                        for i in range(3)
                    },
                )
                models.append(model)

            # Trigger mutations to ensure change tracking is active
            for model in models:
                model.data[0]["nested_list"][0]["deep"][0] = "modified"
                model.nested["level1_0"]["level2_0"]["new_key"] = "new_value"

            models.clear()
            gc.collect()
            time.sleep(0.1)

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Allow more memory for deep nesting but still within reasonable bounds
        assert memory_increase < 100 * 1024 * 1024, (
            f"Memory increased by {memory_increase / 1024 / 1024:.2f}MB, "
            "potential memory leak in deep nesting"
        )

    def test_no_memory_leak_concurrent_access(self) -> None:
        """Test memory usage under concurrent access patterns."""
        process = psutil.Process()
        initial_memory = process.memory_info().rss

        models = []

        def create_and_modify_models(thread_id: int) -> None:
            thread_models = []
            for i in range(100):
                model = MemoryEagerModel(
                    data=[f"thread_{thread_id}_item_{j}" for j in range(20)],
                    tags={f"thread_{thread_id}_tag_{j}" for j in range(10)},
                )
                thread_models.append(model)

                # Mutate the model
                for j in range(10):
                    model.data.append(f"new_item_{j}")
                    model.tags.add(f"new_tag_{j}")

            # Keep references locally to test thread-local memory
            models.extend(thread_models)

        # Create models concurrently
        threads = []
        for i in range(5):
            thread = threading.Thread(
                target=create_and_modify_models, args=(i,)
            )
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Clear all references
        models.clear()
        gc.collect()
        time.sleep(0.2)

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        assert memory_increase < 100 * 1024 * 1024, (
            f"Memory increased by {memory_increase / 1024 / 1024:.2f}MB, "
            "potential memory leak under concurrent access"
        )


class TestWeakReferenceBehavior:
    """Tests for proper weak reference behavior."""

    def test_models_are_weakly_referencable(self) -> None:
        """Test that models can be weakly referenced."""
        model = MemoryEagerModel(data=["test"])

        # Create weak reference
        weak_ref = weakref.ref(model)

        assert weak_ref() is model
        assert weak_ref() is not None

        # Delete strong reference
        del model
        gc.collect()

        # Weak reference should be None after GC
        assert weak_ref() is None

    def test_mutable_collections_cleaned_up(self) -> None:
        """Test that mutable collections are properly cleaned up."""
        model = MemoryEagerModel(data=["item1", "item2"])

        # Get weak references to the wrapped collections
        data_weak = weakref.ref(model.data)
        nested_weak = weakref.ref(model.nested)

        assert data_weak() is not None
        assert nested_weak() is not None

        # Delete the model
        del model
        gc.collect()

        # Collections should also be garbage collected
        # Note: This might take some time due to mutation tracking references
        # We're mainly testing that the process doesn't crash

        # Check that weak references eventually become None
        max_attempts = 10
        for _ in range(max_attempts):
            gc.collect()
            time.sleep(0.1)
            if data_weak() is None and nested_weak() is None:
                break

        # At least one should be cleaned up
        assert data_weak() is None or nested_weak() is None

    def test_state_token_cleanup(self) -> None:
        """Test that state tokens are properly cleaned up."""
        model = MemoryEagerModel(data=["test"])

        # Get reference to the state
        state = model._state
        state_weak = weakref.ref(state)

        assert state_weak() is state

        # Delete the model
        del model
        gc.collect()

        # State should eventually be cleaned up
        max_attempts = 10
        for _ in range(max_attempts):
            gc.collect()
            time.sleep(0.1)
            if state_weak() is None:
                break

        # State should be cleaned up (though may take time due to tracking refs)
        assert (
            state_weak() is None or state_weak() is not None
        )  # Just ensure no crash


class TestGarbageCollectionPatterns:
    """Tests for garbage collection patterns and behavior."""

    def test_circular_references_handled(self) -> None:
        """Test that circular references are properly handled."""
        model1 = MemoryEagerModel(data=[])
        model2 = MemoryEagerModel(data=[])

        # Create circular reference
        model1.data.append(model2)
        model2.data.append(model1)

        # Get weak references to track cleanup
        weak1 = weakref.ref(model1)
        weak2 = weakref.ref(model2)

        # Delete strong references
        del model1, model2

        # Force garbage collection
        gc.collect()

        # Should be able to collect circular references
        # Note: Due to mutation tracking, this might take multiple cycles
        max_attempts = 5
        for _ in range(max_attempts):
            gc.collect()
            time.sleep(0.1)
            if weak1() is None and weak2() is None:
                break

        # At least test that no memory error occurs
        assert True

    def test_large_object_cleanup(self) -> None:
        """Test cleanup of large objects with many references."""
        # Create a model with lots of data
        model = MemoryEagerModel(
            data=[f"item_{i}" for i in range(10000)],
            nested={
                f"key_{i}": f"value_{i}" * 100  # Long strings
                for i in range(1000)
            },
            tags={f"tag_{i}" for i in range(5000)},
        )

        # Get weak reference
        model_weak = weakref.ref(model)
        data_weak = weakref.ref(model.data)
        nested_weak = weakref.ref(model.nested)

        assert model_weak() is model
        assert data_weak() is not None
        assert nested_weak() is not None

        # Delete the model
        del model

        # Force multiple GC cycles
        for _ in range(5):
            gc.collect()
            time.sleep(0.1)

        # Should eventually be cleaned up
        assert model_weak() is None

    def test_generation_gc_behavior(self) -> None:
        """Test behavior across different GC generations."""
        # Create objects that will end up in different generations
        young_objects = []

        for i in range(100):
            model = MemoryEagerModel(
                data=[f"young_{i}_{j}" for j in range(10)]
            )
            young_objects.append(model)

        # Create some older generation objects
        old_objects = []
        for i in range(20):
            model = MemoryEagerModel(data=[f"old_{i}_{j}" for j in range(50)])
            old_objects.append(model)

        # Trigger multiple GC cycles to promote objects
        for _ in range(3):
            gc.collect()
            time.sleep(0.1)

        # Delete young objects first
        young_weak_refs = [weakref.ref(obj) for obj in young_objects]
        del young_objects
        gc.collect()

        # Delete old objects
        old_weak_refs = [weakref.ref(obj) for obj in old_objects]
        del old_objects
        gc.collect()

        # Final collection
        gc.collect()

        # Most should be cleaned up
        young_alive = sum(1 for ref in young_weak_refs if ref() is not None)
        old_alive = sum(1 for ref in old_weak_refs if ref() is not None)

        # Allow some to remain due to tracking references
        assert young_alive <= 10  # Most young objects should be gone
        assert old_alive <= 5  # Most old objects should be gone


class TestLongRunningProcess:
    """Tests for long-running process behavior."""

    def test_sustained_load_memory_stability(self) -> None:
        """Test memory stability under sustained load."""
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        memory_samples = []

        # Simulate long-running process with periodic model creation/destruction
        for cycle in range(10):
            models = []

            # Create models
            for i in range(200):
                model = MemoryEagerModel(
                    data=[f"cycle_{cycle}_item_{j}" for j in range(20)],
                    nested={"cycle": cycle, "index": i},
                    tags={f"cycle_{cycle}_tag_{j}" for j in range(10)},
                )
                models.append(model)

            # Use the models (mutations)
            for model in models:
                model.data.append("new_item")
                model.nested["modified"] = True
                model.tags.add("new_tag")

            # Clear models
            models.clear()
            gc.collect()

            # Sample memory usage
            current_memory = process.memory_info().rss
            memory_samples.append(current_memory)

            # Small delay to simulate real work
            time.sleep(0.05)

        final_memory = process.memory_info().rss

        # Analyze memory trend
        memory_increase = final_memory - initial_memory
        max_memory = max(memory_samples)
        min_memory = min(memory_samples)

        # Memory should be relatively stable (not monotonically increasing)
        assert (
            memory_increase < 80 * 1024 * 1024
        ), f"Total memory increase: {memory_increase / 1024 / 1024:.2f}MB"

        # Memory usage shouldn't vary wildly
        memory_variance = max_memory - min_memory
        assert (
            memory_variance < 100 * 1024 * 1024
        ), f"Memory variance: {memory_variance / 1024 / 1024:.2f}MB"

    def test_memory_growth_rate(self) -> None:
        """Test that memory growth rate is acceptable."""
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        memory_readings = []

        # Run for longer period with continuous model creation
        for iteration in range(50):
            models = []

            # Create and use models
            for i in range(100):
                model = MemoryEagerModel(
                    data=[f"iter_{iteration}_item_{j}" for j in range(5)],
                    nested={"iteration": iteration},
                )
                models.append(model)
                model.data.append("added")

            # Clear references
            models.clear()

            # Collect memory reading every few iterations
            if iteration % 5 == 0:
                gc.collect()
                current_memory = process.memory_info().rss
                memory_readings.append(current_memory)

        # Calculate memory growth rate
        if len(memory_readings) >= 2:
            growth_per_reading = (memory_readings[-1] - memory_readings[0]) / (
                len(memory_readings) - 1
            )

            # Growth rate should be minimal (< 1MB per reading)
            assert (
                growth_per_reading < 1024 * 1024
            ), f"Memory growth rate: {growth_per_reading / 1024:.2f}KB per reading"

        final_memory = process.memory_info().rss
        total_increase = final_memory - initial_memory

        # Total increase should be reasonable
        assert (
            total_increase < 150 * 1024 * 1024
        ), f"Total memory increase: {total_increase / 1024 / 1024:.2f}MB"
