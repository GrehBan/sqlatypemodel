"""Unit tests for Batch Changes (Notification Suppression)."""

import pytest
from unittest.mock import patch
from pydantic import BaseModel, Field
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase

from sqlatypemodel import MutableMixin, ModelType
from sqlatypemodel.mixin import events 


class BatchData(MutableMixin, BaseModel):
    """Test model for batch operations."""
    counter: int = 0
    tags: list[str] = Field(default_factory=list)
    meta: dict[str, int] = Field(default_factory=dict)

class BatchBase(DeclarativeBase):
    pass

class BatchEntity(BatchBase):
    """SQLAlchemy entity."""
    __tablename__ = "batch_entities"
    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[BatchData] = mapped_column(ModelType(BatchData))


class TestBatching:
    """Tests for batch_changes() context manager."""

    @pytest.fixture(autouse=True)
    def setup_db(self, session):
        """Prepare DB schema for each test."""
        BatchBase.metadata.create_all(session.get_bind())

    def _count_root_calls(self, mock_notify, root_obj):
        """Helper: count how many times safe_changed was called specifically for the root object."""
        count = 0
        for call in mock_notify.call_args_list:
            if call.args[0] is root_obj:
                count += 1
        return count

    def test_single_notification_for_multiple_changes(self, session):
        """Verify that multiple mutations trigger only ONE notification from Root."""
        entity = BatchEntity(data=BatchData())
        session.add(entity)
        session.commit()

        real_safe_changed = events.safe_changed

        with patch("sqlatypemodel.mixin.events.safe_changed", side_effect=real_safe_changed) as mock_notify:
            
            with entity.data.batch_changes():
                entity.data.counter += 1
                
                entity.data.tags.append("a")
                
                entity.data.meta["x"] = 1
                
                assert self._count_root_calls(mock_notify, entity.data) == 0

            assert self._count_root_calls(mock_notify, entity.data) == 1

        session.commit()
        session.expire_all()
        reloaded = session.get(BatchEntity, entity.id)
        
        assert reloaded.data.counter == 1
        assert reloaded.data.tags == ["a"]
        assert reloaded.data.meta["x"] == 1

    def test_nested_batching(self, session):
        entity = BatchEntity(data=BatchData())
        session.add(entity)
        session.commit()
        
        real_safe_changed = events.safe_changed

        with patch("sqlatypemodel.mixin.events.safe_changed", side_effect=real_safe_changed) as mock_notify:
            
            with entity.data.batch_changes():
                entity.data.tags.append("level1")
                
                with entity.data.batch_changes():
                    entity.data.tags.append("level2")
                
                assert self._count_root_calls(mock_notify, entity.data) == 0
                
                entity.data.tags.append("level1_again")
            
            assert self._count_root_calls(mock_notify, entity.data) == 1

        session.commit()
        reloaded = session.get(BatchEntity, entity.id)
        assert reloaded.data.tags == ["level1", "level2", "level1_again"]

    def test_loop_performance_simulation(self, session):
        """Simulate a loop with 1000 items."""
        entity = BatchEntity(data=BatchData())
        session.add(entity)
        session.commit()

        real_safe_changed = events.safe_changed

        with patch("sqlatypemodel.mixin.events.safe_changed", side_effect=real_safe_changed) as mock_notify:
            with entity.data.batch_changes():
                for i in range(1000):
                    entity.data.tags.append(str(i))
            
            assert self._count_root_calls(mock_notify, entity.data) == 1

        session.commit()
        reloaded = session.get(BatchEntity, entity.id)
        assert len(reloaded.data.tags) == 1000
    
    def test_exception_safety(self, session):
        """Verify exception handling resets flags."""
        entity = BatchEntity(data=BatchData())
        session.add(entity)
        session.commit()

        try:
            with entity.data.batch_changes():
                entity.data.counter = 999
                raise ValueError("Boom!")
        except ValueError:
            pass

        assert getattr(entity.data, "_change_suppress_level", 0) == 0

        # Verify system is still working after crash
        real_safe_changed = events.safe_changed
        with patch("sqlatypemodel.mixin.events.safe_changed", side_effect=real_safe_changed) as mock_notify:
            entity.data.tags.append("recovery")
            assert self._count_root_calls(mock_notify, entity.data) == 1