"""Example 02: High-Performance Lazy Loading.

This example compares standard `MutableMixin` vs `LazyMutableMixin`.
Lazy loading defers the cost of wrapping mutable structures until they are
accessed, which can be significantly faster for read-heavy workloads where
only a subset of fields are accessed.
"""

from __future__ import annotations

import time

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from sqlatypemodel import LazyMutableMixin, ModelType, MutableMixin
from sqlatypemodel.util.sqlalchemy import create_engine


class Base(DeclarativeBase):
    """Base SQLAlchemy model."""

    pass


# Standard Model
class EagerSettings(MutableMixin, BaseModel):
    """Eagerly loaded settings model."""

    data: str = "some large amount of data"


# Lazy Model
class LazySettings(LazyMutableMixin, BaseModel):
    """Lazily loaded settings model."""

    data: str = "some large amount of data"


class EagerUser(Base):
    """User entity with eager settings."""

    __tablename__ = "eager_users"
    id: Mapped[int] = mapped_column(primary_key=True)
    settings: Mapped[EagerSettings] = mapped_column(ModelType(EagerSettings))


class LazyUser(Base):
    """User entity with lazy settings."""

    __tablename__ = "lazy_users"
    id: Mapped[int] = mapped_column(primary_key=True)
    settings: Mapped[LazySettings] = mapped_column(ModelType(LazySettings))


def run_example() -> None:
    """Run the lazy loading benchmark example."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    count = 1000
    print(f"Generating {count} objects for comparison...")

    with Session(engine) as session:
        # Batch insert
        session.add_all(
            [EagerUser(settings=EagerSettings()) for _ in range(count)]
        )
        session.add_all(
            [LazyUser(settings=LazySettings()) for _ in range(count)]
        )
        session.commit()

        # 1. Test Eager Loading (Every object is initialized immediately)
        start = time.perf_counter()
        session.execute(select(EagerUser)).scalars().all()
        eager_time = (time.perf_counter() - start) * 1000
        print(f"Eager load time: {eager_time:.2f}ms")

        # 2. Test Lazy Loading (Wrappers are created only on access)
        start = time.perf_counter()
        users_lazy = session.execute(select(LazyUser)).scalars().all()
        lazy_time = (time.perf_counter() - start) * 1000
        print(f"Lazy load time:  {lazy_time:.2f}ms")

        ratio = eager_time / lazy_time
        print(f"\nResult: Lazy loading is {ratio:.1f}x faster in this test.")

        # Accessing one lazy attribute triggers JIT wrapping
        print("\nAccessing one lazy attribute...")
        users_lazy[0].settings.data = "modified"
        session.commit()
        print("Lazy mutation saved successfully.")


if __name__ == "__main__":
    run_example()
