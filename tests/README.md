# sqlatypemodel Test Suite

This directory contains the comprehensive test suite for `sqlatypemodel`. It uses `pytest` and `hypothesis` for property-based testing.

## Test Structure

The tests are organized into logical categories:

*   **`unit/`**: Isolated unit tests for core components
    *   `test_mixin_core.py`: Tests for `MutableMixin`
    *   `test_lazy.py`: Tests for `LazyMutableMixin` logic
    *   `test_wrapping_logic.py`, `test_state.py`, `test_events.py`: Focused tests for internal logic
*   **`integration/`**: Integration with external systems
    *   `test_sqlalchemy.py`: Core SQLAlchemy integration scenarios
    *   `test_database_specific.py`: PostgreSQL/MySQL compatibility
    *   `test_async_integration.py`: `sqlalchemy.ext.asyncio` support
    *   `test_pickle.py`: Pickling and serialization
*   **`performance/`**: Benchmarks and performance verification
    *   `test_performance.py`, `test_performance_comprehensive.py`: Benchmarks
    *   `test_memory_leaks.py`: Memory usage tests
*   **`concurrency/`**: Thread safety verification
    *   `test_concurrency.py`: Concurrent mutation tests
*   **`property/`**: Hypothesis-based fuzz testing
    *   `test_property_based.py`: Random input testing

## Running Tests

### Quick Start

```bash
poetry run pytest -v
```

### Verbose Output

```bash
poetry run pytest -v --tb=short
```

### Coverage Report

```bash
poetry run pytest --cov=sqlatypemodel --cov-report=term-missing
```

### Specific Test Categories

```bash
# Only unit tests
poetry run pytest tests/unit/ -v

# Only integration tests
poetry run pytest tests/integration/ -v

# Only benchmarks
poetry run pytest tests/performance/ -v -m benchmark

# Exclude slow tests
poetry run pytest -v -m "not slow"
```

### Database Integration Tests

Some tests require PostgreSQL and MySQL instances.

**Setup:**

```bash
# Set environment variables
export POSTGRES_HOST=localhost
export POSTGRES_USER=test
export POSTGRES_PASSWORD=test
export POSTGRES_DB=test

export MYSQL_HOST=localhost
export MYSQL_USER=test
export MYSQL_PASSWORD=test
export MYSQL_DB=test
```

**Run with Docker Compose:**

```bash
docker-compose up -d postgres mysql
poetry run pytest tests/integration/test_database_specific.py -v
docker-compose down
```

## CI/CD Integration

All tests run automatically on:

- **Every push**: Via `tests.yml` workflow
- **Pull requests**: Full test matrix on Python 3.10-3.14
- **Databases**: PostgreSQL 13+ and MySQL 8.0+

See `.github/WORKFLOWS.md` for CI/CD details.

## Performance Benchmarks

Run performance tests locally:

```bash
poetry run pytest tests/performance/ -v -m benchmark

# Or specific benchmark
poetry run pytest tests/performance/test_performance.py::test_lazy_loading_benchmark -v
```

Key metrics tracked:

- Lazy vs Eager loading performance
- Memory usage
- Mutation tracking overhead
- Serialization speed

## Test Coverage

Target: 100% coverage on source code

```bash
poetry run pytest --cov=sqlatypemodel --cov-report=html
open htmlcov/index.html
```

## Common Issues

**PostgreSQL not available:**
- Tests skip automatically if not configured
- Set environment variables to enable

**MySQL not available:**
- Tests skip automatically if not configured
- Set environment variables to enable

**Memory tests fail:**
- May occur on systems with memory pressure
- Run in isolation: `poetry run pytest tests/unit/test_memory_leaks.py -v`

## Contributing Tests

When adding new features:

1. Add unit test in `tests/unit/`
2. Add integration test in `tests/integration/`
3. Update performance benchmarks if applicable
4. Ensure coverage stays at 100%
5. Run: `poetry run pytest --cov=sqlatypemodel -v`
