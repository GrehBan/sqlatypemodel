"""Test isolation and cleanup utilities.

Provides comprehensive tools for ensuring tests are properly isolated
and cleaned up to prevent test interference.
"""

from __future__ import annotations

import gc
import threading
import time
import weakref
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session


class IsolationManager:
    """Manages test isolation and cleanup procedures."""

    def __init__(self, session: Session):
        self.session = session
        self._original_thread_count = threading.active_count()
        self._original_objects = len(gc.get_objects())
        self._patches: list[Any] = []
        self._cleanup_callbacks: list[Callable[[], Any]] = []

    def add_cleanup_callback(self, callback: Callable[[], Any]) -> None:
        """Add a cleanup callback to be executed after the test."""
        self._cleanup_callbacks.append(callback)

    def register_patch(self, patch_obj: Any) -> None:
        """Register a patch to be cleaned up."""
        self._patches.append(patch_obj)

    def cleanup(self) -> None:
        """Perform comprehensive cleanup."""
        try:
            # Execute cleanup callbacks
            for callback in self._cleanup_callbacks:
                try:
                    callback()
                except Exception:
                    # Log but don't fail cleanup
                    pass

            # Stop all patches
            for patch_obj in self._patches:
                try:
                    patch_obj.stop()
                except Exception:
                    pass

            # Force garbage collection
            gc.collect()

            # Wait a bit for thread cleanup
            time.sleep(0.1)

            # Check for thread leaks
            current_thread_count = threading.active_count()
            if current_thread_count > self._original_thread_count:
                # Log thread leak but don't fail the test
                pass

        except Exception:
            # Cleanup should never fail the test
            pass


@pytest.fixture
def isolation_manager(
    session: Session,
) -> Generator[IsolationManager, None, None]:
    """Provide a test isolation manager."""
    manager = IsolationManager(session)

    try:
        yield manager
    finally:
        manager.cleanup()


@contextmanager
def database_isolation(session: Session) -> Generator[None, None, None]:
    """Context manager for database isolation."""
    # Start a transaction
    transaction = session.begin_nested()

    try:
        yield
    finally:
        # Roll back the nested transaction
        transaction.rollback()

        # Clear the session
        session.expunge_all()

        # Reset database state
        try:
            session.execute(text("DELETE FROM users_eager"))
            session.execute(text("DELETE FROM users_lazy"))
            session.execute(text("DELETE FROM nested_entities"))
            session.commit()
        except Exception:
            session.rollback()


@pytest.fixture
def isolated_session(session: Session) -> Generator[Session, None, None]:
    """Provide an isolated database session."""
    with database_isolation(session):
        yield session


@contextmanager
def memory_isolation() -> Generator[None, None, None]:
    """Context manager for memory isolation."""
    # Force garbage collection before test
    gc.collect()

    # Track objects before test
    initial_objects = len(gc.get_objects())

    try:
        yield
    finally:
        # Force garbage collection after test
        gc.collect()
        gc.collect()  # Call twice to ensure thorough cleanup

        # Check for memory leaks (but don't fail the test)
        final_objects = len(gc.get_objects())
        object_increase = final_objects - initial_objects

        # Log significant increases but allow some variance
        if object_increase > 1000:
            pass  # Could log this


@pytest.fixture
def memory_isolated() -> Generator[None, None, None]:
    """Provide memory isolation for the test."""
    with memory_isolation():
        yield


@contextmanager
def thread_isolation() -> Generator[None, None, None]:
    """Context manager for thread isolation."""
    initial_threads = set(threading.enumerate())

    try:
        yield
    finally:
        # Wait for threads to finish
        time.sleep(0.1)

        # Check for stray threads
        current_threads = set(threading.enumerate())
        stray_threads = current_threads - initial_threads

        # Try to join stray threads
        for thread in stray_threads:
            if hasattr(thread, "join") and thread.is_alive():
                try:
                    thread.join(timeout=1.0)
                except Exception:
                    pass


@pytest.fixture
def thread_isolated() -> Generator[None, None, None]:
    """Provide thread isolation for the test."""
    with thread_isolation():
        yield


@contextmanager
def state_isolation() -> Generator[None, None, None]:
    """Context manager for application state isolation."""
    # Store any mutable global state
    from sqlatypemodel import model_type

    # Backup registry state
    original_registry = getattr(model_type.ModelType, "_registry", None)

    try:
        yield
    finally:
        # Restore original state
        if original_registry is not None:
            model_type.ModelType._registry = original_registry.copy()


@pytest.fixture
def state_isolated() -> Generator[None, None, None]:
    """Provide application state isolation."""
    with state_isolation():
        yield


class MockEnvironment:
    """Mock environment for testing."""

    def __init__(self):
        self.env_vars = {}
        self.patches = []

    def set_env(self, key: str, value: str) -> None:
        """Set an environment variable."""
        self.env_vars[key] = value
        patcher = patch.dict("os.environ", {key: value})
        patcher.start()
        self.patches.append(patcher)

    def cleanup(self) -> None:
        """Clean up environment."""
        for patch_obj in self.patches:
            try:
                patch_obj.stop()
            except Exception:
                pass
        self.patches.clear()
        self.env_vars.clear()


@pytest.fixture
def mock_environment() -> Generator[MockEnvironment, None, None]:
    """Provide a mock environment manager."""
    env = MockEnvironment()

    try:
        yield env
    finally:
        env.cleanup()


class ResourceTracker:
    """Track resource usage during tests."""

    def __init__(self):
        self.initial_memory = None
        self.initial_objects = None
        self.initial_threads = None

    def start_tracking(self) -> None:
        """Start tracking resources."""
        import os

        import psutil

        try:
            self.initial_memory = psutil.Process(os.getpid()).memory_info().rss
        except Exception:
            self.initial_memory = None

        self.initial_objects = len(gc.get_objects())
        self.initial_threads = threading.active_count()

    def get_usage(self) -> dict[str, Any]:
        """Get current resource usage."""
        import os

        import psutil

        try:
            current_memory = psutil.Process(os.getpid()).memory_info().rss
            memory_delta = (
                current_memory - self.initial_memory
                if self.initial_memory
                else None
            )
        except Exception:
            memory_delta = None

        object_delta = (
            len(gc.get_objects()) - self.initial_objects
            if self.initial_objects
            else None
        )
        thread_delta = (
            threading.active_count() - self.initial_threads
            if self.initial_threads
            else None
        )

        return {
            "memory_delta": memory_delta,
            "object_delta": object_delta,
            "thread_delta": thread_delta,
        }


@pytest.fixture
def resource_tracker() -> Generator[ResourceTracker, None, None]:
    """Provide a resource usage tracker."""
    tracker = ResourceTracker()
    tracker.start_tracking()

    yield tracker


# Comprehensive isolation fixture that combines all isolation methods
@pytest.fixture
def fully_isolated(session: Session) -> Generator[Session, None, None]:
    """Provide a fully isolated test environment."""
    with database_isolation(session):
        with memory_isolation():
            with thread_isolation():
                with state_isolation():
                    yield session


# Cleanup utilities for specific scenarios
class DatabaseCleaner:
    """Utilities for cleaning database state."""

    @staticmethod
    def clean_all_tables(session: Session) -> None:
        """Clean all test tables."""
        tables = ["users_eager", "users_lazy", "nested_entities"]

        for table in tables:
            try:
                session.execute(text(f"DELETE FROM {table}"))
            except Exception:
                pass

        session.commit()

    @staticmethod
    def reset_sequences(session: Session) -> None:
        """Reset database sequences."""
        try:
            session.execute(text("DELETE FROM sqlite_sequence"))
            session.commit()
        except Exception:
            pass


@pytest.fixture
def database_cleaner(session: Session) -> DatabaseCleaner:
    """Provide a database cleaner."""
    cleaner = DatabaseCleaner()

    try:
        yield cleaner
    finally:
        cleaner.clean_all_tables(session)


# Weak reference tracking for detecting leaks
class WeakRefTracker:
    """Track objects using weak references to detect leaks."""

    def __init__(self):
        self.tracked_objects = []
        self.weak_refs = []

    def track(self, obj: Any) -> None:
        """Track an object."""
        self.tracked_objects.append(obj)
        self.weak_refs.append(weakref.ref(obj))

    def check_leaks(self) -> list[Any]:
        """Check for leaked objects."""
        leaked = []
        for i, weak_ref in enumerate(self.weak_refs):
            if weak_ref() is not None:
                leaked.append(self.tracked_objects[i])
        return leaked

    def cleanup(self) -> None:
        """Clear tracking."""
        self.tracked_objects.clear()
        self.weak_refs.clear()


@pytest.fixture
def weak_ref_tracker() -> Generator[WeakRefTracker, None, None]:
    """Provide a weak reference tracker."""
    tracker = WeakRefTracker()

    try:
        yield tracker
    finally:
        tracker.cleanup()


# Test timing utilities
class TimingTracker:
    """Time test execution for performance verification."""

    def __init__(self, max_duration: float | None = None):
        self.max_duration = max_duration
        self.start_time = None
        self.end_time = None

    def start(self) -> None:
        """Start timing."""
        self.start_time = time.perf_counter()

    def stop(self) -> float:
        """Stop timing and return duration."""
        self.end_time = time.perf_counter()
        return self.duration

    @property
    def duration(self) -> float:
        """Get current duration."""
        if self.start_time is None:
            return 0.0
        return (self.end_time or time.perf_counter()) - self.start_time

    def check_max_duration(self) -> bool:
        """Check if duration exceeds maximum."""
        if self.max_duration is None:
            return True
        return self.duration <= self.max_duration


@pytest.fixture
def test_timer() -> Generator[TimingTracker, None, None]:
    """Provide a test timer."""
    timer = TimingTracker()

    yield timer

    # Auto-check duration if max is set
    if timer.max_duration is not None and not timer.check_max_duration():
        pytest.fail(f"Test exceeded maximum duration of {timer.max_duration}s")


# Context manager for timing
@contextmanager
def timed(
    max_duration: float | None = None,
) -> Generator[TimingTracker, None, None]:
    """Context manager for timing operations."""
    timer = TimingTracker(max_duration)
    timer.start()

    try:
        yield timer
    finally:
        timer.stop()

        if max_duration is not None and not timer.check_max_duration():
            pytest.fail(
                f"Operation exceeded maximum duration of {max_duration}s"
            )
