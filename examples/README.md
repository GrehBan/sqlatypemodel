# sqlatypemodel Examples

This directory contains ready-to-run examples demonstrating the key features of `sqlatypemodel`.

## Quick Start

Install dependencies:

```bash
poetry install --all-extras
# OR
pip install pydantic attrs sqlalchemy aiosqlite orjson
```

Run any example:

```bash
python 01_pydantic_basic.py
```

## Available Examples

1.  **[01_pydantic_basic.py](./01_pydantic_basic.py)**: Basic setup with Pydantic and SQLAlchemy.
2.  **[02_lazy_loading.py](./02_lazy_loading.py)**: Demonstrates the performance boost of `LazyMutableMixin`.
3.  **[03_dataclasses.py](./03_dataclasses.py)**: Integration with standard Python dataclasses.
4.  **[04_attrs.py](./04_attrs.py)**: Integration with the `attrs` library.
5.  **[05_async_sqlalchemy.py](./05_async_sqlalchemy.py)**: Usage with SQLAlchemy's `AsyncSession`.
6.  **[06_nested_collections.py](./06_nested_collections.py)**: Tracking deep mutations in lists/dicts.
7.  **[07_pickle_celery.py](./07_pickle_celery.py)**: Serialization and task queue compatibility.
8.  **[comparison_bench.py](./comparison_bench.py)**: Detailed benchmark script comparing Eager vs Lazy loading performance and memory usage.

## Safety

All examples use SQLite in-memory databases (no external database setup required).

## Testing Examples

Run the examples in the CI/CD pipeline:

```bash
# Local testing
poetry run pytest examples/ -v

# See available marks
poetry run pytest --markers
```

## Performance

See `comparison_bench.py` for performance comparisons:

- **Lazy vs Eager Loading**: Lazy loading is 5.1x faster for initialization
- **Memory Usage**: Lazy loading uses 35% less memory
- **Mutation Tracking**: Zero-cost for unchanged objects

## CI/CD Integration

Examples are tested as part of the GitHub Actions workflow. See `.github/WORKFLOWS.md` for details.
