"""
Example 04: Attrs Integration

This example shows how to use `attrs` classes with MutableMixin.
We use the safe `sqlatypemodel.util.attrs.define` wrapper.
"""

from attrs import asdict
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from sqlatypemodel import ModelType, MutableMixin

# Use our safe wrapper!
from sqlatypemodel.util.attrs import define
from sqlatypemodel.util.sqlalchemy import create_engine


@define
class AppState(MutableMixin):
    status: str
    counts: dict[str, int]


class Base(DeclarativeBase):
    pass


class Application(Base):
    __tablename__ = "apps"
    id: Mapped[int] = mapped_column(primary_key=True)
    state: Mapped[AppState] = mapped_column(
        ModelType(AppState, dumper=asdict, loader=lambda d: AppState(**d))
    )


def run_example():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        app = Application(
            state=AppState(status="active", counts={"users": 10})
        )
        session.add(app)
        session.commit()

        # Mutating dictionary inside Attrs class
        app.state.counts["users"] += 5
        session.commit()

        print(f"App status: {app.state.status}, count: {app.state.counts}")


if __name__ == "__main__":
    run_example()
