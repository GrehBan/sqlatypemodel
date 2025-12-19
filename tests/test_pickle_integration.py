"""Integration tests for Pickle in realistic scenarios."""

import pickle
import pytest
from typing import Any
from pydantic import BaseModel
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlatypemodel import MutableMixin, ModelType

class TaskConfig(MutableMixin, BaseModel):
    """Mutable configuration model."""
    retries: int = 3

# Промежуточный класс для DeclarativeBase (требование SQLAlchemy 2.0)
class IntegrationBase(DeclarativeBase):
    pass

class Task(IntegrationBase):
    """SQLAlchemy entity."""
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    config: Mapped[TaskConfig] = mapped_column(ModelType(TaskConfig))

@pytest.mark.integration
class TestPickleIntegration:
    """Tests simulating external systems like Celery."""

    def test_workflow_lifecycle(self, session) -> None:
        """Verify object consistency across DB -> Pickle -> DB cycle."""
        IntegrationBase.metadata.create_all(session.get_bind())
        
        task = Task(config=TaskConfig(retries=5))
        session.add(task)
        session.commit()
        
        # FIX: Принудительная загрузка атрибутов.
        # session.commit() делает все объекты "expired".
        # Если мы сделаем expunge() на expired объекте, pickle сохранит это состояние.
        # При unpickle объект попытается обновиться, но сессии уже нет -> DetachedInstanceError.
        _ = task.config
        
        session.expunge(task)
        
        # 1. Сериализация
        payload = pickle.dumps(task)

        # 2. Десериализация
        worker_task = pickle.loads(payload)
        
        # 3. Изменение
        worker_task.config.retries = 1
        
        # 4. Возврат результата
        result_payload = pickle.dumps(worker_task)

        # 5. Сохранение
        final_task = pickle.loads(result_payload)
        merged_task = session.merge(final_task)
        session.commit()

        saved = session.get(Task, task.id)
        assert saved.config.retries == 1