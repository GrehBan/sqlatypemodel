from collections.abc import Generator
from typing import Any

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import Engine, StaticPool
from sqlalchemy.orm import Session

from sqlatypemodel import LazyMutableMixin, MutableMixin
from sqlatypemodel.util.sqlalchemy import create_engine


class EagerModel(MutableMixin, BaseModel):
    """
    Model for Eager loading tests.
    """
    model_config = {"extra": "allow"}
    
    data: list[Any] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
    
class LazyModel(LazyMutableMixin, BaseModel):
    """
    Model for Lazy loading tests.
    """
    model_config = {"extra": "allow"}

    data: dict[str, Any] = Field(default_factory=dict)
    items: list[int] = Field(default_factory=list)


@pytest.fixture(scope="session")
def engine() -> Generator[Engine, None, None]:
    """Shared in-memory engine."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool # Важно для in-memory сохранения данных между сессиями
    )
    yield eng
    eng.dispose()

@pytest.fixture(scope="function")
def session(engine: Engine) -> Generator[Session, None, None]:
    """Fresh session per test."""
    conn = engine.connect()
    trans = conn.begin()
    sess = Session(bind=conn)
    
    yield sess
    
    sess.close()
    trans.rollback()
    conn.close()