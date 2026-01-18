"""Example 03: Python Dataclasses Support.

Demonstrates using Python `dataclasses` with `MutableMixin`.
Using the safe `sqlatypemodel.util.dataclasses.dataclass` wrapper is
recommended to ensure compatibility with SQLAlchemy's mutable system by
disabling recursion-prone defaults like `eq=True`.
"""

from __future__ import annotations

from dataclasses import asdict

from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from sqlatypemodel import ModelType, MutableMixin

# Use our safe wrapper!
from sqlatypemodel.util.dataclasses import dataclass
from sqlatypemodel.util.sqlalchemy import create_engine


# 1. Define Dataclass
@dataclass
class Config(MutableMixin):
    """Configuration dataclass with mutation tracking."""

    host: str
    port: int
    retries: int = 3


class Base(DeclarativeBase):
    """Base SQLAlchemy model."""

    pass


class Server(Base):
    """Server entity with configuration."""

    __tablename__ = "servers"
    id: Mapped[int] = mapped_column(primary_key=True)

    # For dataclasses, we provide a custom loader/dumper to ModelType
    config: Mapped[Config] = mapped_column(
        ModelType(Config, dumper=asdict, loader=lambda d: Config(**d))
    )


def run_example() -> None:
    """Run the dataclasses example."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        server = Server(config=Config(host="localhost", port=8080))
        session.add(server)
        session.commit()

        # Mutation
        server.config.port = 9000
        session.commit()

        print(f"Server host: {server.config.host}:{server.config.port}")


if __name__ == "__main__":
    run_example()
