"""Performance regression detection and benchmarking."""

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, Field

from sqlatypemodel import LazyMutableMixin, MutableMixin


# Test models for performance testing
class PerfEagerModel(MutableMixin, BaseModel):
    """Model for performance testing with eager loading."""

    model_config = {"extra": "allow"}

    data: list[Any] = Field(default_factory=list)
    nested: dict[str, Any] = Field(default_factory=dict)
    counter: int = 0


class PerfLazyModel(LazyMutableMixin, BaseModel):
    """Model for performance testing with lazy loading."""

    model_config = {"extra": "allow"}

    items: list[Any] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    counter: int = 0


class PerformanceBenchmark:
    """Helper class for performance benchmarking."""

    def __init__(
        self,
        name: str,
        baseline_file: Path = Path("performance_baselines.json"),
    ):
        self.name = name
        self.baseline_file = baseline_file
        self.results: dict[str, float] = {}
        self.baselines: dict[str, float] = {}

        # Load existing baselines
        if baseline_file.exists():
            with open(baseline_file) as f:
                self.baselines = json.load(f).get(name, {})

    def measure(self, operation_name: str, iterations: int = 1000):
        """Decorator to measure execution time."""

        def decorator(func):
            def wrapper(*args, **kwargs):
                # Warm up
                for _ in range(10):
                    func(*args, **kwargs)

                # Measure
                start_time = time.perf_counter()
                for _ in range(iterations):
                    func(*args, **kwargs)
                end_time = time.perf_counter()

                avg_time = (
                    (end_time - start_time) / iterations * 1000000
                )  # microseconds
                self.results[operation_name] = avg_time

                return avg_time

            return wrapper

        return decorator

    def check_regression(
        self, operation_name: str, tolerance_percent: float = 20.0
    ) -> bool:
        """Check if performance has regressed beyond tolerance."""
        if operation_name not in self.results:
            return False

        if operation_name not in self.baselines:
            # No baseline to compare against, store current as baseline
            return False

        current = self.results[operation_name]
        baseline = self.baselines[operation_name]

        regression_percent = ((current - baseline) / baseline) * 100

        if regression_percent > tolerance_percent:
            pytest.fail(
                f"Performance regression detected in '{operation_name}': "
                f"current {current:.2f}μs vs baseline {baseline:.2f}μs "
                f"({regression_percent:+.1f}%)"
            )

        return regression_percent > tolerance_percent

    def save_baseline(self) -> None:
        """Save current results as new baseline."""
        all_baselines = {}
        if self.baseline_file.exists():
            with open(self.baseline_file) as f:
                all_baselines = json.load(f)

        all_baselines[self.name] = self.results

        with open(self.baseline_file, "w") as f:
            json.dump(all_baselines, f, indent=2)


class TestPerformanceRegression:
    """Tests for performance regression detection."""

    def test_eager_model_creation_performance(self) -> None:
        """Test eager model creation performance."""
        benchmark = PerformanceBenchmark("eager_model_creation")

        @benchmark.measure("simple_creation", iterations=1000)
        def create_simple_model():
            return PerfEagerModel(data=["item"], nested={"key": "value"})

        @benchmark.measure("complex_creation", iterations=500)
        def create_complex_model():
            return PerfEagerModel(
                data=[f"item_{i}" for i in range(100)],
                nested={f"key_{i}": f"value_{i}" for i in range(50)},
                counter=42,
            )

        # Run measurements
        simple_time = create_simple_model()
        complex_time = create_complex_model()

        # Check for regressions
        benchmark.check_regression("simple_creation", tolerance_percent=25.0)
        benchmark.check_regression("complex_creation", tolerance_percent=25.0)

        # Reasonable performance expectations
        assert (
            simple_time < 500
        ), f"Simple creation too slow: {simple_time:.2f}μs"
        assert (
            complex_time < 2000
        ), f"Complex creation too slow: {complex_time:.2f}μs"

        # Save baseline if this is a first run
        if os.getenv("SAVE_PERFORMANCE_BASELINES"):
            benchmark.save_baseline()

    def test_lazy_model_creation_performance(self) -> None:
        """Test lazy model creation performance."""
        benchmark = PerformanceBenchmark("lazy_model_creation")

        @benchmark.measure("lazy_simple_creation", iterations=1000)
        def create_lazy_simple_model():
            return PerfLazyModel(items=["item"], config={"key": "value"})

        @benchmark.measure("lazy_complex_creation", iterations=500)
        def create_lazy_complex_model():
            return PerfLazyModel(
                items=[f"item_{i}" for i in range(100)],
                config={f"key_{i}": f"value_{i}" for i in range(50)},
                counter=42,
            )

        # Run measurements
        lazy_simple_time = create_lazy_simple_model()
        lazy_complex_time = create_lazy_complex_model()

        # Check for regressions
        benchmark.check_regression(
            "lazy_simple_creation", tolerance_percent=25.0
        )
        benchmark.check_regression(
            "lazy_complex_creation", tolerance_percent=25.0
        )

        # Lazy creation should be faster than eager
        assert (
            lazy_simple_time < 300
        ), f"Lazy simple creation too slow: {lazy_simple_time:.2f}μs"
        assert (
            lazy_complex_time < 1000
        ), f"Lazy complex creation too slow: {lazy_complex_time:.2f}μs"

        # Save baseline if this is a first run
        if os.getenv("SAVE_PERFORMANCE_BASELINES"):
            benchmark.save_baseline()

    def test_mutation_tracking_performance(self) -> None:
        """Test mutation tracking performance."""
        benchmark = PerformanceBenchmark("mutation_tracking")

        # Test eager model mutations
        eager_model = PerfEagerModel(data=[], nested={}, counter=0)

        @benchmark.measure("eager_list_append", iterations=10000)
        def eager_append():
            eager_model.data.append("item")

        @benchmark.measure("eager_dict_assign", iterations=10000)
        def eager_assign():
            eager_model.nested[f"key_{len(eager_model.nested)}"] = "value"

        @benchmark.measure("eager_counter_increment", iterations=10000)
        def eager_increment():
            eager_model.counter += 1

        # Test lazy model mutations
        lazy_model = PerfLazyModel(items=[], config={}, counter=0)

        @benchmark.measure("lazy_list_append", iterations=10000)
        def lazy_append():
            lazy_model.items.append("item")

        @benchmark.measure("lazy_dict_assign", iterations=10000)
        def lazy_assign():
            lazy_model.config[f"key_{len(lazy_model.config)}"] = "value"

        @benchmark.measure("lazy_counter_increment", iterations=10000)
        def lazy_increment():
            lazy_model.counter += 1

        # Run measurements
        eager_append_time = eager_append()
        eager_assign_time = eager_assign()
        eager_increment_time = eager_increment()

        lazy_append_time = lazy_append()
        lazy_assign_time = lazy_assign()
        lazy_increment_time = lazy_increment()

        # Check for regressions
        for op in [
            "eager_list_append",
            "eager_dict_assign",
            "eager_counter_increment",
            "lazy_list_append",
            "lazy_dict_assign",
            "lazy_counter_increment",
        ]:
            benchmark.check_regression(op, tolerance_percent=30.0)

        # Reasonable performance expectations
        assert (
            eager_append_time < 100
        ), f"Eager append too slow: {eager_append_time:.2f}μs"
        assert (
            eager_assign_time < 100
        ), f"Eager assign too slow: {eager_assign_time:.2f}μs"
        assert (
            eager_increment_time < 50
        ), f"Eager increment too slow: {eager_increment_time:.2f}μs"

        assert (
            lazy_append_time < 100
        ), f"Lazy append too slow: {lazy_append_time:.2f}μs"
        assert (
            lazy_assign_time < 100
        ), f"Lazy assign too slow: {lazy_assign_time:.2f}μs"
        assert (
            lazy_increment_time < 50
        ), f"Lazy increment too slow: {lazy_increment_time:.2f}μs"

        # Save baseline if this is a first run
        if os.getenv("SAVE_PERFORMANCE_BASELINES"):
            benchmark.save_baseline()

    def test_deep_structure_performance(self) -> None:
        """Test performance with deeply nested structures."""
        benchmark = PerformanceBenchmark("deep_structure_performance")

        # Create deeply nested model
        deep_model = PerfEagerModel(
            data=[{"nested": {"deep": {"value": i}}} for i in range(10)],
            nested={
                f"level1_{i}": {
                    f"level2_{j}": {
                        f"level3_{k}": list(range(5)) for k in range(3)
                    }
                    for j in range(3)
                }
                for i in range(3)
            },
        )

        @benchmark.measure("deep_mutation", iterations=1000)
        def deep_mutation():
            deep_model.data[0]["nested"]["deep"]["value"] = "modified"

        @benchmark.measure("deep_nested_mutation", iterations=1000)
        def deep_nested_mutation():
            deep_model.nested["level1_0"]["level2_0"]["level3_0"].append(
                "new_item"
            )

        @benchmark.measure("deep_access", iterations=1000)
        def deep_access():
            _ = deep_model.data[0]["nested"]["deep"]["value"]
            _ = deep_model.nested["level1_0"]["level2_0"]["level3_0"]

        # Run measurements
        deep_mutation_time = deep_mutation()
        deep_nested_mutation_time = deep_nested_mutation()
        deep_access_time = deep_access()

        # Check for regressions
        for op in ["deep_mutation", "deep_nested_mutation", "deep_access"]:
            benchmark.check_regression(op, tolerance_percent=35.0)

        # Reasonable performance for deep structures
        assert (
            deep_mutation_time < 500
        ), f"Deep mutation too slow: {deep_mutation_time:.2f}μs"
        assert (
            deep_nested_mutation_time < 500
        ), f"Deep nested mutation too slow: {deep_nested_mutation_time:.2f}μs"
        assert (
            deep_access_time < 200
        ), f"Deep access too slow: {deep_access_time:.2f}μs"

        # Save baseline if this is a first run
        if os.getenv("SAVE_PERFORMANCE_BASELINES"):
            benchmark.save_baseline()

    def test_jit_wrapping_performance(self) -> None:
        """Test JIT wrapping performance for lazy models."""
        benchmark = PerformanceBenchmark("jit_wrapping_performance")

        # Create lazy model but don't access attributes yet
        lazy_model = PerfLazyModel(
            items=[f"item_{i}" for i in range(100)],
            config={f"key_{i}": f"value_{i}" for i in range(50)},
        )

        @benchmark.measure("first_list_access", iterations=100)
        def first_list_access():
            # Access a new model each time to trigger JIT
            model = PerfLazyModel(items=[1, 2, 3, 4, 5])
            _ = model.items[0]  # Triggers JIT wrapping

        @benchmark.measure("first_dict_access", iterations=100)
        def first_dict_access():
            # Access a new model each time to trigger JIT
            model = PerfLazyModel(config={"key": "value"})
            _ = model.config["key"]  # Triggers JIT wrapping

        @benchmark.measure("cached_list_access", iterations=10000)
        def cached_list_access():
            _ = lazy_model.items[0]  # Should use cached JIT wrapper

        @benchmark.measure("cached_dict_access", iterations=10000)
        def cached_dict_access():
            _ = lazy_model.config["key_0"]  # Should use cached JIT wrapper

        # Run measurements
        first_list_time = first_list_access()
        first_dict_time = first_dict_access()
        cached_list_time = cached_list_access()
        cached_dict_time = cached_dict_access()

        # Check for regressions
        for op in [
            "first_list_access",
            "first_dict_access",
            "cached_list_access",
            "cached_dict_access",
        ]:
            benchmark.check_regression(op, tolerance_percent=40.0)

        # JIT wrapping has overhead but should be reasonable
        assert (
            first_list_time < 1000
        ), f"First list access too slow: {first_list_time:.2f}μs"
        assert (
            first_dict_time < 500
        ), f"First dict access too slow: {first_dict_time:.2f}μs"

        # Cached access should be fast
        assert (
            cached_list_time < 20
        ), f"Cached list access too slow: {cached_list_time:.2f}μs"
        assert (
            cached_dict_time < 20
        ), f"Cached dict access too slow: {cached_dict_time:.2f}μs"

        # Cached should be faster than first access
        assert (
            cached_list_time < first_list_time
        ), "Cached list access should be faster than first access"
        assert (
            cached_dict_time < first_dict_time
        ), "Cached dict access should be faster than first access"

        # Save baseline if this is a first run
        if os.getenv("SAVE_PERFORMANCE_BASELINES"):
            benchmark.save_baseline()

    def test_memory_allocation_performance(self) -> None:
        """Test memory allocation performance."""
        benchmark = PerformanceBenchmark("memory_allocation_performance")

        @benchmark.measure("bulk_model_creation", iterations=100)
        def bulk_creation():
            return [
                PerfEagerModel(
                    data=[f"item_{j}" for j in range(10)],
                    nested={f"key_{j}": f"value_{j}" for j in range(5)},
                )
                for _ in range(100)
            ]

        @benchmark.measure("bulk_lazy_creation", iterations=100)
        def bulk_lazy_creation():
            return [
                PerfLazyModel(
                    items=[f"item_{j}" for j in range(10)],
                    config={f"key_{j}": f"value_{j}" for j in range(5)},
                )
                for _ in range(100)
            ]

        @benchmark.measure("bulk_mutation", iterations=50)
        def bulk_mutation():
            model = PerfEagerModel(data=list(range(1000)))
            for i in range(100):
                model.data.append(f"new_item_{i}")
                model.data[i] = f"modified_{i}"
            return model

        # Run measurements
        bulk_creation_time = bulk_creation()
        bulk_lazy_creation_time = bulk_lazy_creation()
        bulk_mutation_time = bulk_mutation()

        # Check for regressions
        for op in [
            "bulk_model_creation",
            "bulk_lazy_creation",
            "bulk_mutation",
        ]:
            benchmark.check_regression(op, tolerance_percent=30.0)

        # Reasonable performance expectations
        assert (
            bulk_creation_time < 50000
        ), f"Bulk creation too slow: {bulk_creation_time:.2f}μs"
        assert (
            bulk_lazy_creation_time < 20000
        ), f"Bulk lazy creation too slow: {bulk_lazy_creation_time:.2f}μs"
        assert (
            bulk_mutation_time < 20000
        ), f"Bulk mutation too slow: {bulk_mutation_time:.2f}μs"

        # Lazy should be faster for bulk creation
        assert (
            bulk_lazy_creation_time < bulk_creation_time
        ), "Lazy bulk creation should be faster"

        # Save baseline if this is a first run
        if os.getenv("SAVE_PERFORMANCE_BASELINES"):
            benchmark.save_baseline()


class TestPerformanceComparison:
    """Compare performance between different approaches."""

    def test_eager_vs_lazy_performance_comparison(self) -> None:
        """Compare eager vs lazy loading performance."""
        eager_times = []
        lazy_times = []

        # Test model creation
        for _ in range(100):
            start = time.perf_counter()
            PerfEagerModel(data=["item"], config={"key": "value"})
            eager_times.append((time.perf_counter() - start) * 1000000)

            start = time.perf_counter()
            PerfLazyModel(items=["item"], config={"key": "value"})
            lazy_times.append((time.perf_counter() - start) * 1000000)

        avg_eager = sum(eager_times) / len(eager_times)
        avg_lazy = sum(lazy_times) / len(lazy_times)

        # Lazy should generally be faster for creation
        lazy_speedup = avg_eager / avg_lazy
        assert (
            lazy_speedup > 1.5
        ), f"Lazy creation should be significantly faster (speedup: {lazy_speedup:.2f}x)"

        # Test first access performance (JIT overhead)
        lazy_first_access_times = []
        for _ in range(50):
            model = PerfLazyModel(items=["test_item"])
            start = time.perf_counter()
            _ = model.items[0]  # Triggers JIT
            lazy_first_access_times.append(
                (time.perf_counter() - start) * 1000000
            )

        avg_first_access = sum(lazy_first_access_times) / len(
            lazy_first_access_times
        )

        # First access can be slower than eager, but should be reasonable
        assert (
            avg_first_access < avg_eager * 5
        ), "First access too slow compared to eager creation"
