from __future__ import annotations

import gc
import time

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from sqlatypemodel import LazyMutableMixin, ModelType, MutableMixin
from sqlatypemodel.util.sqlalchemy import create_engine

# --- MODELS ---


class NestedModel(BaseModel):
    id: int
    data: list[int] = Field(default_factory=lambda: list(range(10)))
    meta: dict[str, str] = {"key": "value", "type": "test"}


class EagerSettings(MutableMixin, BaseModel):
    label: str = "benchmark"
    items: list[NestedModel] = Field(default_factory=list)


class LazySettings(LazyMutableMixin, BaseModel):
    label: str = "benchmark"
    items: list[NestedModel] = Field(default_factory=list)


class Base(DeclarativeBase):
    pass


class EagerEntity(Base):
    __tablename__ = "eager_entities"
    id: Mapped[int] = mapped_column(primary_key=True)
    settings: Mapped[EagerSettings] = mapped_column(ModelType(EagerSettings))


class LazyEntity(Base):
    __tablename__ = "lazy_entities"
    id: Mapped[int] = mapped_column(primary_key=True)
    settings: Mapped[LazySettings] = mapped_column(ModelType(LazySettings))


# --- BENCHMARK LOGIC ---


def get_memory():
    """Simple memory usage helper (Linux/macOS)."""
    try:
        import psutil

        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024  # MB
    except ImportError:
        return 0


def run_detailed_bench(count: int = 5000):
    print(f"--- sqlatypemodel detailed comparison (N={count}) ---")

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    # 1. Preparation
    sample_items = [NestedModel(id=i) for i in range(5)]
    eager_data = [
        EagerEntity(settings=EagerSettings(items=sample_items))
        for _ in range(count)
    ]
    lazy_data = [
        LazyEntity(settings=LazySettings(items=sample_items))
        for _ in range(count)
    ]

    with Session(engine) as session:
        session.add_all(eager_data)
        session.add_all(lazy_data)
        session.commit()

    print(f"Database populated. Memory: {get_memory():.2f} MB\n")

    # --- EAGER TEST ---
    gc.collect()
    start_mem = get_memory()
    start_time = time.perf_counter()

    with Session(engine) as session:
        # Load phase
        t0 = time.perf_counter()
        results_eager = session.execute(select(EagerEntity)).scalars().all()
        t_load_eager = (time.perf_counter() - t0) * 1000

        # Access phase (reading a nested value)
        t0 = time.perf_counter()
        for obj in results_eager:
            _ = obj.settings.items[0].id
        t_access_eager = (time.perf_counter() - t0) * 1000

        # Mutation phase
        t0 = time.perf_counter()
        results_eager[0].settings.items[0].id = 999
        session.commit()
        t_mutate_eager = (time.perf_counter() - t0) * 1000

    total_eager = (time.perf_counter() - start_time) * 1000
    end_mem_eager = get_memory() - start_mem

    # --- LAZY TEST ---
    gc.collect()
    start_mem = get_memory()
    start_time = time.perf_counter()

    with Session(engine) as session:
        # Load phase (should be near instant)
        t0 = time.perf_counter()
        results_lazy = session.execute(select(LazyEntity)).scalars().all()
        t_load_lazy = (time.perf_counter() - t0) * 1000

        # Access phase (JIT wrapping happens here)
        t0 = time.perf_counter()
        for obj in results_lazy:
            # Trigger JIT wrapping for 'settings' and then 'items'
            _ = obj.settings.items[0].id
        t_access_lazy = (time.perf_counter() - t0) * 1000

        # Mutation phase
        t0 = time.perf_counter()
        results_lazy[0].settings.items[0].id = 999
        session.commit()
        t_mutate_lazy = (time.perf_counter() - t0) * 1000

    total_lazy = (time.perf_counter() - start_time) * 1000
    end_mem_lazy = get_memory() - start_mem

    # --- OUTPUT ---

    header = (
        f"{'Phase':<20} | {'Eager (ms)':<15} | "
        f"{'Lazy (ms)':<15} | {'Improvement'}"
    )
    print(header)
    print("-" * len(header))

    load_ratio = t_load_eager / max(t_load_lazy, 0.001)
    print(
        f"{'1. DB Load':<20} | {t_load_eager:>15.2f} | "
        f"{t_load_lazy:>15.2f} | {load_ratio:>10.1f}x"
    )

    access_ratio = t_access_eager / max(t_access_lazy, 0.001)
    print(
        f"{'2. First Access':<20} | {t_access_eager:>15.2f} | "
        f"{t_access_lazy:>15.2f} | {access_ratio:>10.1f}x"
    )

    mutate_ratio = t_mutate_eager / max(t_mutate_lazy, 0.001)
    print(
        f"{'3. Mutation/Commit':<20} | {t_mutate_eager:>15.2f} | "
        f"{t_mutate_lazy:>15.2f} | {mutate_ratio:>10.1f}x"
    )

    print("-" * len(header))
    total_ratio = total_eager / total_lazy
    print(
        f"{'TOTAL TIME':<20} | {total_eager:>15.2f} | "
        f"{total_lazy:>15.2f} | {total_ratio:>10.1f}x"
    )

    print("\n--- Resource Usage ---")
    print(f"Memory overhead (Eager): {end_mem_eager:.2f} MB")
    print(f"Memory overhead (Lazy):  {end_mem_lazy:.2f} MB")
    print("\n--- Analysis ---")
    print(
        "1. DB Load: Lazy is significantly faster because it "
        "fetches raw JSON and defers model validation/wrapping."
    )
    print(
        "2. First Access: Eager is faster here because wrapping "
        "happened at load. Lazy pays the 'JIT tax' now."
    )
    print(
        "3. Strategy: Use LazyMutableMixin for Large Queries "
        "where you only need a few fields or simple display."
    )
    print(
        "   Use MutableMixin for Write-Heavy loops where every "
        "object WILL be modified."
    )


if __name__ == "__main__":
    run_detailed_bench(5000)
