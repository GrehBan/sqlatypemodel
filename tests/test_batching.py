"""Tests for batch changes context manager."""
from unittest.mock import patch

from pydantic import BaseModel
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from sqlatypemodel import ModelType, MutableMixin


class BatchBase(DeclarativeBase):
    pass


class BatchModel(MutableMixin, BaseModel):
    model_config = {"extra": "allow"} 
    data: list[int] = []


class BatchEntity(BatchBase):
    """SQLAlchemy wrapper for the Pydantic model."""
    __tablename__ = "batch_entities"
    id: Mapped[int] = mapped_column(primary_key=True)
    model: Mapped[BatchModel] = mapped_column(ModelType(BatchModel))


class TestBatching:
    """Test suite for batch_changes context manager."""

    def setup_db(self, session: Session) -> BatchEntity:
        """Create the table and a test row."""
        assert session.bind is not None
        BatchBase.metadata.create_all(session.bind)
        
        obj = BatchEntity(model=BatchModel())
        session.add(obj)
        session.commit()
        return obj

    def test_single_notification_for_multiple_changes(self, session: Session) -> None:
        entity = self.setup_db(session)
        trackable_obj = entity.model
        
        with patch("sqlatypemodel.mixin.events.flag_modified") as mock_flag:
            with trackable_obj.batch_changes():
                trackable_obj.data.append(1)
                trackable_obj.data.append(2)
                
                assert mock_flag.call_count == 0
            
            assert mock_flag.call_count == 1

    def test_nested_batching(self, session: Session) -> None:
        entity = self.setup_db(session)
        trackable_obj = entity.model
        
        with patch("sqlatypemodel.mixin.events.flag_modified") as mock_flag:
            with trackable_obj.batch_changes():
                with trackable_obj.batch_changes():
                    trackable_obj.data.append(1)
                
                assert mock_flag.call_count == 0
            
            assert mock_flag.call_count == 1

    def test_loop_performance_simulation(self, session: Session) -> None:
        entity = self.setup_db(session)
        trackable_obj = entity.model
        
        with patch("sqlatypemodel.mixin.events.flag_modified") as mock_flag:
            with trackable_obj.batch_changes():
                for i in range(100):
                    trackable_obj.data.append(i)
            
            assert mock_flag.call_count == 1

    def test_exception_safety(self, session: Session) -> None:
        entity = self.setup_db(session)
        trackable_obj = entity.model
        
        try:
            with trackable_obj.batch_changes():
                trackable_obj.data.append(1)
                raise ValueError("oops")
        except ValueError:
            pass
        
        assert trackable_obj._change_suppress_level == 0