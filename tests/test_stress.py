"""Property-based fuzzing tests using Hypothesis."""

from hypothesis import settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, Bundle
from pydantic import BaseModel
from sqlalchemy.orm import Session, DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool
from sqlatypemodel import MutableMixin, ModelType
from sqlatypemodel.sqlalchemy_utils import create_engine

class StressBase(DeclarativeBase):
    pass

class NestedData(MutableMixin, BaseModel):
    """Nested mutable data structure."""
    val: int
    child: list[int] = []

class StressEntity(StressBase):
    """SQLAlchemy entity for fuzzing."""
    __tablename__ = "stress_entities"
    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[NestedData] = mapped_column(ModelType(NestedData))

class DBStateMachine(RuleBasedStateMachine):
    """State machine for random sequence testing."""

    def __init__(self):
        super().__init__()
        self.engine = create_engine(
            "sqlite:///:memory:", 
            poolclass=StaticPool,
            connect_args={"check_same_thread": False}
        )
        StressBase.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def teardown(self):
        self.session.close()
        self.engine.dispose()
        super().teardown()

    entities = Bundle("entities")

    # FIX: orjson поддерживает только 64-битные знаковые целые числа.
    # Ограничиваем генератор Hypothesis, чтобы не ловить TypeError.
    MIN_I64 = -(2**63)
    MAX_I64 = (2**63) - 1

    @rule(target=entities, val=st.integers(min_value=MIN_I64, max_value=MAX_I64))
    def create_entity(self, val):
        obj = StressEntity(data=NestedData(val=val))
        self.session.add(obj)
        self.session.commit()
        return obj

    @rule(entity=entities, new_val=st.integers(min_value=MIN_I64, max_value=MAX_I64))
    def modify_data(self, entity, new_val):
        entity.data.val = new_val
        self.session.commit()
        
        self.session.expire(entity)
        assert entity.data.val == new_val

    @rule(entity=entities, item=st.integers(min_value=MIN_I64, max_value=MAX_I64))
    def modify_nested_list(self, entity, item):
        entity.data.child.append(item)
        self.session.commit()
        
        self.session.expire(entity)
        assert entity.data.child[-1] == item

TestDBStateMachine = DBStateMachine.TestCase