# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2025-12-21

A performance-focused release introducing **Lazy Loading** architecture, caching mechanisms, and a complete codebase refactor for strict typing and modularity.

### Added

* **Lazy Loading (`LazyMutableMixin`)**: Implemented a **Just-In-Time (JIT)** wrapping strategy.
* **Performance**: Benchmarks demonstrate a **157x speedup** during database loading (7ms vs 1100ms for 5000 objects) by deferring wrapper creation until the moment of attribute access.
* **Robustness**: Automatically handles data injected via "backdoors" (e.g., `pickle`, `model_construct`, direct `__dict__` manipulation) via `__getattribute__` interception.


* **Introspection Caching**: Applied `@lru_cache(maxsize=4096)` to `inspection.ignore_attr_name`. This eliminates introspection overhead for repeated attribute access, reducing the cost of checks to near-zero (O(1)).
* **Benchmarking Suite**: Added `tests/test_benchmark_mixins.py` using `pytest-benchmark` to objectively measure and compare Eager vs. Lazy performance characteristics under load.
* **Modular Architecture**: Split monolithic logic into focused modules:
* `inspection.py`: Validation and attribute scanning.
* `wrapping.py`: Recursive collection wrapping logic.
* `events.py`: Change propagation and `safe_changed` logic.
* `protocols.py`: Strict typing definitions (`Trackable`).



### Changed

* **Code Quality**: Enforced **Google-style docstrings**, `Black` formatting (79 char limit), and `Ruff` rules (`I`, `UP`, `F`, `E`) across the entire codebase.
* **Optimization Strategy**: Reordered attribute validation checks in `inspection.py`. Fast string operations (prefix checks, set lookups) are now performed before expensive object introspection.
* **Test Architecture**: Migrated all tests to the **Ideal Test Architecture**:
* Centralized fixtures in `tests/conftest.py` (Session, Engine, Models).
* Removed `unittest` class-based tests in favor of functional `pytest`.
* Added comprehensive type hints to all test files.



### Fixed

* **Constants Definition**: Fixed a syntax error in `constants.py` where `_ATOMIC_TYPES` was incorrectly defined as a tuple containing a set, instead of a flat `frozenset`.
* **Type Safety**: Resolved circular imports between `mixin.py` and `model_type.py` using strictly typed protocols and conditional imports.

## [0.6.0] - 2025-12-19

A major feature release introducing full **Pickle support** (enabling Caching/Celery workflows), correcting critical identity hashing logic, and fully aligning with SQLAlchemy 2.0 patterns.

### Added
- **Pickle Support**: Implemented robust `__getstate__` and `__setstate__` methods in `MutableMixin`.
    - Handles **Pydantic V2** nested state structures (`__dict__` inside state).
    - Automatically cleans up unpicklable `WeakKeyDictionary` (`_parents`).
    - **Self-Healing**: Automatically triggers `_scan_and_wrap_fields()` after unpickling to restore parent-child tracking relationships, preventing "orphaned" nested objects.
- **Identity Integrity**: Added a `__new__` hook in `MutableMixin` to forcibly restore `__hash__ = object.__hash__`. This ensures compatibility with `@dataclass` and `@attrs` (which typically strip hashing from mutable objects), preventing `TypeError: unhashable type` when used in tracking dictionaries.
- **Testing**: Added `tests/conftest.py` with centralized fixtures (`session`, `engine`) and refactored the entire test suite to native **Pytest** patterns, removing legacy `unittest` dependencies.

### Changed
- **Hashing Logic**: `MutableMixin` now strictly enforces **Identity-based hashing**. This guarantees that modifying a field (e.g., `user.name = "new"`) does not change the object's hash, which is critical for maintaining stable references in `_parents`.
- **Test Suite**:
    - **Performance**: Adjusted overhead thresholds (to 500x) to realistically reflect the cost of recursive Python-based wrapping versus C-based Pydantic assignment.
    - **Fuzzing**: Constrained Hypothesis strategies in `test_stress.py` to generate strictly **64-bit signed integers**, aligning with `orjson` and SQLite limits.

### Fixed
- **Serialization**: Fixed `_pickle.PicklingError` when using local classes in tests by moving test models to the global scope.
- **SQLAlchemy 2.0**: Fixed `InvalidRequestError` in integration tests by ensuring models inherit from a subclass of `DeclarativeBase`, not `DeclarativeBase` directly.
- **Integration**: Resolved `DetachedInstanceError` in Pickle workflows by ensuring attributes are eager-loaded before `session.expunge()`.
- **Pydantic V2**: Fixed a regression where `__getstate__` failed to clean up `_parents` hidden inside Pydantic's nested `__dict__` state structure.

## [0.5.1] - 2025-12-18

A release focused on rigorous testing, cross-database compatibility, and extending support for non-Pydantic models.

### Added
- **Testing**: Integrated **Hypothesis** for property-based testing. The suite now fuzzes thousands of edge cases, including deep nesting, Unicode sequences, and large integers.
- **Utilities**: Added `sqlalchemy_utils` helper module with `create_sync_engine` and `create_async_engine`. These helpers automatically configure `orjson` as the serializer/deserializer, ensuring correct behavior across different SQL dialects (SQLite/Postgres).
- **Architecture**: Officially confirmed and tested support for **Python Dataclasses** and **Attrs** (via `MutableMixin` and Identity Hashing).
- **CI/CD**: Added comprehensive stress tests (`tests/test_stress.py`) verifying concurrency safety, rollback integrity, and memory stability under load.

### Changed
- **Serialization**: `orjson` is now the serialization engine. This provides significant performance gains but introduces a **strict 64-bit signed integer limit** (-2^63 to 2^63-1).
- **Validation**: `MutableMixin` now performs a "short-circuit" identity check before marking objects as dirty. If `new_value is old_value`, the update is skipped to reduce DB overhead.
- **Documentation**: Major README overhaul. Added sections on "Under the Hood" architecture, performance benchmarks, and specific caveats regarding `orjson` integer limits.

### Fixed
- **Testing**: Resolved `sqlite3.OperationalError: no such table` in tests by enforcing `StaticPool` for in-memory SQLite databases during Hypothesis runs.
- **Compatibility**: Fixed `TypeError` when using `orjson` with SQLAlchemy on SQLite (bytes vs string mismatch) by adding an automatic decoding layer in `sqlalchemy_utils`.

## [0.5.0] - 2025-12-18

A major release focused on stability, security, and improved Developer Experience (DX).

### Added
- **Logging**: Implemented structured logging (DEBUG/WARNING/ERROR levels) in `ModelType` and `MutableMixin` to facilitate production debugging without side effects on import.
- **Safety**: Added protection against infinite recursion and DoS attacks via deep JSON nesting. Default limit: 100 levels (configurable via `_max_nesting_depth`).
- **Typing**: Added `py.typed` marker file to `sqlatypemodel/` to support strict type checking (mypy) in user code.
- **Performance**: Optimized `__setattr__` for atomic types (`int`, `str`, `bool`, `float`, `NoneType`, `bytes`, `complex`, `frozenset`) — they now skip the wrapping phase entirely, reducing overhead.

### Changed
- **Error Handling**: The `safe_changed` method no longer swallows critical errors. Expected errors (e.g., dead weakrefs) are logged as DEBUG, while unexpected failures are logged as ERROR with tracebacks.
- **Registration**: Enforced stricter logic in `__init_subclass__`. The `associate` class must now inherit from `ModelType`. Custom types require manual registration via `associate_with`.
- **Versioning**: Package version is now resolved dynamically via `importlib.metadata`, eliminating the risk of mismatch between `pyproject.toml` and `__init__.py`.

### Fixed
- **Pydantic V2 Compatibility**: Fixed a critical issue where `MutableMixin` intercepted Pydantic V2 internal attributes (e.g., `model_fields`), causing conflicts during model initialization.
- **Critical Bug**: Resolved version mismatch
- **Performance**: Fixed potential O(N) complexity in collection change detection. It now uses strict identity checks (O(1)) for lists and dicts.