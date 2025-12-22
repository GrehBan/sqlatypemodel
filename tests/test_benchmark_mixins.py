"""Performance benchmarks for mixins."""
from typing import Any

from pydantic import BaseModel

from sqlatypemodel import LazyMutableMixin, MutableMixin


class EagerModel(MutableMixin, BaseModel):
    data: dict[str, Any]

class LazyModel(LazyMutableMixin, BaseModel):
    data: dict[str, Any]

def generate_complex_data(depth: int = 3, width: int = 3) -> dict[str, Any]:
    if depth == 0:
        return {"val": 1}
    return {
        f"field_{i}": generate_complex_data(depth - 1, width)
        for i in range(width)
    }

DATA_SAMPLE = generate_complex_data(depth=4, width=3)

def test_benchmark_db_load_eager(benchmark: Any) -> None:
    def load_eager() -> None:
        _ = EagerModel(data=DATA_SAMPLE)
    benchmark(load_eager)

def test_benchmark_db_load_lazy(benchmark: Any) -> None:
    def load_lazy() -> None:
        _ = LazyModel(data=DATA_SAMPLE)
    benchmark(load_lazy)

def test_benchmark_read_access_lazy_cached(benchmark: Any) -> None:
    model = LazyModel(data=DATA_SAMPLE)
    _ = model.data

    def read_lazy_cached() -> None:
        _ = model.data
    benchmark(read_lazy_cached)