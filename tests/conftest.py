"""Shared fixtures for pytest."""

import pytest
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, DeclarativeBase
from sqlalchemy.pool import StaticPool

class Base(DeclarativeBase):
    pass

@pytest.fixture
def engine():
    """Create an in-memory SQLite engine with StaticPool.

    StaticPool is required for in-memory SQLite to persist data across
    multiple session commits within the same thread.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    yield engine
    engine.dispose()

@pytest.fixture
def session(engine) -> Generator[Session, None, None]:
    """Create a fresh SQLAlchemy session for each test.

    Automatically creates tables before the test and drops them afterwards.
    """
    Base.metadata.create_all(engine)
    session = Session(engine)
    
    yield session
    
    session.close()
    Base.metadata.drop_all(engine)