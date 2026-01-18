# GEMINI.md - sqlatypemodel

## Project Overview

**sqlatypemodel** is a high-performance Python library that provides typed JSON fields for SQLAlchemy with automatic, deep mutation tracking. It solves the "immutable JSON" problem in SQLAlchemy by allowing you to use strictly typed Python objects (Pydantic models, Dataclasses, Attrs) as database columns while ensuring that every change—even in nested structures—is automatically detected and saved.

### Key Technologies
- **SQLAlchemy:** The core database toolkit and ORM.
- **Pydantic (V2):** Primary model validation and serialization framework.
- **orjson:** Used for high-performance JSON serialization/deserialization.
- **Poetry:** Dependency management and packaging.
- **Ruff & Mypy:** Linting and static type checking.

### Architecture
- **State-Based Tracking:** Uses internal `MutableState` tokens to track object identity and parent-child relationships for mutation propagation.
- **JIT Wrapping:** Employs Just-In-Time wrapping of mutable objects (lists, dicts, nested models) to intercept changes.
- **Mixins:** Provides `MutableMixin` (eagerly wraps all fields) and `LazyMutableMixin` (wraps fields on access) for different performance profiles.
- **ModelType:** A custom SQLAlchemy `TypeDecorator` that handles the bridge between Python models and database JSON.

## Building and Running

This project uses **Poetry**.

### Environment Setup
```bash
# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

### Running Tests
```bash
# Run all tests
poetry run pytest

# Run only unit tests
poetry run pytest tests/unit

# Run benchmarks
poetry run pytest tests/performance --benchmark-only
```

### Linting and Type Checking
```bash
# Run ruff check and format
poetry run ruff check .
poetry run ruff format .

# Run mypy type checking
poetry run ruff mypy src/sqlatypemodel
```

## Development Conventions

- **Typing:** Strict typing is required. Use `mypy` to verify. All source code is in `src/sqlatypemodel` and has a `py.typed` marker.
- **Mutation Tracking:** Any new mutable type support should be integrated into `src/sqlatypemodel/mixin/wrapping.py`.
- **Performance:** Hot paths (attribute access in mixins) should be optimized. Avoid `hasattr` where possible, prefer `try-except AttributeError` or direct `object.__getattribute__`.
- **Testing:** Include unit tests for new features and integration tests with SQLAlchemy. Benchmarks should be updated if core logic changes.
- **Versioning:** Follow semantic versioning. Current version is tracked in `pyproject.toml`.

## Key Files
- `src/sqlatypemodel/model_type/model_type.py`: Core SQLAlchemy type implementation.
- `src/sqlatypemodel/mixin/mixin.py`: Base mixin classes for mutation tracking.
- `src/sqlatypemodel/mixin/wrapping.py`: Logic for wrapping standard collections and nested models.
- `src/sqlatypemodel/mixin/state.py`: Internal state management for tracking.
- `src/sqlatypemodel/util/json.py`: `orjson` integration and serialization utilities.
