"""Example 06: Complex Nested Collections.

Demonstrates deep mutation tracking in nested lists and dictionaries.
Changes in deeply nested structures (e.g., `list[dict[str, Model]]`)
bubble up to SQLAlchemy and mark the column as dirty.
"""

from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from sqlatypemodel import ModelType, MutableMixin
from sqlatypemodel.util.sqlalchemy import create_engine


class MetaInfo(MutableMixin, BaseModel):
    """Nested metadata model."""

    version: int = 1


class Container(MutableMixin, BaseModel):
    """Container model with complex nesting."""

    # A dictionary of models inside a list!
    items: list[dict[str, MetaInfo]] = []


class Base(DeclarativeBase):
    """Base SQLAlchemy model."""

    pass


class ComplexEntity(Base):
    """Entity with complex nested data."""

    __tablename__ = "complex"
    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[Container] = mapped_column(ModelType(Container))


def run_example() -> None:
    """Run the nested collections example."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        # 1. Initialize with complex nesting
        entity = ComplexEntity(data=Container(items=[{"sub": MetaInfo()}]))
        session.add(entity)
        session.commit()

        # 2. Mutate THE DEEPEST level
        # This will bubble up to SQLAlchemy and mark 'data' as dirty!
        entity.data.items[0]["sub"].version += 1

        session.commit()

        # 3. Verify
        session.refresh(entity)
        sub_version = entity.data.items[0]["sub"].version
        print(f"Deep nested version updated: {sub_version}")


if __name__ == "__main__":
    run_example()
