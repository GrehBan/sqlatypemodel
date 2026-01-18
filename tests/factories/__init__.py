"""Comprehensive test factories for sqlatypemodel testing.

Provides factory methods and builders for creating test data with realistic scenarios.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, Field
from typing_extensions import Self

from sqlatypemodel import LazyMutableMixin, MutableMixin


class TestDataFactory:
    """Factory for creating comprehensive test data."""

    @staticmethod
    def create_user_data(
        *,
        user_id: UUID | None = None,
        username: str | None = None,
        email: str | None = None,
        is_active: bool = True,
        created_at: datetime | None = None,
        settings: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create realistic user test data."""
        user_id = user_id or uuid4()
        username = username or f"user_{user_id.hex[:8]}"
        email = email or f"{username}@example.com"
        created_at = created_at or datetime.now(timezone.utc)
        settings = settings or {
            "theme": "dark" if user_id.int % 2 else "light",
            "notifications": user_id.int % 3 != 0,
            "language": "en",
            "preferences": {
                "auto_save": True,
                "public_profile": user_id.int % 5 != 0,
            },
        }
        tags = tags or [f"tag_{i}" for i in range(user_id.int % 5 + 1)]

        return {
            "user_id": str(user_id),
            "username": username,
            "email": email,
            "is_active": is_active,
            "created_at": created_at.isoformat(),
            "settings": settings,
            "tags": tags,
        }

    @staticmethod
    def create_nested_collection_data(
        depth: int = 3,
        width: int = 3,
        include_cycles: bool = False,
    ) -> dict[str, Any]:
        """Create deeply nested collection data for testing recursion limits."""

        def _create_level(current_depth: int) -> dict[str, Any]:
            if current_depth <= 0:
                return {"leaf": True, "value": f"leaf_{uuid4().hex[:8]}"}

            return {
                "level": current_depth,
                "items": [
                    _create_level(current_depth - 1) for _ in range(width)
                ],
                "metadata": {
                    "depth": current_depth,
                    "width": width,
                    "path": [f"level_{i}" for i in range(current_depth)],
                },
            }

        data = _create_level(depth)
        if include_cycles:
            # Create a reference cycle for testing cycle detection
            data["cycle_ref"] = data

        return data

    @staticmethod
    def create_performance_test_data(
        *,
        list_size: int = 1000,
        dict_size: int = 100,
        nested_objects: int = 10,
    ) -> dict[str, Any]:
        """Create data optimized for performance testing."""
        return {
            "large_list": [f"item_{i}" for i in range(list_size)],
            "large_dict": {f"key_{i}": f"value_{i}" for i in range(dict_size)},
            "nested_objects": [
                {
                    "id": i,
                    "data": list(range(10)),
                    "metadata": {"index": i, "processed": True},
                }
                for i in range(nested_objects)
            ],
        }

    @staticmethod
    def create_edge_case_data() -> dict[str, Any]:
        """Create data covering edge cases and boundary conditions."""
        return {
            "empty_values": {
                "empty_string": "",
                "empty_list": [],
                "empty_dict": {},
                "none_value": None,
            },
            "extreme_values": {
                "large_int": 9223372036854775807,  # Max 64-bit int
                "small_int": -9223372036854775808,  # Min 64-bit int
                "too_large_int": 9223372036854775808,  # Triggers fallback
                "very_large_int": 123456789012345678901234567890,
                "float_infinity": float("inf"),
                "float_nan": float("nan"),
                "unicode": "🚀 emoji and 中文 characters",
            },
            "special_strings": [
                "quotes: 'single' and \"double\"",
                "newlines\nand\ttabs\r\ncarriage",
                "backslashes \\ and forward /",
                "json {}",
                "xml <>",
                "yaml ---",
            ],
        }


class ModelFactory:
    """Factory for creating test model instances."""

    @staticmethod
    def create_eager_model(**kwargs: Any) -> EagerTestModel:
        """Create an EagerTestModel with sensible defaults."""
        defaults = TestDataFactory.create_user_data()
        defaults.update(kwargs)
        return EagerTestModel(**defaults)

    @staticmethod
    def create_lazy_model(**kwargs: Any) -> LazyTestModel:
        """Create a LazyTestModel with sensible defaults."""
        defaults = TestDataFactory.create_user_data()
        defaults.update(kwargs)
        return LazyTestModel(**defaults)

    @staticmethod
    def create_model_batch(
        count: int,
        model_type: type[EagerTestModel] | None = None,
        **common_kwargs: Any,
    ) -> list[EagerTestModel]:
        """Create a batch of models with varying data."""
        models = []

        for i in range(count):
            kwargs = common_kwargs.copy()
            kwargs.update(
                {
                    "user_id": str(uuid4()),
                    "username": f"user_batch_{i}",
                    "email": f"user{i}@batch.example.com",
                }
            )
            models.append(ModelFactory.create_eager_model(**kwargs))

        return models


class EagerTestModel(MutableMixin, BaseModel):
    """Test model for eager loading scenarios."""

    user_id: str
    username: str
    email: str
    is_active: bool = True
    created_at: str
    settings: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

    model_config = {
        "extra": "allow",
        "validate_assignment": True,
    }


class LazyTestModel(LazyMutableMixin, BaseModel):
    """Test model for lazy loading scenarios."""

    user_id: str
    username: str
    email: str
    is_active: bool = True
    created_at: str
    settings: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

    model_config = {
        "extra": "allow",
        "validate_assignment": True,
    }


class NestedTestModel(MutableMixin, BaseModel):
    """Test model for nested object scenarios."""

    id: str
    name: str
    children: list[Self] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"validate_assignment": True}


class PerformanceTestModel(MutableMixin, BaseModel):
    """Test model optimized for performance testing."""

    data: list[int] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    nested: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"validate_assignment": True}


# Protocol for test models to ensure type safety
class TestModelProtocol(Protocol):
    """Protocol for test models used in testing."""

    user_id: str
    username: str
    email: str
    is_active: bool
    created_at: str
    settings: dict[str, Any]
    tags: list[str]


# Fixtures for pytest
@pytest.fixture
def test_data_factory() -> type[TestDataFactory]:
    """Provide the TestDataFactory class."""
    return TestDataFactory


@pytest.fixture
def model_factory() -> type[ModelFactory]:
    """Provide the ModelFactory class."""
    return ModelFactory


@pytest.fixture
def sample_user_data() -> dict[str, Any]:
    """Provide sample user data for testing."""
    return TestDataFactory.create_user_data()


@pytest.fixture
def nested_test_data() -> dict[str, Any]:
    """Provide deeply nested test data."""
    return TestDataFactory.create_nested_collection_data()


@pytest.fixture
def performance_test_data() -> dict[str, Any]:
    """Provide performance test data."""
    return TestDataFactory.create_performance_test_data()


@pytest.fixture
def edge_case_data() -> dict[str, Any]:
    """Provide edge case test data."""
    return TestDataFactory.create_edge_case_data()


@pytest.fixture
def eager_model() -> EagerTestModel:
    """Provide an eager test model instance."""
    return ModelFactory.create_eager_model()


@pytest.fixture
def lazy_model() -> LazyTestModel:
    """Provide a lazy test model instance."""
    return ModelFactory.create_lazy_model()


@pytest.fixture
def model_batch() -> list[EagerTestModel]:
    """Provide a batch of test models."""
    return ModelFactory.create_model_batch(10)


@pytest.fixture
def nested_models() -> list[NestedTestModel]:
    """Provide nested test models with relationships."""
    root = NestedTestModel(id="root", name="Root")
    child1 = NestedTestModel(id="child1", name="Child 1")
    child2 = NestedTestModel(id="child2", name="Child 2")
    grandchild = NestedTestModel(id="grandchild", name="Grandchild")

    child1.children.append(grandchild)
    root.children.extend([child1, child2])

    return [root, child1, child2, grandchild]
