# sqlatypemodel Examples

This directory contains ready-to-run examples demonstrating the key features of `sqlatypemodel`.

## Getting Started

Make sure you have the dependencies installed:

```bash
pip install pydantic attrs sqlalchemy aiosqlite orjson
```

## Available Examples

1.  **[01_pydantic_basic.py](./01_pydantic_basic.py)**: Basic setup with Pydantic and SQLAlchemy.
2.  **[02_lazy_loading.py](./02_lazy_loading.py)**: Demonstrates the performance boost of `LazyMutableMixin`.
3.  **[03_dataclasses.py](./03_dataclasses.py)**: Integration with standard Python dataclasses.
4.  **[04_attrs.py](./04_attrs.py)**: Integration with the `attrs` library.
5.  **[05_async_sqlalchemy.py](./05_async_sqlalchemy.py)**: Usage with SQLAlchemy's `AsyncSession`.
6.  **[06_nested_collections.py](./06_nested_collections.py)**: Tracking deep mutations in lists/dicts.
7.  **[07_pickle_celery.py](./07_pickle_celery.py)**: Serialization and task queue compatibility.

## Running

You can run any example directly with Python:

```bash
python 01_pydantic_basic.py
```

All examples use SQLite in-memory databases, so they are safe to run and require no external database setup.
