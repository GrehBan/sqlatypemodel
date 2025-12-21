"""Shared fixtures for pytest."""

from typing import Any, Generator

import pytest
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool

from sqlatypemodel import LazyMutableMixin, MutableMixin


class EagerModel(MutableMixin, BaseModel):
    """Standard eager model for testing."""
    model_config = ConfigDict(validate_assignment=True)
    
    data: list[str] = Field(default_factory=list)
    meta: dict[str, str] = Field(default_factory=dict)


class LazyModel(LazyMutableMixin, BaseModel):
    """Lazy model for testing."""
    model_config = ConfigDict(
        extra="allow",
        arbitrary_types_allowed=True,
        validate_assignment=False
    )
    data: dict[str, Any] = Field(default_factory=dict)
    items: list[int] = Field(default_factory=list)
    meta: dict[str, Any] | None = None


@pytest.fixture(scope="session")
def engine():
    """Create a single in-memory database engine for the test session."""
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture(scope="function")
def session(engine) -> Generator[Session, None, None]:
    """Create a new session for each test function."""
    connection = engine.connect()
    transaction = connection.begin()
    
    session_factory = sessionmaker(bind=connection)
    session = scoped_session(session_factory)
    
    yield session
    
    session.remove()
    transaction.rollback()
    connection.close()