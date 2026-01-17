"""
Example 03: Python Dataclasses Support

Using the safe `sqlatypemodel.util.dataclasses.dataclass` wrapper ensures
compatibility with SQLAlchemy's mutable system by disabling recursion-prone
defaults like eq=True.
"""

from dataclasses import asdict

from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from sqlatypemodel import ModelType, MutableMixin

# Use our safe wrapper!
from sqlatypemodel.util.dataclasses import dataclass
from sqlatypemodel.util.sqlalchemy import create_engine


# 1. Define Dataclass
@dataclass
class Config(MutableMixin):
    host: str
    port: int
    retries: int = 3


class Base(DeclarativeBase):
    pass


class Server(Base):
    __tablename__ = "servers"
    id: Mapped[int] = mapped_column(primary_key=True)

    # For dataclasses, we provide a custom loader/dumper to ModelType
    config: Mapped[Config] = mapped_column(
        ModelType(Config, dumper=asdict, loader=lambda d: Config(**d))
    )


def run_example():
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
