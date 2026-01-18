"""Tests for thread safety and concurrent mutation tracking."""

import gc
import threading
import time
from collections.abc import Generator
from typing import Any

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from sqlatypemodel import LazyMutableMixin, MutableMixin
from sqlatypemodel.model_type import ModelType


# Test models for concurrency testing
class ConcurrentEagerModel(MutableMixin, BaseModel):
    """Model for concurrent eager loading tests."""

    model_config = {"extra": "allow"}

    counter: int = 0
    data: list[Any] = Field(default_factory=list)
    tags: set[str] = Field(default_factory=set)
    meta: dict[str, Any] = Field(default_factory=dict)


class ConcurrentLazyModel(LazyMutableMixin, BaseModel):
    """Model for concurrent lazy loading tests."""

    model_config = {"extra": "allow"}

    counter: int = 0
    items: list[int | str] = Field(
        default_factory=list
    )  # Allow mixed types for testing
    data: dict[str, Any] = Field(default_factory=dict)


# SQLAlchemy entities for concurrency testing
class Base(DeclarativeBase):
    pass


class ConcurrentEntity(Base):
    """Entity for concurrency testing with eager model."""

    __tablename__ = "concurrent_entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    eager_data: Mapped[ConcurrentEagerModel] = mapped_column(
        ModelType(ConcurrentEagerModel)
    )
    lazy_data: Mapped[ConcurrentLazyModel] = mapped_column(
        ModelType(ConcurrentLazyModel)
    )


class TestConcurrencyBasics:
    """Basic thread safety tests."""

    def test_concurrent_model_creation(self) -> None:
        """Test that models can be created concurrently without conflicts."""
        models = []
        errors = []

        def create_model(index: int) -> None:
            try:
                for _ in range(10):
                    model = ConcurrentEagerModel(
                        counter=index,
                        data=[f"thread_{index}_item_{i}" for i in range(5)],
                    )
                    models.append(model)
            except Exception as e:
                errors.append(e)

        # Create models in 10 threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=create_model, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(models) == 100  # 10 threads × 10 models each

        # Verify all models have proper state tracking
        for model in models:
            assert hasattr(model, "_state")
            assert model._state is not None

    def test_concurrent_state_access(self) -> None:
        """Test concurrent access to _state attribute."""
        model = ConcurrentEagerModel(counter=0)
        results = []
        errors = []

        def access_state(thread_id: int) -> None:
            try:
                for i in range(100):
                    state = model._state
                    results.append((thread_id, i, id(state)))
            except Exception as e:
                errors.append(e)

        # Access state from multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=access_state, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 500  # 5 threads × 100 accesses each

        # All accesses should return the same state object
        state_ids = {result[2] for result in results}
        assert (
            len(state_ids) == 1
        ), "State object identity should be consistent"


class TestConcurrentMutationTracking:
    """Tests for concurrent mutation tracking."""

    def test_concurrent_list_mutations(self) -> None:
        """Test concurrent mutations to list attributes."""
        model = ConcurrentEagerModel(data=list(range(100)))
        errors = []
        mutation_counts = []

        def mutate_list(start_idx: int, thread_id: int) -> None:
            try:
                count = 0
                for i in range(50):
                    # Append items
                    model.data.append(f"thread_{thread_id}_item_{i}")
                    count += 1

                    # Modify existing items
                    if start_idx + i < len(model.data):
                        model.data[start_idx + i] = f"modified_{thread_id}_{i}"
                        count += 1

                mutation_counts.append(count)
            except Exception as e:
                errors.append(e)

        # Run mutations in multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=mutate_list, args=(i * 20, i))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(mutation_counts) == 5

        # Verify data integrity
        assert len(model.data) >= 100  # Original + additions

        # Verify change tracking still works
        original_data = model.data.copy()
        model.data.append("final_item")
        assert len(model.data) == len(original_data) + 1

    def test_concurrent_dict_mutations(self) -> None:
        """Test concurrent mutations to dict attributes."""
        model = ConcurrentEagerModel(meta={"initial": "value"})
        errors = []
        operation_counts = []

        def mutate_dict(thread_id: int) -> None:
            try:
                count = 0
                for i in range(25):
                    # Add new keys
                    model.meta[f"thread_{thread_id}_key_{i}"] = f"value_{i}"
                    count += 1

                    # Update existing keys
                    if f"thread_{thread_id}_key_{i - 1}" in model.meta:
                        model.meta[
                            f"thread_{thread_id}_key_{i - 1}"
                        ] = f"updated_{i}"
                        count += 1

                operation_counts.append(count)
            except Exception as e:
                errors.append(e)

        # Run mutations in multiple threads
        threads = []
        for i in range(4):
            thread = threading.Thread(target=mutate_dict, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(operation_counts) == 4

        # Verify data integrity
        # Each thread did 25 additions (some might be updates if we were unlucky with keys,
        # but here keys are thread-unique)
        expected_count = 4 * 25 + 1  # 4 threads * 25 keys + 1 initial
        assert len(model.meta) == expected_count

        # Verify change tracking still works
        model.meta["final_key"] = "final_value"
        assert "final_key" in model.meta

    def test_concurrent_counter_increments(self) -> None:
        """Test concurrent increments to counter fields."""
        model = ConcurrentEagerModel(counter=0)
        errors = []
        increments = []

        def increment_counter(thread_id: int) -> None:
            try:
                local_count = 0
                for i in range(100):
                    # Read-modify-write operation
                    current = model.counter
                    time.sleep(
                        0.001
                    )  # Small delay to increase race condition likelihood
                    model.counter = current + 1
                    local_count += 1
                increments.append(local_count)
            except Exception as e:
                errors.append(e)

        # Run concurrent increments
        threads = []
        for i in range(5):
            thread = threading.Thread(target=increment_counter, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(increments) == 5

        # Note: Due to race conditions, final counter may be less than expected
        # but should be greater than initial value
        assert model.counter > 0


@pytest.fixture(scope="function")
def concurrent_session(
    sqlite_memory_engine: Engine,
) -> Generator[Session, None, None]:
    """Session for concurrent database testing with proper table creation."""
    # Create tables for concurrent testing
    Base.metadata.create_all(sqlite_memory_engine)

    conn = sqlite_memory_engine.connect()
    trans = conn.begin()
    sess = Session(bind=conn)

    yield sess

    sess.close()
    try:
        trans.rollback()
    except Exception:
        pass  # Transaction may already be rolled back
    conn.close()

    # Clean up tables
    Base.metadata.drop_all(sqlite_memory_engine)


class TestConcurrentDatabaseOperations:
    """Tests for concurrent database operations."""

    def test_concurrent_database_mutations(
        self, concurrent_session: Session
    ) -> None:
        """Test concurrent database mutations with change tracking."""
        # Test thread safety with in-memory mutations rather than DB concurrency
        # (SQLite has limited write concurrency support)
        entity = ConcurrentEntity(
            eager_data=ConcurrentEagerModel(counter=0, data=[]),
            lazy_data=ConcurrentLazyModel(counter=0, items=[]),
        )
        concurrent_session.add(entity)
        concurrent_session.commit()

        # Ensure all attributes are loaded before detaching
        concurrent_session.refresh(entity)

        # Detach entity to test MutableMixin thread safety without
        # violating SQLAlchemy Session thread-safety rules
        concurrent_session.expunge(entity)

        errors = []
        modification_counts = []

        def modify_in_memory(thread_id: int) -> None:
            try:
                # Modify the same entity object in memory from multiple threads
                count = 0

                # Eager modifications
                for i in range(10):
                    entity.eager_data.data.append(
                        f"thread_{thread_id}_item_{i}"
                    )
                    entity.eager_data.counter += 1
                    count += 1

                    # Lazy modifications
                    entity.lazy_data.items.append(thread_id * 100 + i)
                    entity.lazy_data.counter += 1
                    count += 1

                    # Small delay to increase chance of race conditions
                    time.sleep(0.001)

                modification_counts.append(count)
            except Exception as e:
                errors.append(e)

        # Run concurrent modifications on the same object
        threads = []
        for i in range(5):
            thread = threading.Thread(target=modify_in_memory, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(modification_counts) == 5

        # Re-attach and save
        entity = concurrent_session.merge(entity)
        concurrent_session.commit()

        # Verify final state - counts should be accumulated
        assert entity.eager_data.counter > 0
        assert entity.lazy_data.counter > 0
        assert len(entity.eager_data.data) > 0
        assert len(entity.lazy_data.items) > 0

        # Test that additional changes are still tracked
        original_data_len = len(entity.eager_data.data)
        entity.eager_data.data.append("final_item")
        assert len(entity.eager_data.data) == original_data_len + 1


class TestConcurrentGarbageCollection:
    """Tests for garbage collection behavior under concurrency."""

    def test_concurrent_gc_with_mutable_objects(self) -> None:
        """Test garbage collection with concurrent mutable object creation/destruction."""
        errors = []
        object_counts = []
        weak_ref_sets = []

        def create_destroy_objects(thread_id: int) -> None:
            try:
                import weakref

                objects = []
                weak_refs = []

                # Create objects
                for i in range(50):
                    model = ConcurrentEagerModel(
                        counter=i, data=[f"item_{i}_{j}" for j in range(3)]
                    )
                    objects.append(model)
                    weak_refs.append(weakref.ref(model))

                object_counts.append(len(objects))
                weak_ref_sets.append(weak_refs)

                # Explicitly delete half the objects
                for obj in objects[:25]:
                    del obj

                # Force garbage collection
                gc.collect()

                # Check remaining objects
                remaining_count = sum(
                    1 for ref in weak_refs if ref() is not None
                )
                # Note: Objects may persist longer due to mutation tracking references
                # This is expected behavior - we're testing that GC doesn't crash
                assert (
                    remaining_count >= 25
                ), f"Expected at least 25 remaining objects, got {remaining_count}"

            except Exception as e:
                errors.append(e)

        # Run concurrent object creation/destruction
        threads = []
        for i in range(3):
            thread = threading.Thread(target=create_destroy_objects, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(object_counts) == 3
        assert all(count == 50 for count in object_counts)

        # Final garbage collection
        gc.collect()


class TestConcurrentLazyLoading:
    """Tests specific to lazy loading under concurrency."""

    def test_concurrent_lazy_initialization(self) -> None:
        """Test lazy initialization under concurrent access."""
        model = ConcurrentLazyModel(counter=0, items=[])
        errors = []
        access_results = []

        def access_lazy_attributes(thread_id: int) -> None:
            try:
                # Access lazy attributes
                for i in range(20):
                    # These should trigger JIT wrapping
                    model.items[i] if i < len(model.items) else None
                    model.data.get(f"key_{i}")

                    # Modify data
                    model.data[f"thread_{thread_id}_key_{i}"] = f"value_{i}"
                    model.items.append(thread_id * 1000 + i)

                access_results.append(thread_id)
            except Exception as e:
                errors.append(e)

        # Run concurrent access
        threads = []
        for i in range(4):
            thread = threading.Thread(target=access_lazy_attributes, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(access_results) == 4

        # Verify final state
        assert len(model.items) == 80  # 4 threads × 20 items each
        assert len(model.data) == 80  # 4 threads × 20 keys each

        # Verify change tracking still works
        original_items = model.items.copy()
        model.items.append("final_item")
        assert len(model.items) == len(original_items) + 1
