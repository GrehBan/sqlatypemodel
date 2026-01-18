"""Example 05: Asynchronous SQLAlchemy Usage.

Demonstrates integration with SQLAlchemy's `AsyncSession` and `aiosqlite`
using the `create_async_engine` helper. Mutation tracking works seamlessly
in async contexts.
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool

from sqlatypemodel import ModelType, MutableMixin
from sqlatypemodel.util.sqlalchemy import create_async_engine


class TaskData(MutableMixin, BaseModel):
    """Task data model with mutation tracking."""

    priority: int = 0
    assigned_to: str | None = None


class Base(DeclarativeBase):
    """Base SQLAlchemy model."""

    pass


class Task(Base):
    """Task entity."""

    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[TaskData] = mapped_column(ModelType(TaskData))


async def run_async_example() -> None:
    """Run the async SQLAlchemy example."""
    # Use create_async_engine helper with StaticPool
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with AsyncSession(engine, expire_on_commit=False) as session:
            # Create
            task = Task(data=TaskData(priority=1))
            session.add(task)
            await session.commit()

            # Update
            task.data.priority = 5
            task.data.assigned_to = "max"

            # Tracking works exactly like sync!
            await session.commit()

            print(f"Async Task updated: {task.data}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_async_example())
