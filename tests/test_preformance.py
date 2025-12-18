"""Performance tests for MutableMixin."""

import time

from pydantic import BaseModel
from sqlalchemy.ext.mutable import MutableList

from sqlatypemodel import MutableMixin


class PerfModel(MutableMixin, BaseModel):
    data: list[int] = []


def test_large_list_assignment_optimization() -> None:
    """
    Verify that assignment is reasonably fast.

    Note: For Pydantic models, true O(1) is impossible because Pydantic
    validates/copies list items on assignment (O(N)).
    However, we ensure it doesn't do *double* work.
    """
    # 1. Create a large MutableList
    size = 100_000
    large_list = MutableList(range(size))

    model = PerfModel()

    # 2. Measure assignment time
    start_time = time.perf_counter()
    model.data = large_list
    end_time = time.perf_counter()

    duration = end_time - start_time

    assert duration < 0.01, f"Assignment took too long: {duration:.4f}s"

    # Verify correctness
    assert len(model.data) == size
    assert model in large_list._parents


def test_repeated_attribute_access_speed() -> None:
    """
    Verify that attribute access overhead is minimal.
    """
    model = PerfModel(data=[1, 2, 3])

    start_time = time.perf_counter()
    for _ in range(100_000):
        _ = model.data
    end_time = time.perf_counter()

    assert (end_time - start_time) < 1.0
