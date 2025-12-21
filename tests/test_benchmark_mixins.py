"""Performance benchmarks comparing Eager vs Lazy implementations."""

import pytest
from sqlatypemodel import LazyMutableMixin, MutableMixin


class EagerModel(MutableMixin):
    pass

class LazyModel(LazyMutableMixin):
    pass


def generate_complex_data(depth=3, width=3):
    if depth == 0:
        return "leaf"
    return {
        f"field_{i}": generate_complex_data(depth - 1, width)
        for i in range(width)
    }

DATA_SAMPLE = generate_complex_data(depth=4, width=3)
N_OBJECTS = 5000


def test_benchmark_db_load_eager(benchmark):
    """Benchmark Eager loading simulation."""
    def load_eager():
        objects = []
        for _ in range(N_OBJECTS):
            obj = EagerModel()
            object.__setattr__(obj, "data", DATA_SAMPLE.copy())
            obj._restore_tracking()
            objects.append(obj)
        return objects

    benchmark(load_eager)


def test_benchmark_db_load_lazy(benchmark):
    """Benchmark Lazy loading simulation."""
    def load_lazy():
        objects = []
        for _ in range(N_OBJECTS):
            obj = LazyModel()
            object.__setattr__(obj, "data", DATA_SAMPLE.copy())
            objects.append(obj)
        return objects

    benchmark(load_lazy)


def test_benchmark_read_access_lazy_cached(benchmark):
    """Benchmark repeated read access on Lazy model (should be cached)."""
    objects = []
    for _ in range(1000):
        obj = LazyModel()
        object.__setattr__(obj, "data", DATA_SAMPLE.copy())
        _ = obj.data  # Warm up cache
        objects.append(obj)

    def read_lazy_cached():
        for obj in objects:
            _ = obj.data

    benchmark(read_lazy_cached)