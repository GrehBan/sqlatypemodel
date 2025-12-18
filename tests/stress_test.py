import sys
import time
import argparse
import random
import string
import uuid
import enum
import threading
import os
import resource  # Linux/Unix specific
from datetime import datetime
from contextlib import contextmanager
from typing import Any, List, Dict, Optional, Set, Iterator
from decimal import Decimal

# =============================================================================
# 0. SETUP & DEPENDENCIES
# =============================================================================
try:
    from pydantic import BaseModel, Field, field_validator
    from sqlalchemy import create_engine, event, select
    from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase, Session, sessionmaker, attributes
    from sqlalchemy.pool import NullPool
    from sqlatypemodel import ModelType, MutableMixin
except ImportError as e:
    print(f"❌ MISSING DEP: {e}")
    sys.exit(1)

# =============================================================================
# 1. FORENSIC LOGGER
# =============================================================================

class ForensicLogger:
    def __init__(self) -> None:
        self.filename = f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        # Line buffered
        self.file = open(self.filename, "w", encoding="utf-8", buffering=1) 
        self.start_global = time.perf_counter_ns()
        self.lock = threading.Lock()
        
        self._write_header()
        print(f"🕵️  FORENSIC LOGGING STARTED: {self.filename}")

    def _write_header(self) -> None:
        self.log_raw("="*100)
        self.log_raw(f"  SQLATYPEMODEL DEEP TRACE | PID: {os.getpid()}")
        self.log_raw(f"  System: {sys.platform} | Python: {sys.version.split()[0]}")
        self.log_raw("="*100 + "\n")

    def log(self, category: str, msg: str, thread_name: str | None = None) -> None:
        if thread_name is None:
            thread_name = threading.current_thread().name
        
        ts = (time.perf_counter_ns() - self.start_global) / 1_000_000  # ms from start
        # resource.getrusage is Unix specific
        try:
            mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 # MB
        except Exception:
            mem = 0.0
        
        formatted = f"[{ts:10.3f}ms] [MEM:{mem:6.2f}MB] [{thread_name:^10}] [{category:^10}] {msg}"
        
        with self.lock:
            print(formatted) # Console
            self.file.write(formatted + "\n") # File

    def log_raw(self, msg: str) -> None:
        with self.lock:
            self.file.write(msg + "\n")

    def close(self) -> None:
        self.log("SYSTEM", "Trace finished. Closing file.")
        self.file.close()

TRACE = ForensicLogger()

# =============================================================================
# 2. PROFILING DECORATORS & CONTEXTS
# =============================================================================

@contextmanager
def step(name: str) -> Iterator[None]:
    """Logs entry, exit, and precise duration of a block."""
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

# =============================================================================
# 3. DATA MODELS
# =============================================================================

class StatusEnum(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"

class ListWrapper(MutableMixin, BaseModel):
    items: List[int] = Field(default_factory=list)

class ComplexTypesModel(MutableMixin, BaseModel):
    decimal_val: Decimal
    created_at: datetime
    uid: uuid.UUID
    status: StatusEnum
    model_config = {"arbitrary_types_allowed": True}

class Node(MutableMixin, BaseModel):
    name: str
    value: int = 0
    children: List["Node"] = Field(default_factory=list)
    tags: Set[str] = Field(default_factory=set)
    meta: Dict[str, Any] = Field(default_factory=dict)
Node.model_rebuild()

class StrictModel(MutableMixin, BaseModel):
    email: str
    age: int = Field(ge=0, le=120)

# =============================================================================
# 4. DB SETUP (FILE BASED FOR STABILITY)
# =============================================================================

class Base(DeclarativeBase):
    pass

class StressEntity(Base):
    __tablename__ = "stress_entities"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    raw_list: Mapped[ListWrapper] = mapped_column(ModelType(ListWrapper), default=ListWrapper)
    complex_data: Mapped[Optional[ComplexTypesModel]] = mapped_column(ModelType(ComplexTypesModel), nullable=True)
    tree_data: Mapped[Node] = mapped_column(ModelType(Node))
    strict_data: Mapped[Optional[StrictModel]] = mapped_column(ModelType(StrictModel), nullable=True)

# ИСПОЛЬЗУЕМ ФАЙЛОВУЮ БД ВМЕСТО :memory: ДЛЯ СТАБИЛЬНОСТИ ПОТОКОВ
DB_FILE = "stress_test.db"
if os.path.exists(DB_FILE):
    os.remove(DB_FILE)

engine = create_engine(
    f"sqlite:///{DB_FILE}", 
    poolclass=NullPool,  # Важно: отключаем пул для файла, чтобы избегать блокировок при закрытии
    connect_args={"timeout": 60} # Ждем блокировки до 60 сек
)

# --- SQL SNIFFER ---
@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn: Any, cursor: Any, statement: Any, parameters: Any, context: Any, executemany: Any) -> None:
    conn.info.setdefault('query_start_time', []).append(time.perf_counter_ns())
    # TRACE.log("SQL_REQ", f"Executing: {statement} | Params: {parameters}")

@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn: Any, cursor: Any, statement: Any, parameters: Any, context: Any, executemany: Any) -> None:
    try:
        start_list = conn.info.get('query_start_time', [])
        if start_list:
            start = start_list.pop(-1)
            duration = (time.perf_counter_ns() - start) / 1000
            # TRACE.log("SQL_RES", f"Done in {duration:.3f}µs")
    except Exception:
        pass

Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)
# Глобальный лок не нужен для SQLite в файловом режиме, если мы полагаемся на его внутренний WAL/Locking,
# но для чистоты теста оставим его для операций записи, чтобы избежать "database is locked" ошибок приложения.
DB_WRITE_LOCK = threading.Lock()

# =============================================================================
# 5. THE TESTS
# =============================================================================

def run_rollback_test() -> None:
    TRACE.log_raw("\n" + "-"*50 + "\nTEST 1: ROLLBACK INTEGRITY\n" + "-"*50)
    
    session = SessionLocal()
    try:
        with step("Setup Entity"):
            entity = StressEntity(name="RollbackTest", tree_data=Node(name="original"))
            session.add(entity)
            session.commit()
            TRACE.log("STATE", f"Entity created. ID: {entity.id}")

        with step("Mutation Phase"):
            entity.tree_data.name = "modified"
            entity.tree_data.value = 999
            TRACE.log("CHECK", f"Session Dirty: {bool(session.dirty)}")
            if not session.dirty:
                 raise AssertionError("Session not dirty after mutation!")

        with step("Rollback Operation"):
            session.rollback()
            TRACE.log("STATE", "Rollback issued")

        with step("Verification"):
            TRACE.log("READ", f"Current Name: {entity.tree_data.name}")
            TRACE.log("READ", f"Current Value: {entity.tree_data.value}")
            if entity.tree_data.name != "original":
                raise AssertionError("Rollback failed on name!")
            if entity.tree_data.value != 0:
                raise AssertionError("Rollback failed on value!")
            
    finally:
        session.close()

def run_deep_mutation_test() -> None:
    TRACE.log_raw("\n" + "-"*50 + "\nTEST 2: DEEP RECURSION & TRACKING\n" + "-"*50)
    
    session = SessionLocal()
    try:
        with step("Build Tree (Depth 10)"):
            root = Node(name="root")
            curr = root
            for i in range(10):
                child = Node(name=f"L{i}")
                curr.children.append(child)
                curr = child
            
            entity = StressEntity(name="DeepTest", tree_data=root)
            session.add(entity)
            session.commit()
        
        with step("Navigate to Leaf"):
            leaf = entity.tree_data
            depth = 0
            while leaf.children:
                leaf = leaf.children[0]
                depth += 1
            TRACE.log("INFO", f"Reached leaf at depth {depth}")

        with step("Modify Leaf"):
            TRACE.log("MUTATE", "Adding tag to leaf set")
            leaf.tags.add("touched_at_bottom")
            
            TRACE.log("MUTATE", "Changing leaf integer value")
            leaf.value = 42

        with step("Check Tracking"):
            is_dirty = session.is_modified(entity)
            TRACE.log("CHECK", f"Entity is_modified: {is_dirty}")
            
            if not is_dirty:
                raise AssertionError("SQLAlchemy did not detect deep change!")

        with step("Commit"):
            session.commit()

        with step("Verify Persistence"):
            session.expire_all()
            reloaded = session.scalars(select(StressEntity).where(StressEntity.name == "DeepTest")).first()
            
            assert reloaded is not None, "Reloaded entity is None!"
            
            leaf_r = reloaded.tree_data
            for _ in range(10): leaf_r = leaf_r.children[0]
            
            TRACE.log("READ", f"Leaf Tags: {leaf_r.tags}")
            if "touched_at_bottom" not in leaf_r.tags:
                raise AssertionError("Deep tag change lost!")

    finally:
        session.close()

def run_concurrency_test() -> None:
    TRACE.log_raw("\n" + "-"*50 + "\nTEST 3: CONCURRENCY THREADING\n" + "-"*50)
    
    # Setup
    with step("Concurrency Setup"):
        s = SessionLocal()
        s.add(StressEntity(name="T1", raw_list=ListWrapper(items=[0])))
        s.add(StressEntity(name="T2", raw_list=ListWrapper(items=[0])))
        s.commit()
        s.close()

    def worker_routine(target_name: str, worker_id: int) -> None:
        th_name = threading.current_thread().name
        TRACE.log("THREAD", f"Worker {worker_id} started for {target_name}")
        
        # Для файловой БД каждый поток создает свое соединение
        local_sess = SessionLocal()
        try:
            with step(f"Read {target_name}"):
                obj = local_sess.scalars(select(StressEntity).where(StressEntity.name == target_name)).first()
            
            assert obj is not None, f"Worker {worker_id} failed to find entity {target_name}"

            for i in range(50):
                obj.raw_list.items.append(worker_id)
                if i % 10 == 0: time.sleep(0.001) 
            
            TRACE.log("THREAD", f"Finished mutations. Waiting for Lock...")
            
            # Даже с файловой БД, SQLite блокирует всю базу на запись.
            # Чтобы избежать 'database is locked', мы синхронизируем commit.
            with DB_WRITE_LOCK:
                TRACE.log("LOCK", f"Acquired Lock. Committing...")
                local_sess.commit()
                TRACE.log("LOCK", "Commit done.")
                
        except Exception as e:
            TRACE.log("ERROR", f"Worker failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            local_sess.close()

    t1 = threading.Thread(target=worker_routine, args=("T1", 1), name="Th-Worker-1")
    t2 = threading.Thread(target=worker_routine, args=("T2", 2), name="Th-Worker-2")

    with step("Running Threads"):
        t1.start()
        t2.start()
        t1.join()
        t2.join()

    with step("Verify Threads"):
        s = SessionLocal()
        r1 = s.scalars(select(StressEntity).where(StressEntity.name == "T1")).first()
        r2 = s.scalars(select(StressEntity).where(StressEntity.name == "T2")).first()
        
        assert r1 is not None
        assert r2 is not None

        c1 = len(r1.raw_list.items)
        c2 = len(r2.raw_list.items)
        TRACE.log("RESULT", f"T1 Items: {c1} (Exp: 51)")
        TRACE.log("RESULT", f"T2 Items: {c2} (Exp: 51)")
        
        if c1 != 51 or c2 != 51:
            raise AssertionError(f"Data loss detected! T1={c1}, T2={c2}")
        s.close()

# =============================================================================
# 6. MAIN EXECUTION
# =============================================================================

def main() -> None:
    try:
        run_rollback_test()
        run_deep_mutation_test()
        run_concurrency_test()
        
        TRACE.log_raw("\n" + "="*50)
        TRACE.log("FINAL", "✅ ALL CHECKS PASSED. NO ANOMALIES DETECTED.")
        TRACE.log_raw("="*50)
        
    except Exception as e:
        TRACE.log("CRITICAL", f"❌ TEST SUITE ABORTED: {e}")
        import traceback
        TRACE.log_raw(traceback.format_exc())
        sys.exit(1)
    finally:
        TRACE.close()
        # Cleanup DB file
        if os.path.exists(DB_FILE):
            try:
                os.remove(DB_FILE)
            except OSError:
                pass

if __name__ == "__main__":
    main()