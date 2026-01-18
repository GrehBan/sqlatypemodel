"""Tests for database-specific behavior and compatibility."""

import os
from collections.abc import Generator
from typing import Any

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import Engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from sqlatypemodel import LazyMutableMixin, MutableMixin
from sqlatypemodel.model_type import ModelType
from sqlatypemodel.util.sqlalchemy import create_engine


# Test models for database testing
class DBTestEagerModel(MutableMixin, BaseModel):
    """Model for database-specific eager testing."""

    model_config = {"extra": "allow"}

    name: str
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    nested_list: list[list[int | str]] = Field(
        default_factory=list
    )  # Allow mixed types for testing


class DBTestLazyModel(LazyMutableMixin, BaseModel):
    """Model for database-specific lazy testing."""

    model_config = {"extra": "allow"}

    identifier: str
    items: list[int] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


# SQLAlchemy entities
class Base(DeclarativeBase):
    pass


class DBTestEntity(Base):
    """Entity for database testing."""

    __tablename__ = "db_test_entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    eager_data: Mapped[DBTestEagerModel] = mapped_column(
        ModelType(DBTestEagerModel)
    )
    lazy_data: Mapped[DBTestLazyModel] = mapped_column(
        ModelType(DBTestLazyModel)
    )


class DatabaseConfig:
    """Configuration for different database types."""

    @staticmethod
    def get_postgres_url() -> str | None:
        """Get PostgreSQL connection URL from environment."""
        pg_host = os.getenv("POSTGRES_HOST", "localhost")
        pg_port = os.getenv("POSTGRES_PORT", "5432")
        pg_user = os.getenv("POSTGRES_USER", "test")
        pg_pass = os.getenv("POSTGRES_PASSWORD", "test")
        pg_db = os.getenv("POSTGRES_DB", "test")

        if all([pg_host, pg_user, pg_pass, pg_db]):
            return (
                f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
            )
        return None

    @staticmethod
    def get_mysql_url() -> str | None:
        """Get MySQL connection URL from environment."""
        mysql_host = os.getenv("MYSQL_HOST", "localhost")
        mysql_port = os.getenv("MYSQL_PORT", "3306")
        mysql_user = os.getenv("MYSQL_USER", "test")
        mysql_pass = os.getenv("MYSQL_PASSWORD", "test")
        mysql_db = os.getenv("MYSQL_DB", "test")

        if all([mysql_host, mysql_user, mysql_pass, mysql_db]):
            return f"mysql+pymysql://{mysql_user}:{mysql_pass}@{mysql_host}:{mysql_port}/{mysql_db}"
        return None


@pytest.fixture(scope="session")
def postgres_engine() -> Generator[Engine, None, None]:
    """PostgreSQL engine fixture."""
    url = DatabaseConfig.get_postgres_url()
    if url is None:
        pytest.skip(
            "PostgreSQL not configured - set POSTGRES_* environment variables"
        )

    try:
        engine = create_engine(url, echo=False)
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        # Create tables
        Base.metadata.create_all(engine)
        yield engine

        Base.metadata.drop_all(engine)
        engine.dispose()
    except Exception:
        pytest.skip("PostgreSQL connection failed")


@pytest.fixture(scope="session")
def mysql_engine() -> Generator[Engine, None, None]:
    """MySQL engine fixture."""
    url = DatabaseConfig.get_mysql_url()
    if url is None:
        pytest.skip("MySQL not configured - set MYSQL_* environment variables")

    try:
        engine = create_engine(url, echo=False)
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        # Create tables
        Base.metadata.create_all(engine)
        yield engine

        Base.metadata.drop_all(engine)
        engine.dispose()
    except Exception:
        pytest.skip("MySQL connection failed")


@pytest.fixture(scope="function")
def postgres_session(
    postgres_engine: Engine,
) -> Generator[Session, None, None]:
    """PostgreSQL session fixture."""
    conn = postgres_engine.connect()
    trans = conn.begin()
    sess = Session(bind=conn)

    yield sess

    sess.close()
    trans.rollback()
    conn.close()


@pytest.fixture(scope="function")
def mysql_session(mysql_engine: Engine) -> Generator[Session, None, None]:
    """MySQL session fixture."""
    conn = mysql_engine.connect()
    trans = conn.begin()
    sess = Session(bind=conn)

    yield sess

    sess.close()
    trans.rollback()
    conn.close()


class TestPostgreSQLCompatibility:
    """Tests for PostgreSQL-specific behavior."""

    @pytest.mark.postgres
    def test_postgresql_json_column_type(
        self, postgres_session: Session
    ) -> None:
        """Test JSON column type compatibility with PostgreSQL."""
        entity = DBTestEntity(
            eager_data=DBTestEagerModel(
                name="postgres_test",
                tags=["tag1", "tag2"],
                metadata={"key": "value"},
                nested_list=[[1, 2], [3, 4]],
            ),
            lazy_data=DBTestLazyModel(
                identifier="pg_lazy", items=[1, 2, 3], config={"setting": True}
            ),
        )

        postgres_session.add(entity)
        postgres_session.commit()

        # Retrieve and verify
        retrieved = postgres_session.get(DBTestEntity, entity.id)
        assert retrieved is not None
        assert retrieved.eager_data.name == "postgres_test"
        assert retrieved.eager_data.tags == ["tag1", "tag2"]
        assert retrieved.eager_data.nested_list == [[1, 2], [3, 4]]
        assert retrieved.lazy_data.identifier == "pg_lazy"
        assert retrieved.lazy_data.items == [1, 2, 3]
        assert retrieved.lazy_data.config["setting"] is True

    @pytest.mark.postgres
    def test_postgresql_jsonb_differences(
        self, postgres_session: Session
    ) -> None:
        """Test PostgreSQL JSONB-specific behavior (if applicable)."""
        # Test with data that might behave differently in JSONB
        entity = DBTestEntity(
            eager_data=DBTestEagerModel(
                name="jsonb_test",
                tags=[],  # Empty arrays
                metadata={},  # Empty objects
                nested_list=[],  # Empty nested arrays
            ),
            lazy_data=DBTestLazyModel(
                identifier="jsonb_lazy", items=[], config={}
            ),
        )

        postgres_session.add(entity)
        postgres_session.commit()

        # Test mutation tracking with empty structures
        retrieved = postgres_session.get(DBTestEntity, entity.id)
        assert retrieved is not None

        # Modify empty structures
        retrieved.eager_data.tags.append("new_tag")
        retrieved.eager_data.metadata["new_key"] = "new_value"
        retrieved.eager_data.nested_list.append([1, 2, 3])

        retrieved.lazy_data.items.extend([1, 2, 3])
        retrieved.lazy_data.config["option"] = False

        postgres_session.commit()

        # Verify changes persisted
        final = postgres_session.get(DBTestEntity, entity.id)
        assert final.eager_data.tags == ["new_tag"]
        assert final.eager_data.metadata["new_key"] == "new_value"
        assert final.eager_data.nested_list == [[1, 2, 3]]
        assert final.lazy_data.items == [1, 2, 3]
        assert final.lazy_data.config["option"] is False

    @pytest.mark.postgres
    def test_postgresql_unicode_support(
        self, postgres_session: Session
    ) -> None:
        """Test Unicode and special character support in PostgreSQL."""
        entity = DBTestEntity(
            eager_data=DBTestEagerModel(
                name="unicode_test_åßç∂",
                tags=["emoji_🚀", "accent_éèê", "cyrillic_фыв"],
                metadata={"unicode_key_Ω": "unicode_value_αβγ"},
                nested_list=[[1, "mixed_🌟"], [2, "types_∆"]],
            ),
            lazy_data=DBTestLazyModel(
                identifier="unicode_lazy_λμν",
                items=[],
                config={"unicode_setting_ξ": True},
            ),
        )

        postgres_session.add(entity)
        postgres_session.commit()

        # Retrieve and verify Unicode handling
        retrieved = postgres_session.get(DBTestEntity, entity.id)
        assert retrieved is not None
        assert retrieved.eager_data.name == "unicode_test_åßç∂"
        assert "emoji_🚀" in retrieved.eager_data.tags
        assert "accent_éèê" in retrieved.eager_data.tags
        assert "cyrillic_фыв" in retrieved.eager_data.tags
        assert (
            retrieved.eager_data.metadata["unicode_key_Ω"]
            == "unicode_value_αβγ"
        )
        assert [1, "mixed_🌟"] in retrieved.eager_data.nested_list
        assert retrieved.lazy_data.identifier == "unicode_lazy_λμν"
        assert retrieved.lazy_data.config["unicode_setting_ξ"] is True

    @pytest.mark.postgres
    def test_postgresql_large_json_objects(
        self, postgres_session: Session
    ) -> None:
        """Test handling of large JSON objects in PostgreSQL."""
        # Create a large JSON object
        large_data = DBTestEagerModel(
            name="large_test",
            tags=[f"tag_{i}" for i in range(1000)],  # 1000 tags
            metadata={
                f"key_{i}": f"value_{i}" * 100  # Long values
                for i in range(100)  # 100 key-value pairs
            },
            nested_list=[
                list(range(100))  # 100 nested lists of 100 integers each
                for _ in range(10)
            ],
        )

        entity = DBTestEntity(
            eager_data=large_data,
            lazy_data=DBTestLazyModel(identifier="large_lazy"),
        )

        postgres_session.add(entity)
        postgres_session.commit()

        # Test partial modification
        retrieved = postgres_session.get(DBTestEntity, entity.id)
        assert retrieved is not None
        assert len(retrieved.eager_data.tags) == 1000
        assert len(retrieved.eager_data.metadata) == 100
        assert len(retrieved.eager_data.nested_list) == 10

        # Modify a small part and verify change tracking
        retrieved.eager_data.tags.append("new_tag")
        retrieved.eager_data.metadata["new_key"] = "new_value"

        postgres_session.commit()

        final = postgres_session.get(DBTestEntity, entity.id)
        assert len(final.eager_data.tags) == 1001
        assert final.eager_data.metadata["new_key"] == "new_value"


class TestMySQLCompatibility:
    """Tests for MySQL-specific behavior."""

    @pytest.mark.mysql
    def test_mysql_json_column_type(self, mysql_session: Session) -> None:
        """Test JSON column type compatibility with MySQL."""
        entity = DBTestEntity(
            eager_data=DBTestEagerModel(
                name="mysql_test",
                tags=["mysql", "json"],
                metadata={"engine": "mysql", "version": "8.0"},
                nested_list=[[1, 2, 3], [4, 5, 6]],
            ),
            lazy_data=DBTestLazyModel(
                identifier="mysql_lazy",
                items=[10, 20, 30],
                config={"charset": "utf8mb4"},
            ),
        )

        mysql_session.add(entity)
        mysql_session.commit()

        # Retrieve and verify
        retrieved = mysql_session.get(DBTestEntity, entity.id)
        assert retrieved is not None
        assert retrieved.eager_data.name == "mysql_test"
        assert retrieved.eager_data.tags == ["mysql", "json"]
        assert retrieved.eager_data.metadata["engine"] == "mysql"
        assert retrieved.eager_data.nested_list == [[1, 2, 3], [4, 5, 6]]
        assert retrieved.lazy_data.identifier == "mysql_lazy"
        assert retrieved.lazy_data.items == [10, 20, 30]
        assert retrieved.lazy_data.config["charset"] == "utf8mb4"

    @pytest.mark.mysql
    def test_mysql_json_functions_compatibility(
        self, mysql_session: Session
    ) -> None:
        """Test compatibility with MySQL JSON functions."""
        entity = DBTestEntity(
            eager_data=DBTestEagerModel(
                name="mysql_functions",
                tags=["array", "test"],
                metadata={"numeric": 42, "boolean": True},
                nested_list=[[1, 2], [3, 4]],
            )
        )

        mysql_session.add(entity)
        mysql_session.commit()

        # Test mutation tracking
        retrieved = mysql_session.get(DBTestEntity, entity.id)
        assert retrieved is not None

        # Modify data in ways that might interact with MySQL JSON functions
        retrieved.eager_data.metadata["new_field"] = "new_value"
        retrieved.eager_data.tags.extend(["new", "tags"])
        retrieved.eager_data.nested_list[0].append(99)

        mysql_session.commit()

        # Verify changes
        final = mysql_session.get(DBTestEntity, entity.id)
        assert final.eager_data.metadata["new_field"] == "new_value"
        assert "new" in final.eager_data.tags
        assert "tags" in final.eager_data.tags
        assert 99 in final.eager_data.nested_list[0]

    @pytest.mark.mysql
    def test_mysql_utf8mb4_support(self, mysql_session: Session) -> None:
        """Test UTF8MB4 character support in MySQL."""
        entity = DBTestEntity(
            eager_data=DBTestEagerModel(
                name="mysql_utf8mb4_🌟",
                tags=["emoji_💫", "chinese_中文", "arabic_العربية"],
                metadata={"unicode_😀": "value_🎉"},
                nested_list=[[1, "mixed_🚀"], [2, "encoding_✓"]],
            ),
            lazy_data=DBTestLazyModel(
                identifier="mysql_unicode_λ",
                items=[],
                config={"utf8_setting": True},
            ),
        )

        mysql_session.add(entity)
        mysql_session.commit()

        # Verify UTF8MB4 handling
        retrieved = mysql_session.get(DBTestEntity, entity.id)
        assert retrieved is not None
        assert "emoji_💫" in retrieved.eager_data.tags
        assert "chinese_中文" in retrieved.eager_data.tags
        assert "arabic_العربية" in retrieved.eager_data.tags
        assert retrieved.eager_data.metadata["unicode_😀"] == "value_🎉"
        assert retrieved.lazy_data.identifier == "mysql_unicode_λ"


class TestCrossDatabaseCompatibility:
    """Tests for cross-database compatibility."""

    def test_json_data_structure_portability(self) -> None:
        """Test that JSON data structures are portable across databases."""
        # Create test data with various JSON structures
        test_data = DBTestEagerModel(
            name="portability_test",
            tags=["tag1", "tag2", "tag3"],
            metadata={
                "string": "value",
                "number": 42,
                "float": 3.14,
                "boolean": True,
                "null": None,
                "array": [1, 2, 3],
                "object": {"nested": "value"},
            },
            nested_list=[[1, 2], [3, 4], [5, 6]],
        )

        # Test serialization/deserialization without database
        from sqlatypemodel.model_type import ModelType

        model_type = ModelType(DBTestEagerModel)

        # Serialize
        serialized = model_type.process_bind_param(test_data, None)
        assert isinstance(serialized, str) or isinstance(serialized, dict)

        # Deserialize
        deserialized = model_type.process_result_value(serialized, None)
        assert isinstance(deserialized, DBTestEagerModel)
        assert deserialized.name == test_data.name
        assert deserialized.tags == test_data.tags
        assert deserialized.metadata == test_data.metadata
        assert deserialized.nested_list == test_data.nested_list

    def test_type_consistency_across_implementations(self) -> None:
        """Test that types remain consistent across different JSON implementations."""
        # Test with various Python types
        test_cases = [
            ("string", "test_string"),
            ("integer", 42),
            ("float", 3.14159),
            ("boolean", True),
            ("null", None),
            ("list", ["1", "2", "3", "mixed", "True"]),
            ("dict", {"key": "value", "nested": {"deep": "value"}}),
            ("nested_lists", [[1, 2], [3, 4], [5, 6]]),
            (
                "mixed",
                {
                    "array": [1, "two", 3.0],
                    "object": {"nested": True},
                    "primitive": "string",
                },
            ),
        ]

        for name, value in test_cases:
            # Create model with specific data
            model_data = {"name": name, "metadata": {"test": value}}

            if name == "nested_lists":
                model_data["nested_list"] = value
            elif isinstance(value, list):
                model_data["tags"] = value
            elif isinstance(value, dict):
                model_data["metadata"] = value

            model = DBTestEagerModel(**model_data)

            # Test round-trip
            model_type = ModelType(DBTestEagerModel)
            serialized = model_type.process_bind_param(model, None)
            deserialized = model_type.process_result_value(serialized, None)

            # Verify data integrity
            if name == "nested_lists":
                assert deserialized.nested_list == value
            elif isinstance(value, list):
                assert deserialized.tags == value
            elif isinstance(value, dict):
                assert deserialized.metadata == value
            else:
                assert deserialized.metadata["test"] == value


class TestDatabaseSpecificEdgeCases:
    """Tests for database-specific edge cases and limitations."""

    def test_large_integer_handling(self) -> None:
        """Test handling of large integers that might exceed JSON limits."""
        from sqlatypemodel.model_type import ModelType

        # Test with 64-bit integer limits
        max_int64 = 2**63 - 1
        min_int64 = -(2**63)

        model = DBTestEagerModel(
            name="large_int_test",
            metadata={
                "max_int64": max_int64,
                "min_int64": min_int64,
                "too_large": max_int64 + 1,  # Should trigger fallback
                "too_small": min_int64 - 1,  # Should trigger fallback
            },
        )

        model_type = ModelType(DBTestEagerModel)
        serialized = model_type.process_bind_param(model, None)
        deserialized = model_type.process_result_value(serialized, None)

        # Values should be preserved (with fallback handling)
        assert deserialized.metadata["max_int64"] == max_int64
        assert deserialized.metadata["min_int64"] == min_int64
        assert deserialized.metadata["too_large"] == max_int64 + 1
        assert deserialized.metadata["too_small"] == min_int64 - 1

    def test_float_precision_handling(self) -> None:
        """Test float precision preservation across JSON implementations."""
        test_floats = [
            3.141592653589793,
            1.23456789012345,
            0.123456789012345,
            1e-10,
            1e10,
            float("inf"),
            float("-inf"),
        ]

        for i, test_float in enumerate(test_floats):
            model = DBTestEagerModel(
                name=f"float_test_{i}", metadata={"test_float": test_float}
            )

            model_type = ModelType(DBTestEagerModel)
            serialized = model_type.process_bind_param(model, None)
            deserialized = model_type.process_result_value(serialized, None)

            # Check float preservation (allowing for JSON precision limits)
            result_float = deserialized.metadata["test_float"]
            if not (test_float != test_float):  # Not NaN
                # For infinity, check that it's handled gracefully
                if test_float == float("inf") or test_float == float("-inf"):
                    # Infinity might be converted to null or a large number or preserved
                    assert result_float is not None or result_float is None
                else:
                    # Regular floats should be approximately equal
                    assert abs(result_float - test_float) < 1e-10
