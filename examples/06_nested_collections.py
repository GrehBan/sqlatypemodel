"""
Example 06: Complex Nested Collections

One of the most powerful features of sqlatypemodel is deep mutation tracking
in nested lists and dictionaries.
"""

from pydantic import BaseModel
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from sqlatypemodel import ModelType, MutableMixin
from sqlatypemodel.util.sqlalchemy import create_engine


class MetaInfo(MutableMixin, BaseModel):
    version: int = 1


class Container(MutableMixin, BaseModel):
    # A dictionary of models inside a list!
    items: list[dict[str, MetaInfo]] = []


class Base(DeclarativeBase):
    pass


class ComplexEntity(Base):
    __tablename__ = "complex"
    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[Container] = mapped_column(ModelType(Container))


def run_example():
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
