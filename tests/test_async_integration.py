"""Integration tests for SQLAlchemy 2.0 AsyncIO support."""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from sqlatypemodel import LazyMutableMixin, ModelType
from sqlatypemodel.util.sqlalchemy import create_async_engine


class AsyncBase(DeclarativeBase):
    pass


class AsyncSettings(LazyMutableMixin, BaseModel):
    """Pydantic model for async testing."""
    theme: str = "light"
    tags: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class AsyncUser(AsyncBase):
    """SQLAlchemy entity for async tests."""
    __tablename__ = "async_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str]
    settings: Mapped[AsyncSettings] = mapped_column(ModelType(AsyncSettings))


@pytest_asyncio.fixture(scope="function")
async def async_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create an async engine."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(AsyncBase.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_session(async_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a fresh async session."""
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest.mark.asyncio
class TestAsyncIntegration:
    """Tests for AsyncIO compatibility."""

    async def test_async_create_and_read(self, async_session: AsyncSession) -> None:
        """Verify basic INSERT and SELECT operations."""
        new_user = AsyncUser(
            username="async_bob",
            settings=AsyncSettings(theme="dark", tags=["v1"])
        )
        async_session.add(new_user)
        await async_session.commit()
        async_session.expunge_all()

        stmt = select(AsyncUser).where(AsyncUser.username == "async_bob")
        result = await async_session.execute(stmt)
        user = result.scalar_one()

        assert user.settings.theme == "dark"
        assert isinstance(user.settings, AsyncSettings)

    async def test_async_mutation_tracking(self, async_session: AsyncSession) -> None:
        """Verify mutation tracking in async sessions."""
        user = AsyncUser(username="mutant", settings=AsyncSettings(tags=["init"]))
        async_session.add(user)
        await async_session.commit()

        user.settings.tags.append("mutated")
        user.settings.meta["key"] = "val"
        user.settings.theme = "changed"

        assert user in async_session.dirty
        
        await async_session.commit()
        async_session.expunge_all()

        reloaded = await async_session.get(AsyncUser, user.id)
        
        assert reloaded is not None
        assert reloaded.settings.tags == ["init", "mutated"]
        assert reloaded.settings.meta == {"key": "val"}
        assert reloaded.settings.theme == "changed"

    async def test_async_rollback(self, async_session: AsyncSession) -> None:
        """Verify rollback."""
        user = AsyncUser(username="rollback_test", settings=AsyncSettings())
        async_session.add(user)
        await async_session.commit()

        user.settings.theme = "broken"
        
        await async_session.rollback()
        await async_session.refresh(user)

        assert user.settings.theme == "light"

    async def test_lazy_loading_in_async(self, async_session: AsyncSession) -> None:
        """Verify LazyMutableMixin."""
        user = AsyncUser(username="lazy_async", settings=AsyncSettings(tags=["1", "2"]))
        async_session.add(user)
        await async_session.commit()
        async_session.expunge_all()

        stmt = select(AsyncUser).where(AsyncUser.username == "lazy_async")
        result = await async_session.execute(stmt)
        loaded_user = result.scalar_one()

        internal_dict = loaded_user.settings.__dict__["tags"]
        assert type(internal_dict) is list
        
        _ = loaded_user.settings.tags
        assert loaded_user.settings.tags == ["1", "2"]