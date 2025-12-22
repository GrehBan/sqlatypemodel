# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2025-12-22

A **major performance and architecture release**. This version introduces the **Lazy Loading** architecture (up to **150x faster reads**), production-grade optimizations, new developer utilities, and a complete codebase refactor.

### 🚀 New Features

- **Lazy Loading (`LazyMutableMixin`)**:
  - **Zero-cost loading**: Objects loaded from the database remain as raw Python dicts/lists until accessed.
  - **JIT (Just-In-Time) Wrapping**: Mutation tracking wrappers are created on-demand via `__getattribute__` interception.
  - **Performance**: Loading 5,000 nested objects takes **~7ms** (Lazy) vs **~1100ms** (Eager).
  - **Robustness**: Automatically handles data injected via "backdoors" (e.g., `pickle`, `__dict__` update) by restoring tracking dynamically upon access.

- **Developer Utilities**:
  - **SQLAlchemy Helpers** (`sqlatypemodel.util.sqlalchemy`): Added `create_engine` and `create_async_engine` wrappers that automatically configure `orjson` serializers with fallback logic.
  - **Attrs Helper** (`sqlatypemodel.util.attrs`): Added a `define` wrapper that enforces `slots=False` and `eq=False`, preventing common runtime errors with `attrs` models.

- **Batching & Optimization**:
  - **Batch Context**: Introduced `batch_changes()` context manager. It suppresses intermediate change notifications during bulk updates, triggering only one SQL flag at the end.
  - **Sentinel Pattern**: Introduced `constants.MISSING` to correctly distinguish between "attribute doesn't exist" and "attribute is None", fixing silent failures on first assignment.

- **ForceHashMixin**:
  - New mixin ensuring objects remain hashable (using Identity Hashing) even when frameworks like Pydantic or Attrs try to disable `__hash__`. Critical for `WeakKeyDictionary` tracking logic.

### ⚡ Performance Improvements

- **Introspection Caching**:
  - Implemented `@lru_cache(maxsize=4096)` on `inspection.ignore_attr_name`.
  - **Impact**: Reduces attribute access overhead to near-zero (**O(1)**) by caching introspection results.

- **Optimized Type Checks**:
  - Changed `_ATOMIC_TYPES` to use a flat `frozenset`.
  - **Impact**: Type membership checks are now O(1). `__setattr__` skips wrapping logic entirely for atomic types (`int`, `str`, `bool`), speeding up simple assignments.

- **Smart Change Detection**:
  - Refined `__setattr__` logic to strictly check `old_value is new_value` before triggering overhead. Reduces unnecessary database dirty-marking by ~40%.

### 🏗️ Architecture & Refactoring

- **Modularization**:
  The monolithic `mixin.py` has been split into focused modules:
  - `sqlatypemodel.mixin.inspection`: Introspection and validation.
  - `sqlatypemodel.mixin.wrapping`: Recursive collection wrapping logic.
  - `sqlatypemodel.mixin.events`: Change signal propagation.
  - `sqlatypemodel.mixin.protocols`: Strict type definitions (`Trackable` protocol).

- **Auto-Registration**:
  - Implemented `__init_subclass__` hook in `BaseMutableMixin`. Models now automatically register with `ModelType` upon inheritance, removing the need for manual setup.

- **Strict Typing**:
  - The codebase is now fully typed (`py.typed` marker included).
  - Protocol definitions updated to match implementation signatures exactly.

### 🐛 Bug Fixes

- **Attrs Compatibility**: Fixed a crash when initializing `attrs` classes with `eq=True`. The library now safely handles identity-based hashing restoration preventing recursion loops.
- **Constants Definition**: Fixed a syntax error where `_ATOMIC_TYPES` was defined as a tuple containing a set, breaking `isinstance` checks.
- **IDE Introspection**: Removed `if not TYPE_CHECKING` guards from `__init__` methods to restore autocomplete and argument hints in IDEs (VS Code, PyCharm).
- **Circular Imports**: Resolved circular dependencies between `model_type` and `mixin` using protocols.
- **Recursion Safety**: Fixed a potential infinite loop in `process_result_value` by ensuring the `_seen` set is passed correctly during tracking restoration.

### 🧪 Testing

- **Architecture**: Migrated entire test suite from `unittest` to native **Pytest**.
- **Fixtures**: Added `conftest.py` with centralized `Session` and `Engine` (in-memory SQLite) fixtures.
- **New Suites**:
  - `test_benchmark_mixins.py`: Performance regression testing using `pytest-benchmark`.
  - `test_custom_types.py`: Explicit compatibility tests for Attrs, Dataclasses, and Plain classes.
  - `test_lazy.py`: Verification of JIT wrapping behavior.

### 📦 Migration Guide

**Non-Breaking**: This release is backward compatible with v0.6.x.

**Recommendations**:
1. **Read-Heavy Workloads**: Switch models to inherit from `LazyMutableMixin` for immediate performance gains.
2. **Attrs Users**: Update imports to use `from sqlatypemodel.util.attrs import define` to ensure safe defaults.
3. **Engine Config**: Use `from sqlatypemodel.util.sqlalchemy import create_engine` to get free `orjson` serialization performance.

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