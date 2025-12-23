"""Property-based fuzzing tests using Hypothesis."""

from typing import Any

from hypothesis import strategies as st
from hypothesis.stateful import Bundle, RuleBasedStateMachine, rule
from pydantic import BaseModel, Field
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import StaticPool

from sqlatypemodel import ModelType, MutableMixin
from sqlatypemodel.util.sqlalchemy import create_engine


class StressBase(DeclarativeBase):
    pass


class NestedData(MutableMixin, BaseModel):
    """Nested mutable data structure."""
    val: int
    meta: dict[str, Any] = Field(default_factory=dict)
    child: list[int] = Field(default_factory=list)


class StressEntity(StressBase):
    """SQLAlchemy entity for fuzzing."""
    __tablename__ = "stress_entities"
    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[NestedData] = mapped_column(ModelType(NestedData))


class DBStateMachine(RuleBasedStateMachine):
    """State machine for random sequence testing."""

    def __init__(self) -> None:
        super().__init__()
        self.engine = create_engine(
            "sqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False}
        )
        StressBase.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def teardown(self) -> None:
        self.session.close()
        self.engine.dispose()
        super().teardown() # type: ignore[no-untyped-call]

    entities = Bundle("entities")

    MIN_I64 = -(2**63)
    MAX_I64 = (2**63) - 1

    @rule(target=entities, val=st.integers(min_value=MIN_I64, max_value=MAX_I64))
    def create_entity(self, val: int) -> StressEntity:
        obj = StressEntity(data=NestedData(val=val))
        self.session.add(obj)
        self.session.commit()
        return obj

    @rule(entity=entities, new_val=st.integers(min_value=MIN_I64, max_value=MAX_I64))
    def modify_data_val(self, entity: StressEntity, new_val: int) -> None:
        """Modify top-level field."""
        entity.data.val = new_val
        self.session.commit()
        self.session.expire(entity)
        assert entity.data.val == new_val

    @rule(entity=entities, item=st.integers(min_value=MIN_I64, max_value=MAX_I64))
    def modify_nested_list(self, entity: StressEntity, item: int) -> None:
        """Modify nested list (append)."""
        entity.data.child.append(item)
        self.session.commit()
        self.session.expire(entity)
        assert entity.data.child[-1] == item

    @rule(entity=entities, key=st.text(min_size=1), value=st.integers(min_value=MIN_I64, max_value=MAX_I64))
    def modify_nested_dict(self, entity: StressEntity, key: str, value: int) -> None:
        """Modify nested dictionary."""
        entity.data.meta[key] = value
        self.session.commit()
        self.session.expire(entity)
        assert entity.data.meta[key] == value

    @rule(entity=entities)
    def check_consistency(self, entity: StressEntity) -> None:
        """Verify object structure is preserved."""
        _ = entity.data.val
        _ = entity.data.child
        _ = entity.data.meta


TestDBStateMachine = DBStateMachine.TestCase