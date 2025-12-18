import sys
import os
import shutil
import tempfile
import time
import threading
import resource
import dataclasses
from datetime import datetime
from contextlib import contextmanager
from typing import List, Dict, Set, Any, Optional, Iterator, cast

import pytest
from hypothesis import strategies as st, settings, HealthCheck, given, note
from hypothesis.stateful import RuleBasedStateMachine, rule, Bundle
from sqlalchemy import create_engine, select, event
from sqlalchemy.orm import Session, sessionmaker, Mapped, mapped_column, DeclarativeBase
from sqlalchemy.pool import NullPool, StaticPool
from pydantic import BaseModel, Field

# Imports from your library
from sqlatypemodel import ModelType, MutableMixin

# =============================================================================
# 0. OPTIONAL DEPENDENCIES (ATTRS)
# =============================================================================
try:
    import attrs
    HAS_ATTRS = True
except ImportError:
    HAS_ATTRS = False

# =============================================================================
# 1. FORENSIC LOGGER
# =============================================================================

class ForensicLogger:
    def __init__(self) -> None:
        self.filename = f"trace_hypothesis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.file = open(self.filename, "w", encoding="utf-8", buffering=1) 
        self.start_global = time.perf_counter_ns()
        self.lock = threading.Lock()
        self._write_header()
        print(f"🕵️  FORENSIC LOGGING STARTED: {self.filename}")

    def _write_header(self) -> None:
        self.log_raw("="*100)
        self.log_raw(f"  SQLATYPEMODEL HYPOTHESIS TRACE | PID: {os.getpid()}")
        self.log_raw(f"  System: {sys.platform} | Python: {sys.version.split()[0]}")
        self.log_raw(f"  Attrs installed: {HAS_ATTRS}")
        self.log_raw("="*100 + "\n")

    def log(self, category: str, msg: str) -> None:
        ts = (time.perf_counter_ns() - self.start_global) / 1_000_000
        try:
            mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        except Exception:
            mem = 0.0
        
        thread_name = threading.current_thread().name
        formatted = f"[{ts:10.3f}ms] [MEM:{mem:6.2f}MB] [{thread_name:^10}] [{category:^10}] {msg}"
        with self.lock:
            self.file.write(formatted + "\n")

    def log_raw(self, msg: str) -> None:
        with self.lock:
            self.file.write(msg + "\n")

    def close(self) -> None:
        self.log("SYSTEM", "Trace finished. Closing file.")
        self.file.close()

TRACE = ForensicLogger()

@pytest.fixture(scope="session", autouse=True)
def cleanup_logger() -> Iterator[None]:
    yield
    TRACE.close()

# =============================================================================
# 2. PROFILING DECORATORS
# =============================================================================

@contextmanager
def step(name: str) -> Iterator[None]:
    TRACE.log("STEP_IN", f">>> {name}")
    t0 = time.perf_counter_ns()
    try:
        yield
    except Exception as e:
        dt = (time.perf_counter_ns() - t0) / 1000
        TRACE.log("STEP_ERR", f"!!! {name} FAILED after {dt:.3f}µs: {e}")
        raise
    else:
        dt = (time.perf_counter_ns() - t0) / 1000
        TRACE.log("STEP_OUT", f"<<< {name} DONE in {dt:.3f}µs")

def attach_sql_sniffer(engine: Any) -> None:
    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(
        conn: Any, cursor: Any, statement: Any, parameters: Any, context: Any, executemany: Any
    ) -> None:
        conn.info.setdefault('query_start_time', []).append(time.perf_counter_ns())
        params_str = str(parameters)
        if len(params_str) > 200:
            params_str = params_str[:200] + "... (truncated)"
        TRACE.log("SQL_REQ", f"Exec: {statement} | Params: {params_str}")

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(
        conn: Any, cursor: Any, statement: Any, parameters: Any, context: Any, executemany: Any
    ) -> None:
        try:
            start_list = conn.info.get('query_start_time', [])
            if start_list:
                start = start_list.pop(-1)
                duration = (time.perf_counter_ns() - start) / 1000
                TRACE.log("SQL_RES", f"Done in {duration:.3f}µs")
        except Exception:
            pass

# =============================================================================
# 3. DATA MODELS (PYDANTIC, DATACLASS, CUSTOM, ATTRS)
# =============================================================================

class ListWrapper(MutableMixin, BaseModel):
    items: List[int] = Field(default_factory=list)

class Node(MutableMixin, BaseModel):
    name: str
    value: int = 0
    children: List["Node"] = Field(default_factory=list)
    tags: Set[str] = Field(default_factory=set)
    meta: Dict[str, str] = Field(default_factory=dict)
Node.model_rebuild()

# --- 2. DATACLASS ---
@dataclasses.dataclass
class CompatibleDataclass(MutableMixin):
    """Стандартный датакласс, реализующий протокол Pydantic для sqlatypemodel"""
    pk: int
    label: str
    active: bool = True

    def model_dump(self, mode: str = "python") -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def model_validate(cls, obj: Any) -> "CompatibleDataclass":
        if isinstance(obj, cls): return obj
        return cls(**obj)

# --- 3. CUSTOM VANILLA CLASS ---
class VanillaClass(MutableMixin):
    """Обычный класс Python"""
    def __init__(self, raw_data: str, counter: int) -> None:
        self.raw_data = raw_data
        self.counter = counter
    
    def __eq__(self, other: Any) -> bool:
        return isinstance(other, VanillaClass) and self.__dict__ == other.__dict__

    def model_dump(self, mode: str = "python") -> dict[str, Any]:
        return {"raw_data": self.raw_data, "counter": self.counter}

    @classmethod
    def model_validate(cls, obj: Any) -> "VanillaClass":
        if isinstance(obj, cls): return obj
        return cls(raw_data=obj["raw_data"], counter=obj["counter"])
    
    def __repr__(self) -> str:
        return f"VanillaClass(raw_data={self.raw_data}, counter={self.counter})"

# --- 4. ATTRS (Conditional) ---
if HAS_ATTRS:
    @attrs.define
    class CompatibleAttrs(MutableMixin):
        title: str
        score: float
        
        def model_dump(self, mode: str = "python") -> dict[str, Any]:
            return attrs.asdict(self)

        @classmethod
        def model_validate(cls, obj: Any) -> "CompatibleAttrs":
            if isinstance(obj, cls): return obj
            return cls(**obj)
else:
    CompatibleAttrs = None # type: ignore


# --- SQLALCHEMY MODEL ---
class Base(DeclarativeBase):
    pass

class StressEntity(Base):
    __tablename__ = "stress_entities"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    
    # Pydantic Fields
    raw_list: Mapped[ListWrapper] = mapped_column(ModelType(ListWrapper), default=ListWrapper)
    tree_data: Mapped[Node] = mapped_column(ModelType(Node))
    
    # New Types
    dc_data: Mapped[Optional[CompatibleDataclass]] = mapped_column(ModelType(CompatibleDataclass), nullable=True)
    vanilla_data: Mapped[Optional[VanillaClass]] = mapped_column(ModelType(VanillaClass), nullable=True)
    
    if HAS_ATTRS:
        attrs_data: Mapped[Optional[CompatibleAttrs]] = mapped_column(ModelType(CompatibleAttrs), nullable=True)

# =============================================================================
# 4. STRATEGIES
# =============================================================================

MIN_INT64 = -2**63
MAX_INT64 = 2**63 - 1

def node_strategy(max_leaves: int = 25) -> st.SearchStrategy[Node]:
    return st.recursive(
        st.builds(Node, name=st.text(min_size=1), value=st.integers(MIN_INT64, MAX_INT64), 
                  children=st.lists(st.nothing(), max_size=0), tags=st.sets(st.text()), meta=st.dictionaries(st.text(), st.text())),
        lambda children: st.builds(Node, name=st.text(min_size=1), value=st.integers(MIN_INT64, MAX_INT64), 
                                   children=st.lists(children, max_size=2), tags=st.sets(st.text()), meta=st.dictionaries(st.text(), st.text())),
        max_leaves=max_leaves
    )

dataclass_strategy = st.builds(CompatibleDataclass, pk=st.integers(MIN_INT64, MAX_INT64), label=st.text(), active=st.booleans())
vanilla_strategy = st.builds(VanillaClass, raw_data=st.text(), counter=st.integers(MIN_INT64, MAX_INT64))

# Аннотация Any нужна, чтобы mypy не ругался на несовместимые типы в ветках if/else
attrs_strategy: st.SearchStrategy[Any] 

if HAS_ATTRS:
    attrs_strategy = st.builds(CompatibleAttrs, title=st.text(), score=st.floats(allow_nan=False, allow_infinity=False))
else:
    attrs_strategy = st.none()

# =============================================================================
# 5. STATE MACHINE
# =============================================================================

class DBStateMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        
        TRACE.log("STATE", f"Initializing DBStateMachine: {self.db_path}")
        self.engine = create_engine(f"sqlite:///{self.db_path}", poolclass=NullPool)
        attach_sql_sniffer(self.engine)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

    def teardown(self) -> None:
        TRACE.log("STATE", "Teardown DBStateMachine")
        self.session.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        shutil.rmtree(self.temp_dir)

    entities = Bundle("entities")

    @rule(target=entities, 
          name=st.text(min_size=1),
          tree=node_strategy(max_leaves=3),
          dc=st.one_of(st.none(), dataclass_strategy),
          vanilla=st.one_of(st.none(), vanilla_strategy),
          attrs_obj=st.one_of(st.none(), attrs_strategy) if HAS_ATTRS else st.none())
    def create_entity(self, name: str, tree: Node, dc: Optional[CompatibleDataclass], 
                      vanilla: Optional[VanillaClass], attrs_obj: Any) -> StressEntity:
        """Создание сущности со смесью Pydantic, Dataclass, Custom и Attrs"""
        with step(f"Rule: Create Mixed Entity '{name[:5]}...'"):
            kw: Dict[str, Any] = {
                "name": name, 
                "tree_data": tree, 
                "dc_data": dc, 
                "vanilla_data": vanilla
            }
            if HAS_ATTRS:
                kw["attrs_data"] = attrs_obj

            entity = StressEntity(**kw)
            self.session.add(entity)
            self.session.commit()
            return entity

    @rule(entity=entities, inc=st.integers(1, 10))
    def mutate_dataclass(self, entity: StressEntity, inc: int) -> None:
        """Проверка отслеживания изменений в Dataclass"""
        if entity.dc_data is None:
            return 
            
        with step(f"Rule: Mutate Dataclass ID={entity.id}"):
            self.session.add(entity)
            old_pk = entity.dc_data.pk
            
            TRACE.log("MUTATE", f"Dataclass.pk {old_pk} += {inc}")
            entity.dc_data.pk += inc
            
            assert self.session.dirty, "Session not dirty after dataclass mutation!"
            self.session.commit()
            
            self.session.expire(entity)
            # Mypy не знает, что после перезагрузки поле не None, если мы знаем логику
            # Но для строгости лучше проверить
            assert entity.dc_data is not None
            assert entity.dc_data.pk == old_pk + inc

    @rule(entity=entities, suffix=st.text(min_size=1))
    def mutate_vanilla(self, entity: StressEntity, suffix: str) -> None:
        """Проверка отслеживания изменений в обычном классе"""
        if entity.vanilla_data is None:
            return
            
        with step(f"Rule: Mutate Vanilla ID={entity.id}"):
            self.session.add(entity)
            TRACE.log("MUTATE", f"Vanilla append suffix: {suffix}")
            entity.vanilla_data.raw_data += suffix
            
            assert self.session.dirty
            self.session.commit()
            
            self.session.expire(entity)
            assert entity.vanilla_data is not None
            assert entity.vanilla_data.raw_data.endswith(suffix)

    if HAS_ATTRS:
        @rule(entity=entities, new_score=st.floats(0, 100))
        def mutate_attrs(self, entity: StressEntity, new_score: float) -> None:
            """Проверка отслеживания изменений в Attrs"""
            if entity.attrs_data is None:
                return

            with step(f"Rule: Mutate Attrs ID={entity.id}"):
                self.session.add(entity)
                
                # --- FIX FOR HYPOTHESIS COLLISIONS ---
                if entity.attrs_data.score == new_score:
                     new_score += 1.0
                
                TRACE.log("MUTATE", f"Attrs score -> {new_score}")
                entity.attrs_data.score = new_score
                
                assert self.session.dirty
                self.session.commit()
                
                self.session.expire(entity)
                assert entity.attrs_data is not None
                assert abs(entity.attrs_data.score - new_score) < 0.0001


# =============================================================================
# 6. ZONES
# =============================================================================

@pytest.fixture
def session() -> Iterator[Session]:
    TRACE.log("SETUP", "Creating :memory: session with StaticPool")
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False})
    attach_sql_sniffer(engine)
    Base.metadata.create_all(engine)
    sess = Session(engine)
    yield sess
    TRACE.log("TEARDOWN", "Closing session")
    sess.close()
    Base.metadata.drop_all(engine)

@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(dc=dataclass_strategy)
def test_dataclass_roundtrip(session: Session, dc: CompatibleDataclass) -> None:
    """Отдельный тест чисто для датаклассов"""
    session.rollback()
    entity = StressEntity(name="DC_Test", dc_data=dc, tree_data=Node(name="r"), vanilla_data=None)
    session.add(entity)
    session.commit()
    
    session.expire_all()
    loaded = session.scalars(select(StressEntity).where(StressEntity.id == entity.id)).first()
    assert loaded is not None
    assert loaded.dc_data == dc

# Запуск State Machine
TestDBStateMachine = DBStateMachine.TestCase