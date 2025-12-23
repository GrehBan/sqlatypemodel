# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.0] - 2025-12-23

A **major architectural release** that eliminates the need for hashable models, fixes critical garbage collection race conditions, and achieves 100% strict type safety.

### 🏗️ State-Based Architecture (Major Change)

- **MutableState Token System**:
  - **The Problem**: Previous versions relied on `ForceHashMixin` to make mutable objects (like Pydantic models) hashable for tracking. This was fragile and conflicted with libraries that enforce `eq=True, frozen=False`.
  - **The Solution**: Introduced `MutableState`. Each parent object now holds a unique, immutable identity token (`_state`). Children track their parents via this token in a `WeakKeyDictionary`.
  - **Benefit**: **Zero Monkey-Patching**. You can now use standard unhashable Python objects as parents without `ForceHashMixin`.

- **Inverted Ownership (GC Fix)**:
  - Fixed a critical race condition where tracking links could be garbage-collected prematurely.
  - **Logic**: The **Parent** now strongly holds its own `_state` token. The **Child** holds a weak reference to that token in `_parents`. The link now persists exactly as long as the parent is alive.

- **Thread Safety:** Every MutableState instance includes a `threading.RLock`. This recursive lock protects the link and unlink operations, ensuring that the dependency graph remains consistent even when modified by multiple threads.

### 🛡️ Type Safety & Stability

- **Strict Typing (`mypy --strict`)**:
  - The codebase now passes `mypy --strict` checks.
  - Added generic type parameters to `MutableState[T]` and `ModelType[T]` for better IDE autocompletion and static analysis support.

- **SQLAlchemy Compatibility**:
  - Fixed `AttributeError: 'InstanceState' object has no attribute '_sa_instance_state'` in `safe_changed`. The event propagator now correctly distinguishes between our internal `MutableState` and SQLAlchemy's `InstanceState`.

### 💥 Breaking Changes

- **Removed `ForceHashMixin`**: This mixin has been removed as it is no longer necessary. If your code relied on it for custom hashing, please migrate to standard Python hashing or use the new `MutableState` identity system.
- **Internal API**: `_parents` is now a `WeakKeyDictionary` mapping `MutableState` -> `str` (attribute name), instead of `Parent Object` -> `str`.
- **Renamed** `json_loads` -> `loader` `json_dumps` -> `dumper` in `sqlatypemodel.model_type.ModelType`

## [0.7.0] - 2025-12-22

A **monumental release** rewriting the core architecture. This version introduces **Lazy Loading** (up to 150x faster reads), **Graph Isomorphism** support for circular references, production-grade **Pickle stability**, and robust support for Python Dataclasses on Python 3.12+.

### 🚀 New Features & Architecture

- **Lazy Loading (`LazyMutableMixin`)**:
  - **Zero-cost loading**: Objects loaded from the database remain as raw Python dicts/lists until accessed.
  - **JIT Wrapping**: Mutation tracking wrappers are created on-demand via `__getattribute__`.
  - **Self-Healing**: Automatically restores parent-child tracking links if an object loses them (e.g., after `pickle` restoration or direct `__dict__` manipulation).
  - **Performance**: Loading 5,000 nested objects takes **~7ms** (Lazy) vs **~1100ms** (Eager).

- **Graph Isomorphism (Circular Reference Support)**:
  - **The Problem**: Previously, self-referencing structures (e.g., `l = []; l.append(l)`) caused infinite recursion or returned raw objects during wrapping.
  - **The Solution**: The wrapping logic now uses a `_seen` dictionary (instead of a `_seen` set). It correctly detects cycles and returns the **existing wrapper**, preserving the exact object graph structure.

- **Developer Utilities**:
  - **Dataclass Wrapper** (`sqlatypemodel.util.dataclasses`): Added a safe `@dataclass` wrapper that forces `eq=False` and `slots=False`. This prevents recursion crashes during initialization on Python 3.12+ and ensures compatibility with `MutableMixin`.
  - **SQLAlchemy Helpers** (`sqlatypemodel.util.sqlalchemy`): Added `create_engine` wrappers that auto-configure `orjson` with fallback logic.
  - **Attrs Helper** (`sqlatypemodel.util.attrs`): Added a `define` wrapper enforcing safe defaults (`slots=False`, `eq=False`).

- **Batching Context**:
  - Introduced `batch_changes()` context manager. Suppresses intermediate SQL updates during bulk loops (`for i in range(100): list.append(i)` -> 1 update).

### 🛡️ Critical Stability Fixes

- **Pickle Robustness (No Monkey-Patching)**:
  - **Fix**: Removed runtime monkey-patching of `instance.changed = ...`. This was causing objects to lose tracking capabilities after unpickling (standard `pickle` drops instance methods).
  - **Implementation**: Introduced `MutableMethods` mixin. Notification logic is now part of the class definition (`KeyableMutableList`, etc.), ensuring it survives serialization cycles.

- **Dataclass Initialization Safety (Python 3.12+)**:
  - **Fix**: Resolved `AttributeError` crashes and recursion loops during Dataclass initialization.
  - **Root Cause**: `WeakKeyDictionary` checks equality on insertion. Standard Dataclasses generate value-based `__eq__` which crashes on partially initialized objects and violates the Identity Hashing contract.
  - **Solution**: `ForceHashMixin` now enforces **Identity Equality** (`__eq__ = object.__eq__`) alongside identity hashing.

- **ForceHashMixin**:
  - Ensures mutable objects remain hashable (via `id()`) even if Pydantic/Attrs try to disable `__hash__`. Essential for `WeakKeyDictionary` tracking.

### ⚡ Performance Improvements

- **Introspection Caching**:
  - Added `@lru_cache` to `is_pydantic` and `ignore_attr_name`.
  - **Impact**: Eliminates expensive MRO traversal and `hasattr` checks during deep structure scanning.

- **Optimized Type Checks**:
  - Converted `_ATOMIC_TYPES` to a flat `frozenset`. `__setattr__` now skips wrapping logic entirely for atomic types (int, str, bool) in O(1) time.

- **Smart Change Detection**:
  - `__setattr__` now strictly checks `old_value is new_value` before triggering overhead, reducing unnecessary DB dirty-marking by ~40%.

### 🏗️ Refactoring

- **Modularization**: Split monolithic `mixin.py` into `inspection`, `wrapping`, `events`, and `protocols`.
- **Auto-Registration**: Implemented `__init_subclass__`. Models automatically register with `ModelType` upon inheritance.
- **Strict Typing**: Codebase is fully typed with `py.typed` marker.

### 🧪 Testing

- **Migration to Pytest**: Replaced `unittest` with native Pytest fixtures.
- **New Edge Case Suite**: Added `tests/test_edge_cases.py` covering:
  - Circular dependencies (A -> A).
  - Diamond dependencies (Shared mutable objects).
  - Re-parenting objects between models.
  - Pydantic `model_construct` bypass.

### 📦 Migration Guide

**Non-Breaking**: Backward compatible with v0.6.x.

1. **Lazy Loading**: Switch to `class MyModel(LazyMutableMixin, ...)` for read-heavy apps.
2. **Dataclasses**: Use `from sqlatypemodel.util.dataclasses import dataclass` instead of the standard library to ensure safety.

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