"""Integration tests with real database systems.

Tests sqlatypemodel with actual database backends to ensure
production-ready behavior and compatibility.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import pytest
from sqlalchemy import (
    Column,
    Integer,
    String,
    text,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase, Session
from tests.factories import EagerTestModel, LazyTestModel, ModelFactory

from sqlatypemodel import ModelType
from sqlatypemodel.util.sqlalchemy import create_async_engine, create_engine


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models in integration tests."""

    pass


# Test entities for integration testing
class EagerUserEntity(Base):
    """Entity for testing eager models."""

    __tablename__ = "eager_users"

    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), nullable=False)
    settings = Column(ModelType(EagerTestModel), nullable=False)


class LazyUserEntity(Base):
    """Entity for testing lazy models."""

    __tablename__ = "lazy_users"

    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), nullable=False)
    settings = Column(ModelType(LazyTestModel), nullable=False)


class DatabaseTestConfig:
    """Configuration for database testing."""

    def __init__(self):
        self.postgresql_url = os.getenv("TEST_POSTGRESQL_URL")
        self.mysql_url = os.getenv("TEST_MYSQL_URL")
        self.sqlite_url = "sqlite:///test_integration.db"
        self.sqlite_memory_url = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def db_config() -> DatabaseTestConfig:
    """Provide database configuration."""
    return DatabaseTestConfig()


@contextmanager
def postgresql_engine(
    db_config: DatabaseTestConfig,
) -> Generator[Any, None, None]:
    """Context manager for PostgreSQL testing."""
    if not db_config.postgresql_url:
        pytest.skip("PostgreSQL not configured")

    engine = create_engine(db_config.postgresql_url)

    try:
        # Create tables
        Base.metadata.create_all(engine)
        yield engine
    except Exception as e:
        if "connection" in str(e).lower():
            pytest.skip("PostgreSQL connection failed")
        raise
    finally:
        # Clean up
        Base.metadata.drop_all(engine)
        engine.dispose()


@contextmanager
def mysql_engine(db_config: DatabaseTestConfig) -> Generator[Any, None, None]:
    """Context manager for MySQL testing."""
    if not db_config.mysql_url:
        pytest.skip("MySQL not configured")

    engine = create_engine(db_config.mysql_url)

    try:
        # Create tables
        Base.metadata.create_all(engine)
        yield engine
    except Exception as e:
        if "connection" in str(e).lower():
            pytest.skip("MySQL connection failed")
        raise
    finally:
        # Clean up
        Base.metadata.drop_all(engine)
        engine.dispose()


@contextmanager
def sqlite_file_engine(
    db_config: DatabaseTestConfig,
) -> Generator[Any, None, None]:
    """Context manager for SQLite file testing."""
    engine = create_engine(db_config.sqlite_url)

    try:
        # Create tables
        Base.metadata.create_all(engine)
        yield engine
    finally:
        # Clean up
        Base.metadata.drop_all(engine)
        engine.dispose()

        # Remove database file
        if os.path.exists("test_integration.db"):
            os.unlink("test_integration.db")


@pytest.fixture
def postgresql_session(
    db_config: DatabaseTestConfig,
) -> Generator[Session, None, None]:
    """Provide PostgreSQL session for testing."""
    with postgresql_engine(db_config) as engine:
        with Session(engine) as session:
            yield session


@pytest.fixture
def mysql_session(
    db_config: DatabaseTestConfig,
) -> Generator[Session, None, None]:
    """Provide MySQL session for testing."""
    with mysql_engine(db_config) as engine:
        with Session(engine) as session:
            yield session


@pytest.fixture
def sqlite_file_session(
    db_config: DatabaseTestConfig,
) -> Generator[Session, None, None]:
    """Provide SQLite file session for testing."""
    with sqlite_file_engine(db_config) as engine:
        with Session(engine) as session:
            yield session


class TestSQLiteIntegration:
    """Integration tests with SQLite database."""

    def test_sqlite_crud_operations(self) -> None:
        """Test CRUD operations with SQLite."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        with Session(engine) as session:
            # Create
            model = ModelFactory.create_eager_model()
            entity = EagerUserEntity(
                username=model.username, email=model.email, settings=model
            )
            session.add(entity)
            session.commit()
            session.refresh(entity)

            # Read
            loaded_entity = (
                session.query(EagerUserEntity)
                .filter_by(username=model.username)
                .first()
            )
            assert loaded_entity is not None
            assert loaded_entity.settings.user_id == model.user_id
            assert loaded_entity.settings.username == model.username

            # Update
            loaded_entity.settings.tags.append("sqlite_test")
            loaded_entity.settings.settings["sqlite_key"] = True
            session.commit()

            # Verify update
            updated_entity = (
                session.query(EagerUserEntity)
                .filter_by(username=model.username)
                .first()
            )
            assert "sqlite_test" in updated_entity.settings.tags
            assert updated_entity.settings.settings["sqlite_key"] is True

            # Delete
            session.delete(updated_entity)
            session.commit()

            # Verify deletion
            deleted_entity = (
                session.query(EagerUserEntity)
                .filter_by(username=model.username)
                .first()
            )
            assert deleted_entity is None

    def test_sqlite_lazy_model_integration(self) -> None:
        """Test lazy model integration with SQLite."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        with Session(engine) as session:
            # Create with lazy model
            model = ModelFactory.create_lazy_model()
            entity = LazyUserEntity(
                username=model.username, email=model.email, settings=model
            )
            session.add(entity)
            session.commit()
            session.refresh(entity)

            # Access lazy-loaded data
            _ = entity.settings.tags  # Trigger lazy loading
            _ = entity.settings.settings  # Trigger lazy loading

            # Test mutations after lazy loading
            entity.settings.tags.append("lazy_sqlite_test")
            entity.settings.settings["lazy_sqlite_key"] = True
            session.commit()

            # Verify mutations persisted
            updated_entity = (
                session.query(LazyUserEntity)
                .filter_by(username=model.username)
                .first()
            )
            _ = updated_entity.settings.tags  # Trigger lazy loading
            assert "lazy_sqlite_test" in updated_entity.settings.tags
            assert updated_entity.settings.settings["lazy_sqlite_key"] is True

    def test_sqlite_transaction_isolation(self) -> None:
        """Test transaction isolation with SQLite."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        with Session(engine) as session1:
            with Session(engine) as session2:
                # Start transaction in session1
                model1 = ModelFactory.create_eager_model(username="user1")
                entity1 = EagerUserEntity(
                    username="user1",
                    email="user1@example.com",
                    settings=model1,
                )
                session1.add(entity1)

                # Should not be visible in session2 yet
                entity2 = (
                    session2.query(EagerUserEntity)
                    .filter_by(username="user1")
                    .first()
                )
                assert entity2 is None

                # Commit session1
                session1.commit()

                # Should be visible in session2 now
                entity2 = (
                    session2.query(EagerUserEntity)
                    .filter_by(username="user1")
                    .first()
                )
                assert entity2 is not None
                assert entity2.settings.username == "user1"


@pytest.mark.postgres
class TestPostgreSQLIntegration:
    """Integration tests with PostgreSQL."""

    def test_postgresql_json_functionality(
        self, postgresql_session: Session
    ) -> None:
        """Test PostgreSQL-specific JSON functionality."""
        session = postgresql_session

        # Create entity with complex JSON data
        model = ModelFactory.create_eager_model()
        model.settings["postgresql_features"] = {
            "array_type": [1, 2, 3],
            "nested_json": {"deep": "value"},
            "null_value": None,
        }

        entity = EagerUserEntity(
            username=model.username, email=model.email, settings=model
        )
        session.add(entity)
        session.commit()
        session.refresh(entity)

        # Test JSON querying (PostgreSQL specific)
        result = session.execute(
            text(
                """
                SELECT settings->'postgresql_features'->'nested_json'->>'deep' as deep_value
                FROM eager_users
                WHERE username = :username
            """
            ),
            {"username": model.username},
        ).fetchone()

        assert result is not None
        assert result.deep_value == "value"

    def test_postgresql_large_json_handling(
        self, postgresql_session: Session
    ) -> None:
        """Test handling of large JSON documents in PostgreSQL."""
        session = postgresql_session

        # Create large JSON data
        large_data = {
            "large_array": [f"item_{i}" for i in range(1000)],
            "large_dict": {f"key_{i}": f"value_{i}" for i in range(100)},
            "nested": {
                f"level_{i}": {
                    f"subkey_{j}": f"subvalue_{j}" for j in range(10)
                }
                for i in range(10)
            },
        }

        model = ModelFactory.create_eager_model()
        model.settings.update(large_data)

        entity = EagerUserEntity(
            username=model.username, email=model.email, settings=model
        )
        session.add(entity)
        session.commit()
        session.refresh(entity)

        # Verify large data handling
        assert len(entity.settings["large_array"]) == 1000
        assert len(entity.settings["large_dict"]) == 100
        assert len(entity.settings["nested"]) == 10

        # Test mutation of large data
        entity.settings["large_array"].append("new_item")
        session.commit()

        updated_entity = (
            session.query(EagerUserEntity)
            .filter_by(username=model.username)
            .first()
        )
        assert len(updated_entity.settings["large_array"]) == 1001


@pytest.mark.mysql
class TestMySQLIntegration:
    """Integration tests with MySQL."""

    def test_mysql_json_functionality(self, mysql_session: Session) -> None:
        """Test MySQL-specific JSON functionality."""
        session = mysql_session

        # Create entity with JSON data
        model = ModelFactory.create_eager_model()
        model.settings["mysql_features"] = {
            "json_extract_test": "extract_me",
            "json_path_test": {"nested": "value"},
        }

        entity = EagerUserEntity(
            username=model.username, email=model.email, settings=model
        )
        session.add(entity)
        session.commit()
        session.refresh(entity)

        # Test JSON extraction (MySQL specific)
        result = session.execute(
            text(
                """
                SELECT JSON_EXTRACT(settings, '$.mysql_features.json_extract_test') as extracted_value
                FROM eager_users
                WHERE username = :username
            """
            ),
            {"username": model.username},
        ).fetchone()

        assert result is not None
        assert '"extract_me"' in str(result.extracted_value)

    def test_mysql_utf8_handling(self, mysql_session: Session) -> None:
        """Test UTF-8 character handling in MySQL."""
        session = mysql_session

        # Create model with Unicode characters
        model = ModelFactory.create_eager_model(
            username="mysql_用户_🚀", email="mysql@example.com"
        )
        model.settings["unicode_data"] = {
            "chinese": "中文测试",
            "emoji": "🎉🔥💯",
            "mixed": "Mix 中文 with 🚀 emojis",
        }

        entity = EagerUserEntity(
            username=model.username, email=model.email, settings=model
        )
        session.add(entity)
        session.commit()
        session.refresh(entity)

        # Verify Unicode handling
        assert entity.settings["unicode_data"]["chinese"] == "中文测试"
        assert entity.settings["unicode_data"]["emoji"] == "🎉🔥💯"
        assert (
            entity.settings["unicode_data"]["mixed"]
            == "Mix 中文 with 🚀 emojis"
        )

        # Test mutation of Unicode data
        entity.settings["unicode_data"]["new_unicode"] = "✨ 新内容"
        session.commit()

        updated_entity = (
            session.query(EagerUserEntity)
            .filter_by(username=model.username)
            .first()
        )
        assert (
            updated_entity.settings["unicode_data"]["new_unicode"]
            == "✨ 新内容"
        )


class TestAsyncIntegration:
    """Integration tests with async SQLAlchemy."""

    @pytest.mark.asyncio
    async def test_async_sqlite_integration(self) -> None:
        """Test async integration with SQLite."""
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async_session_maker = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async with async_session_maker() as session:
            # Create with async session
            model = ModelFactory.create_eager_model()
            entity = EagerUserEntity(
                username=model.username, email=model.email, settings=model
            )
            session.add(entity)
            await session.commit()
            await session.refresh(entity)

            # Test mutations
            entity.settings.tags.append("async_test")
            entity.settings.settings["async_key"] = True
            await session.commit()

            # Verify mutations
            result = await session.get(EagerUserEntity, entity.id)
            assert "async_test" in result.settings.tags
            assert result.settings.settings["async_key"] is True

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_async_concurrent_operations(self) -> None:
        """Test concurrent async operations."""
        import asyncio

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async_session_maker = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async def create_user(user_id: int):
            async with async_session_maker() as session:
                model = ModelFactory.create_eager_model(
                    username=f"async_user_{user_id}"
                )
                entity = EagerUserEntity(
                    username=model.username,
                    email=f"user_{user_id}@example.com",
                    settings=model,
                )
                session.add(entity)
                await session.commit()
                await session.refresh(entity)
                return entity

        # Create multiple users concurrently
        tasks = [create_user(i) for i in range(10)]
        entities = await asyncio.gather(*tasks)

        # Verify all users were created
        assert len(entities) == 10

        async with async_session_maker() as session:
            all_users = await session.execute(
                text("SELECT COUNT(*) FROM eager_users")
            )
            count = all_users.scalar()
            assert count == 10

        await engine.dispose()


class TestMultiDatabaseCompatibility:
    """Test compatibility across different database backends."""

    @pytest.mark.parametrize(
        "session_fixture",
        [
            "sqlite_file_session",
            pytest.param("postgresql_session", marks=pytest.mark.postgres),
            pytest.param("mysql_session", marks=pytest.mark.mysql),
        ],
    )
    def test_cross_database_behavior(self, request, session_fixture) -> None:
        """Test consistent behavior across databases."""
        session = request.getfixturevalue(session_fixture)

        # Test model creation and basic operations
        model = ModelFactory.create_eager_model()

        # Add some test data
        model.tags.extend(["cross_db_test1", "cross_db_test2"])
        model.settings["cross_db"] = {
            "nested": {"value": "test"},
            "array": [1, 2, 3],
            "unicode": "🚀 test",
        }

        entity = EagerUserEntity(
            username=model.username, email=model.email, settings=model
        )
        session.add(entity)
        session.commit()
        session.refresh(entity)

        # Test roundtrip consistency
        assert entity.settings.user_id == model.user_id
        assert entity.settings.tags == model.tags
        assert (
            entity.settings.settings["cross_db"]["nested"]["value"] == "test"
        )
        assert entity.settings.settings["cross_db"]["array"] == [1, 2, 3]
        assert entity.settings.settings["cross_db"]["unicode"] == "🚀 test"

        # Test mutations
        entity.settings.tags.append("after_mutation")
        entity.settings.settings["cross_db"]["mutated"] = True
        session.commit()

        # Verify mutations
        updated_entity = (
            session.query(EagerUserEntity)
            .filter_by(username=model.username)
            .first()
        )
        assert "after_mutation" in updated_entity.settings.tags
        assert updated_entity.settings.settings["cross_db"]["mutated"] is True


class TestDatabaseMigrationScenarios:
    """Test database migration and schema evolution scenarios."""

    def test_schema_evolution_handling(self) -> None:
        """Test handling of schema evolution."""
        # Create initial schema
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        with Session(engine) as session:
            # Create data with current schema
            model = ModelFactory.create_eager_model()
            model.settings["migration_test"] = {
                "version": "1.0",
                "data": "old",
            }

            entity = EagerUserEntity(
                username=model.username, email=model.email, settings=model
            )
            session.add(entity)
            session.commit()

            # Simulate schema evolution by modifying model
            loaded_entity = session.query(EagerUserEntity).first()

            # Add new fields that weren't in original schema
            loaded_entity.settings.settings["migration_test"][
                "version"
            ] = "2.0"
            loaded_entity.settings.settings["migration_test"][
                "new_field"
            ] = "new_value"
            loaded_entity.settings.settings["migration_test"][
                "deprecated_field"
            ] = None

            session.commit()

            # Verify evolution worked
            evolved_entity = session.query(EagerUserEntity).first()
            assert (
                evolved_entity.settings.settings["migration_test"]["version"]
                == "2.0"
            )
            assert (
                evolved_entity.settings.settings["migration_test"]["new_field"]
                == "new_value"
            )
            assert (
                evolved_entity.settings.settings["migration_test"][
                    "deprecated_field"
                ]
                is None
            )

    def test_backward_compatibility(self) -> None:
        """Test backward compatibility with older data."""
        # Simulate loading data that might have different structure
        old_json_data = {
            "user_id": "old_user",
            "username": "old_user",
            "email": "old@example.com",
            "is_active": True,
            "created_at": "2024-01-01T00:00:00Z",
            # Missing tags and settings that are in new schema
        }

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        with Session(engine) as session:
            # Insert raw JSON data
            session.execute(
                text(
                    """
                    INSERT INTO eager_users (username, email, settings)
                    VALUES (:username, :email, :settings)
                """
                ),
                {
                    "username": old_json_data["username"],
                    "email": old_json_data["email"],
                    "settings": json.dumps(old_json_data),
                },
            )
            session.commit()

            # Try to load with new model
            loaded_entity = session.query(EagerUserEntity).first()

            # Should handle missing fields gracefully
            assert loaded_entity.settings.user_id == "old_user"
            # tags and settings should be None or default values
            assert hasattr(loaded_entity.settings, "tags")
            assert hasattr(loaded_entity.settings, "settings")


class TestProductionScenarios:
    """Production-like scenario testing."""

    def test_high_volume_operations(self) -> None:
        """Test high-volume operations."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        with Session(engine) as session:
            # Bulk insert
            models = []
            for i in range(1000):
                model = ModelFactory.create_eager_model(
                    username=f"bulk_user_{i}", email=f"bulk_{i}@example.com"
                )
                model.tags.extend([f"tag_{j}" for j in range(5)])
                model.settings.update(
                    {f"key_{j}": f"value_{j}" for j in range(3)}
                )

                entity = EagerUserEntity(
                    username=model.username, email=model.email, settings=model
                )
                models.append(entity)

            # Bulk insert
            start_time = time.time()
            session.add_all(models)
            session.commit()
            insert_time = time.time() - start_time

            # Bulk update
            start_time = time.time()
            for entity in session.query(EagerUserEntity).all():
                entity.settings.tags.append("bulk_updated")
                entity.settings.settings["bulk_update"] = True
            session.commit()
            update_time = time.time() - start_time

            # Bulk read
            start_time = time.time()
            all_entities = session.query(EagerUserEntity).all()
            for entity in all_entities:
                _ = entity.settings.tags
                _ = entity.settings.settings
            read_time = time.time() - start_time

            # Performance assertions
            assert insert_time < 5.0  # 1000 inserts in < 5 seconds
            assert update_time < 5.0  # 1000 updates in < 5 seconds
            assert read_time < 2.0  # 1000 reads in < 2 seconds
            assert len(all_entities) == 1000

            # Verify data integrity
            for entity in all_entities:
                assert "bulk_updated" in entity.settings.tags
                assert entity.settings.settings["bulk_update"] is True

    def test_connection_pool_behavior(self) -> None:
        """Test behavior with connection pooling."""
        from sqlalchemy.pool import QueuePool

        db_file = "pool_test.db"
        if os.path.exists(db_file):
            os.unlink(db_file)

        try:
            # Create engine with connection pooling using QueuePool
            # QueuePool is needed to support max_overflow
            engine = create_engine(
                f"sqlite:///{db_file}",
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
            )
            Base.metadata.create_all(engine)

            def create_and_modify_data(session_id: int):
                with Session(engine) as session:
                    model = ModelFactory.create_eager_model(
                        username=f"pool_user_{session_id}",
                        email=f"pool_{session_id}@example.com",
                    )
                    entity = EagerUserEntity(
                        username=model.username,
                        email=model.email,
                        settings=model,
                    )
                    session.add(entity)
                    session.commit()

                    # Modify data
                    entity.settings.tags.append(f"pool_session_{session_id}")
                    session.commit()

                    return entity.id

            # Test concurrent sessions
            import threading

            threads = []
            results = []

            def worker(session_id):
                try:
                    entity_id = create_and_modify_data(session_id)
                    results.append(entity_id)
                except Exception as e:
                    results.append(e)

            # Start multiple threads to test connection pooling
            for i in range(15):  # More than pool_size to test overflow
                t = threading.Thread(target=worker, args=(i,))
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            # Verify all operations succeeded
            assert len(results) == 15
            assert all(isinstance(r, int) for r in results)  # No errors

            # Verify data integrity
            with Session(engine) as session:
                all_users = session.query(EagerUserEntity).all()
                assert len(all_users) == 15

                for user in all_users:
                    assert user.username.startswith("pool_user_")
                    assert len(user.settings.tags) > 0
                    assert any(
                        "pool_session_" in tag for tag in user.settings.tags
                    )
        finally:
            engine.dispose()
            if os.path.exists(db_file):
                os.unlink(db_file)
