"""Integration tests for Pickle in realistic scenarios."""

import pickle
from typing import cast

import pytest
from pydantic import BaseModel
from sqlalchemy import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from sqlatypemodel import ModelType, MutableMixin


class IntegrationBase(DeclarativeBase):
    pass


class TaskConfig(MutableMixin, BaseModel):
    retries: int = 3


class Task(IntegrationBase):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    config: Mapped[TaskConfig] = mapped_column(ModelType(TaskConfig))


@pytest.mark.integration
class TestPickleIntegration:
    """Tests simulating external systems like Celery."""

    def test_workflow_lifecycle(self, session: Session, engine: Engine) -> None:
        """Verify object consistency across DB -> Pickle -> DB cycle."""
        IntegrationBase.metadata.create_all(engine)

        task = Task(config=TaskConfig(retries=5))
        session.add(task)
        session.commit()

        _ = task.config

        session.expunge(task)

        payload = pickle.dumps(task)

        worker_task = pickle.loads(payload)

        worker_task.config.retries = 1

        result_payload = pickle.dumps(worker_task)

        final_task = pickle.loads(result_payload)
        
        session.merge(final_task)
        session.commit()

        saved = cast(Task, session.get(Task, task.id))
        assert saved.config.retries == 1