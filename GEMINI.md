# GEMINI.md - Project Context

## Project Overview

**sqlatypemodel** is a high-performance Python library designed to solve the "immutable JSON" problem in SQLAlchemy. It provides a typed `ModelType` for SQLAlchemy columns that allows using **Pydantic**, **Dataclasses**, or **Attrs** models while ensuring that deep mutations are automatically tracked and persisted.

### Key Technologies
- **Python 3.10+** (Fully tested up to 3.14)
- **SQLAlchemy 2.0+**
- **orjson**: Primary serialization engine with standard `json` fallback.
- **Strict Typing**: 100% `mypy --strict` compliant codebase.
- **State-Based Architecture**: Uses `MutableState` tokens for identity tracking, supporting unhashable models without monkey-patching.

### Core Components
- `ModelType`: SQLAlchemy `TypeDecorator` handling serialization and tracking restoration.
- `MutableMixin`: Eager tracking mixin for immediate change detection.
- `LazyMutableMixin`: JIT wrapping mixin for maximum load performance (~150x faster).
- `examples/`: Full suite of functional example scripts.

---

## Architecture & Logic Flow

The library employs a "bubble-up" mutation signal:
1. **Leaf Change**: A change in a nested collection (e.g., `list.append()`) triggers `self.changed()`.
2. **State Propagation**: The signal travels up through `MutableState` tokens via `safe_changed()`.
3. **Root Signal**: The signal reaches the top-level SQLAlchemy model, triggering `flag_modified()`.

---

## Building and Running

### Installation
```bash
pip install .[fast]
```

### Testing & Linting
```bash
# Full verification suite
pytest tests/ -v
mypy sqlatypemodel
ruff check .
black --check .
```

---

## Recent Major Improvements (v0.8.0)
- **Strict Type Safety**: Eliminated all `Any` where possible and removed all `type: ignore` comments.
- **Improved DX**: Added `@overload` signatures to decorators for better IDE support.
- **Modular Refactoring**: Split internal logic into `_introspection_data.py` and `_sentinel.py`.
- **Automated CI/CD**: Added linting and type checking to GitHub Actions.
- **Documentation**: New `ARCHITECTURE.md`, expanded `README.md`, and full `examples/` directory.

---

## File Structure Highlights

- `sqlatypemodel/mixin/`: Core logic (`state.py`, `wrapping.py`, `events.py`).
- `sqlatypemodel/model_type/`: SQLAlchemy integration.
- `sqlatypemodel/util/`: Helpers for JSON, Dataclasses, and Attrs.
- `examples/`: Ready-to-run feature demonstrations.
- `tests/`: Comprehensive test suite.