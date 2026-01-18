"""Enhanced pytest configuration with comprehensive fixtures."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from collections.abc import AsyncGenerator, Callable, Generator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from pydantic import BaseModel
from sqlalchemy import (
    Column,
    Engine,
    Integer,
    StaticPool,
    String,
    text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    sessionmaker,
)
from sqlalchemy.pool import QueuePool

from sqlatypemodel import LazyMutableMixin, ModelType, MutableMixin
from sqlatypemodel.util.sqlalchemy import create_async_engine, create_engine

# Import our new factories
from tests.factories import (
    EagerTestModel,
    LazyTestModel,
    ModelFactory,
    NestedTestModel,
    PerformanceTestModel,
    TestDataFactory,
)

# Configure logging for tests
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Suppress noisy logs during testing
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)


# Simple test models for edge case testing
class EagerTestModelSimple(MutableMixin, BaseModel):
    """Simple eager model for edge case testing with minimal fields."""

    data: dict[str, Any] | None = None
    items: list[Any] | None = None


class LazyTestModelSimple(LazyMutableMixin, BaseModel):
    """Simple lazy model for edge case testing with minimal fields."""

    data: dict[str, Any] | None = None
    items: list[Any] | None = None


# Export aliases for convenience - use simple versions for edge case testing
LazyModel = LazyTestModelSimple
EagerModel = EagerTestModelSimple


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models in tests."""

    pass


# SQLAlchemy entity models for testing
class UserEntity(Base):
    """Test entity using eager model."""

    __tablename__ = "users_eager"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    settings = Column(ModelType(EagerTestModel), nullable=False)


class LazyUserEntity(Base):
    """Test entity using lazy model."""

    __tablename__ = "users_lazy"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    settings = Column(ModelType(LazyTestModel), nullable=False)


class NestedEntity(Base):
    """Test entity for nested models."""

    __tablename__ = "nested_entities"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    data = Column(ModelType(NestedTestModel), nullable=False)


# Database fixtures
@pytest.fixture(scope="session")
def sqlite_memory_engine() -> Generator[Engine, None, None]:
    """In-memory SQLite engine for fast testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,  # Disable SQL echo for cleaner test output
    )

    # Create all tables
    Base.metadata.create_all(engine)

    yield engine

    engine.dispose()


@pytest.fixture(scope="session")
def sqlite_file_engine() -> Generator[Engine, None, None]:
    """File-based SQLite engine for persistence testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    try:
        engine = create_engine(
            f"sqlite:///{db_path}",
            poolclass=QueuePool,
            pool_pre_ping=True,
            echo=False,
        )

        Base.metadata.create_all(engine)
        yield engine

    finally:
        engine.dispose()
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.fixture
def session(sqlite_memory_engine: Engine) -> Generator[Session, None, None]:
    """Fresh session for each test."""
    connection = sqlite_memory_engine.connect()
    transaction = connection.begin()

    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()

    # Ensure clean state
    session.execute(text("DELETE FROM users_eager"))
    session.execute(text("DELETE FROM users_lazy"))
    session.execute(text("DELETE FROM nested_entities"))
    session.commit()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def persistent_session(
    sqlite_file_engine: Engine,
) -> Generator[Session, None, None]:
    """Session that persists data across the test."""
    SessionLocal = sessionmaker(bind=sqlite_file_engine)
    session = SessionLocal()

    yield session

    session.close()


# Context managers for testing
@contextmanager
def performance_context() -> Generator[Callable[[], float], None, None]:
    """Context manager for performance measurements."""
    import time

    start_time = time.perf_counter()

    def get_elapsed() -> float:
        return time.perf_counter() - start_time

    yield get_elapsed


@pytest.fixture
def performance_timer() -> Generator[Callable[[], float], None, None]:
    """Performance timer fixture."""
    with performance_context() as timer:
        yield timer


# Model fixtures with enhanced capabilities
@pytest.fixture
def eager_user_model() -> EagerTestModel:
    """Create a standard eager model with test data."""
    return ModelFactory.create_eager_model()


@pytest.fixture
def lazy_user_model() -> LazyTestModel:
    """Create a standard lazy model with test data."""
    return ModelFactory.create_lazy_model()


@pytest.fixture
def nested_model_hierarchy() -> list[NestedTestModel]:
    """Create a hierarchy of nested models."""
    models = []

    # Create root level
    for i in range(3):
        root = NestedTestModel(
            id=f"root_{i}",
            name=f"Root Model {i}",
            metadata={"level": "root", "index": i},
        )

        # Create children
        for j in range(2):
            child = NestedTestModel(
                id=f"child_{i}_{j}",
                name=f"Child Model {i}-{j}",
                metadata={"level": "child", "parent": root.id, "index": j},
            )

            # Create grandchildren
            for k in range(2):
                grandchild = NestedTestModel(
                    id=f"grandchild_{i}_{j}_{k}",
                    name=f"Grandchild Model {i}-{j}-{k}",
                    metadata={
                        "level": "grandchild",
                        "parent": child.id,
                        "root": root.id,
                        "index": k,
                    },
                )
                child.children.append(grandchild)

            root.children.append(child)
            models.append(child)

        models.append(root)

    return models


@pytest.fixture
def large_dataset_models() -> list[EagerTestModel]:
    """Create a large dataset for performance testing."""
    return ModelFactory.create_model_batch(1000)


@pytest.fixture
def edge_case_models() -> dict[str, EagerTestModel]:
    """Create models covering edge cases."""
    factory = TestDataFactory()
    edge_data = factory.create_edge_case_data()

    models = {}

    # Empty values model
    models["empty"] = ModelFactory.create_eager_model(
        **edge_data["empty_values"],
        username="empty_user",
    )

    # Extreme values model
    models["extreme"] = ModelFactory.create_eager_model(
        settings=edge_data["extreme_values"],
        username="extreme_user",
    )

    # Special strings model
    models["strings"] = ModelFactory.create_eager_model(
        settings={"special_strings": edge_data["special_strings"]},
        username="strings_user",
    )

    return models


# Database entity fixtures
@pytest.fixture
def user_entity(
    session: Session, eager_user_model: EagerTestModel
) -> UserEntity:
    """Create a user entity with eager model."""
    entity = UserEntity(
        username=eager_user_model.username,
        settings=eager_user_model,
    )
    session.add(entity)
    session.commit()
    session.refresh(entity)
    return entity


@pytest.fixture
def lazy_user_entity(
    session: Session, lazy_user_model: LazyTestModel
) -> LazyUserEntity:
    """Create a user entity with lazy model."""
    entity = LazyUserEntity(
        username=lazy_user_model.username,
        settings=lazy_user_model,
    )
    session.add(entity)
    session.commit()
    session.refresh(entity)
    return entity


@pytest.fixture
def nested_entity(
    session: Session, nested_model_hierarchy: list[NestedTestModel]
) -> NestedEntity:
    """Create a nested entity."""
    root_model = nested_model_hierarchy[-1]  # Get the last root model
    entity = NestedEntity(
        name=root_model.name,
        data=root_model,
    )
    session.add(entity)
    session.commit()
    session.refresh(entity)
    return entity


# Utility fixtures
@pytest.fixture
def temp_directory() -> Generator[Path, None, None]:
    """Temporary directory for file-based tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def mock_time() -> Generator[Callable[[float], None], None, None]:
    """Mock time.time() for deterministic testing."""
    import time

    original_time = time.time
    current_time = 0.0

    def set_time(t: float) -> None:
        nonlocal current_time
        current_time = t

    def mock_time_func() -> float:
        return current_time

    time.time = mock_time_func
    yield set_time
    time.time = original_time


# Test data fixtures
@pytest.fixture
def serialization_test_data() -> dict[str, Any]:
    """Comprehensive data for serialization testing."""
    return {
        "simple": {"key": "value", "number": 42},
        "complex": {
            "nested": {"deep": {"deeper": "value"}},
            "list": [1, 2, {"nested": "item"}],
            "mixed": ["string", 123, {"dict": True}, [1, 2, 3]],
        },
        "datetime": datetime.now(timezone.utc).isoformat(),
        "uuid": str(uuid4()),
        "large_int": 123456789012345678901234567890,
    }


@pytest.fixture
def mutation_scenarios() -> dict[str, Callable[[EagerTestModel], None]]:
    """Common mutation scenarios for testing."""

    def append_to_list(model: BaseModel) -> None:
        model.tags.append("new_tag")

    def update_dict(model: BaseModel) -> None:
        model.settings["new_key"] = "new_value"

    def nested_mutation(model: BaseModel) -> None:
        if "nested" not in model.settings:
            model.settings["nested"] = {}
        model.settings["nested"]["deep"] = {"value": "changed"}

    def remove_from_list(model: BaseModel) -> None:
        if model.tags:
            model.tags.pop(0)

    def clear_dict(model: BaseModel) -> None:
        model.settings.clear()

    return {
        "append_to_list": append_to_list,
        "update_dict": update_dict,
        "nested_mutation": nested_mutation,
        "remove_from_list": remove_from_list,
        "clear_dict": clear_dict,
    }


# Error scenario fixtures
@pytest.fixture
def error_scenarios() -> dict[str, Callable[[], Exception]]:
    """Common error scenarios for testing."""

    def create_invalid_model() -> ValueError:
        return ValueError("Invalid model data")

    def create_serialization_error() -> TypeError:
        return TypeError("Cannot serialize object")

    def create_deserialization_error() -> json.JSONDecodeError:
        return json.JSONDecodeError("Invalid JSON", "", 0)

    return {
        "invalid_model": create_invalid_model,
        "serialization_error": create_serialization_error,
        "deserialization_error": create_deserialization_error,
    }


# Performance testing fixtures
@pytest.fixture
def benchmark_config() -> dict[str, Any]:
    """Configuration for benchmark testing."""
    return {
        "iterations": 1000,
        "warmup_iterations": 100,
        "max_time": 1.0,  # seconds
        "min_rounds": 5,
    }


@pytest.fixture
def memory_profiler() -> Generator[Callable[[], dict[str, int]], None, None]:
    """Memory profiler fixture for testing."""
    import os

    import psutil

    def get_memory_usage() -> dict[str, int]:
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        return {
            "rss": memory_info.rss,  # Resident Set Size
            "vms": memory_info.vms,  # Virtual Memory Size
        }

    yield get_memory_usage


# Async testing fixtures (for async SQLAlchemy)
@pytest.fixture(scope="session")
def event_loop() -> Generator[Any, None, None]:
    """Create an instance of the default event loop for the test session."""

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_sqlite_engine() -> AsyncGenerator[Any, None]:
    """Async SQLite engine for async testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def async_session(async_sqlite_engine: Any) -> AsyncGenerator[Any, None]:
    """Async session fixture."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    async_session_maker = async_sessionmaker(
        async_sqlite_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session


# Export test models for other tests to import
__all__ = [
    "Base",
    "UserEntity",
    "LazyUserEntity",
    "NestedEntity",
    "EagerTestModel",
    "LazyTestModel",
    "NestedTestModel",
    "PerformanceTestModel",
    "EagerTestModelSimple",
    "LazyTestModelSimple",
    "sqlite_memory_engine",
    "sqlite_file_engine",
    "session",
    "persistent_session",
    "performance_timer",
    "eager_user_model",
    "lazy_user_model",
    "nested_model_hierarchy",
    "large_dataset_models",
    "edge_case_models",
    "user_entity",
    "lazy_user_entity",
    "nested_entity",
    "temp_directory",
    "mock_time",
    "serialization_test_data",
    "mutation_scenarios",
    "error_scenarios",
    "benchmark_config",
    "memory_profiler",
    "event_loop",
    "async_sqlite_engine",
    "async_session",
    "LazyModel",
    "EagerModel",
]
