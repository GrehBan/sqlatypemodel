# tests/test_performance.py
import time

import pytest
from pydantic import BaseModel
from sqlalchemy.ext.mutable import MutableList

from sqlatypemodel import MutableMixin


class PerfModel(MutableMixin, BaseModel):
    data: list[int] = []

class TestAssignmentPerformance:
    @pytest.mark.benchmark(group="wrapping")
    def test_large_list_assignment_optimization(self) -> None:
        size = 100_000
        large_list = MutableList(range(size))
        model = PerfModel()

        start_time = time.perf_counter()
        model.data = large_list
        duration = time.perf_counter() - start_time

        assert duration < 0.01, f"Assignment too slow: {duration:.4f}s"
        assert len(model.data) == size
        
        assert model._state in large_list._parents

    def test_repeated_attribute_access_speed(self) -> None:
        """Benchmark overhead of __getattribute__ interception."""
        model = PerfModel(data=[1, 2, 3])
        
        _ = model.data

        start = time.perf_counter()
        for _ in range(100_000):
            _ = model.data
        duration = time.perf_counter() - start
        
        assert duration < 0.2, f"Access too slow: {duration:.4f}s"