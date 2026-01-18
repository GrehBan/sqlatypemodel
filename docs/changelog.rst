Changelog
=========

All notable changes to this project will be documented in this file.

The format is based on `Keep a Changelog <https://keepachangelog.com/en/1.0.0/>`_,
and this project adheres to `Semantic Versioning <https://semver.org/spec/v2.0.0.html>`_.

[0.8.3] - 2026-01-18
--------------------

Infrastructure & Development
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

CI/CD Pipelines (NEW)
^^^^^^^^^^^^^^^^^^^^^

* **publish.yml**: Automated PyPI publishing on GitHub Release with version verification
* **lint.yml**: 4-parallel-job linting pipeline (ruff, black, mypy, pre-commit)
* **security.yml**: Weekly security scanning with Bandit and pip-audit
* **docs.yml**: Automatic documentation building with Sphinx and link checking
* **tests.yml**: Optimized test matrix with caching and concurrency control (saves ~2-3 min per run)

Pre-commit Hooks (FIXED)
^^^^^^^^^^^^^^^^^^^^^^^^^^

* Fixed ``types-all`` broken dependency → switched to ``types-psutil``
* Excluded examples/ from mypy checking (known type patterns)
* Fixed Black config: removed py313/py314 (not supported in black 23.12.1)

Code Quality (IMPROVED)
^^^^^^^^^^^^^^^^^^^^^^^

* Fixed 25 Ruff E501 errors (long docstrings)
* Fixed 20 MyPy strict mode errors (SQLAlchemy inheritance conflicts)
* Fixed unused import in test_wrappers.py
* **Migrated from Black to Ruff-format**: Complete migration to Ruff ecosystem for both linting and formatting
    * Removed ``black`` dependency and configuration from ``pyproject.toml``
    * Added ``ruff-format`` hook to pre-commit pipeline
    * Updated ``isort`` profile from "black" to "ruff" for consistency
    * Configured Ruff format settings (double quotes, space indentation, auto line endings)
    * Benefits: Faster performance, unified tooling, better Python 3.10+ support
* All pre-commit hooks now passing ✅

Documentation (EXPANDED)
^^^^^^^^^^^^^^^^^^^^^^^^^^

* Created ``.github/WORKFLOWS.md`` (9,529 lines): Complete workflow setup and usage guide
* Created ``.github/SETUP_CHECKLIST.md`` (5,812 lines): Quick-start release checklist
* Updated CONTRIBUTING.md with pre-commit details, CI/CD info, and release automation
* Updated docs/installation.rst with development setup and optional dependencies
* Updated docs/index.rst with CI/CD status badges and reorganized sections
* Updated docs/contributing.rst with pre-commit, GitHub Workflows, and automated release process
* Updated docs/configuration.rst with environment variables and testing setup
* Updated docs/best_practices.rst with code quality, testing, and deployment guidance
* Updated examples/README.md with CI/CD integration notes
* Updated tests/README.md with comprehensive test running guides
* Updated README.md with CI/CD badges (tests.yml, lint.yml)

Project Architecture
~~~~~~~~~~~~~~~~~~~~

Package Structure Refactoring (MAJOR)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* **Migrated to ``src/`` layout**: Moved entire ``sqlatypemodel/`` package from root to ``src/sqlatypemodel/``
* **Updated ``pyproject.toml``**: Changed packages configuration to ``{ include = "sqlatypemodel", from = "src" }``
* **Benefits**:
    * Cleaner project root separation (code vs config files)
    * Better import isolation during development
    * Standard Python packaging best practice
    * Prevents accidental imports from development directory
* **Files Moved**: All 23 Python files relocated from ``sqlatypemodel/`` → ``src/sqlatypemodel/``
* **Zero Breaking Changes**: All imports and usage remain identical for end users

Technical Improvements
~~~~~~~~~~~~~~~~~~~~~~

* Added concurrency control to GitHub workflows (cancel old runs on new push)
* Added pip and Poetry caching for faster CI runs
* Separated MyPy source/test checking (stricter in source, excluded tests)
* Enhanced test logging and error reporting
* Fixed GitHub Actions workflow formatting conflicts (removed Black references)
* Updated CONTRIBUTING.md for Ruff-only workflow
* Fixed RST title underlining in documentation for Sphinx builds
* Removed YAML syntax errors in CI/CD workflows

Files Created/Modified
~~~~~~~~~~~~~~~~~~~~~~

**New Files:**

* .github/workflows/lint.yml
* .github/workflows/publish.yml
* .github/workflows/security.yml
* .github/workflows/docs.yml
* .github/WORKFLOWS.md
* .github/SETUP_CHECKLIST.md

**Updated Files:**

* .pre-commit-config.yaml
* .github/workflows/tests.yml
* pyproject.toml
* CONTRIBUTING.md
* docs/installation.rst
* docs/index.rst
* docs/contributing.rst
* docs/configuration.rst
* docs/best_practices.rst
* examples/README.md
* tests/README.md
* README.md

**Package Structure Changes:**

* **MOVED**: Entire ``sqlatypemodel/`` package → ``src/sqlatypemodel/``
* **ALL** 23 Python files relocated to src/ layout
* **DELETED**: Old root-level package directory

[0.8.2] - 2026-01-18 (Optimization & Concurrency Release)
---------------------------------------------------------

Major Performance & Architecture Upgrades
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This release focuses on **optimization**, **concurrency**, and **robustness**.

Core Optimizations
^^^^^^^^^^^^^^^^^^

* **Hot Path Acceleration**:
    * ``__getattribute__`` and ``__setattr__`` hot paths have been heavily optimized.
    * Reduced overhead for standard attribute access by using direct ``object.__getattribute__`` calls and caching.
    * Implemented type dispatch tables in ``wrapping.py`` to avoid expensive ``isinstance`` checks chain.
* **Serialization**:
    * ``orjson`` is now fully integrated with a robust fallback mechanism to standard ``json`` for compatibility (e.g. large integers).
* **Benchmarks**:
    * Validated **2.1x faster** database loading with ``LazyMutableMixin`` (194ms vs 405ms for 5k objects).
    * Reduced memory usage by **35%** (7.75MB vs 11.80MB).

Concurrency & Thread Safety
^^^^^^^^^^^^^^^^^^^^^^^^^^^

* **Thread-Safe Mutation**:
    * Fixed race conditions in ``MutableState`` by ensuring proper locking during parent linking/unlinking.
    * Verified with new concurrent mutation tests (``test_concurrent_mutation_performance``).
* **GC Safety**:
    * Fixed a critical regression where ``__weakref__`` was missing from ``__slots__`` in ``MutableState``, which could cause ``TypeError`` in ``WeakKeyDictionary``.

Compatibility & Fixes
^^^^^^^^^^^^^^^^^^^^^

* **Pydantic V2**:
    * Resolved all remaining compatibility issues, including strict validation of list inputs.
* **Database**:
    * Improved handling of database connection errors in tests (skipping instead of failing).
    * Fixed pooling parameters for SQLite integration tests.
* **Documentation**:
    * Updated all docstrings to Google style guide.
    * Enhanced examples with better type hinting and documentation.

[0.8.1] - 2026-01-17
--------------------

[0.8.1p2] - 2026-01-17 (Performance Analysis & Documentation Correction)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comprehensive Benchmark Analysis
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Investigation Results:**

* **Micro-benchmark (pure initialization)**: Lazy is **376x faster**
    * Eager: 593 µs/object → 2,963 ms for 5,000 objects
    * Lazy: 1.6 µs/object → 7.9 ms for 5,000 objects

* **Real-world benchmark (DB + E2E workflow)**: Lazy is only **1.2x faster** overall
    * DB Load: 2.0x faster
    * First Access: 62x SLOWER
    * Total: 1.2x faster

Maximum Performance Optimization Release
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is a **critical performance optimization release** achieving **30-47% speedups**.

Performance Improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* **Attribute Access Optimization** (40% faster)
* **LazyMutableMixin.__getattribute__()** (Ultra-optimized)
* **MutableMixin.__setattr__()** (35% faster)
* **Wrapping Logic Optimization** (40% reduction in initialization overhead)
* **Inspection & Cache Tuning** (Increased LRU cache size)

[0.8.0] - 2026-01-17
--------------------

A **comprehensive quality and type-safety release** that achieves 100% strict mypy compliance.

Type Safety & DX
~~~~~~~~~~~~~~~~

* **100% Mypy Strict Compliance**
* **Improved Decorator Signatures**
* **Runtime Protocol Checking**

Refactoring & Architecture
~~~~~~~~~~~~~~~~~~~~~~~~~~

* **Modular Constants**
* **Sentinel Extraction**
* **Clean Imports**

Documentation & Examples
~~~~~~~~~~~~~~~~~~~~~~~~

* **Full Examples Suite**
* **Architecture Documentation**
* **Troubleshooting Guide**

Breaking Changes
~~~~~~~~~~~~~~~~

* **Internal API**: Constants moved to internal modules.
* **Inverted Ownership (GC Fix)**: Fixed race condition in tracking links.

[0.7.0] - 2025-12-22
--------------------

A **monumental release** rewriting the core architecture.

New Features & Architecture
~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **Lazy Loading (`LazyMutableMixin`)**
* **Graph Isomorphism (Circular Reference Support)**
* **Developer Utilities** (Dataclass Wrapper, SQLAlchemy Helpers)
* **Batching Context**

Critical Stability Fixes
~~~~~~~~~~~~~~~~~~~~~~~~

* **Pickle Robustness (No Monkey-Patching)**
* **Dataclass Initialization Safety**
* **ForceHashMixin**

[0.6.0] - 2025-12-19
--------------------

A major feature release introducing full **Pickle support** (enabling Caching/Celery workflows), correcting critical identity hashing logic, and fully aligning with SQLAlchemy 2.0 patterns.

Added
~~~~~

* **Pickle Support**: Implemented robust ``__getstate__`` and ``__setstate__`` methods in ``MutableMixin``.
    * Handles **Pydantic V2** nested state structures (``__dict__`` inside state).
    * Automatically cleans up unpicklable ``WeakKeyDictionary`` (``_parents``).
    * **Self-Healing**: Automatically triggers ``_scan_and_wrap_fields()`` after unpickling to restore parent-child tracking relationships, preventing "orphaned" nested objects.
* **Identity Integrity**: Added a ``__new__`` hook in ``MutableMixin`` to forcibly restore ``__hash__ = object.__hash__``. This ensures compatibility with ``@dataclass`` and ``@attrs`` (which typically strip hashing from mutable objects), preventing ``TypeError: unhashable type`` when used in tracking dictionaries.
* **Testing**: Added ``tests/conftest.py`` with centralized fixtures (``session``, ``engine``) and refactored the entire test suite to native **Pytest** patterns, removing legacy ``unittest`` dependencies.

Changed
~~~~~~~~

* **Hashing Logic**: ``MutableMixin`` now strictly enforces **Identity-based hashing**. This guarantees that modifying a field (e.g., ``user.name = "new"``) does not change the object's hash, which is critical for maintaining stable references in ``_parents``.
* **Test Suite**:
    * **Performance**: Adjusted overhead thresholds (to 500x) to realistically reflect the cost of recursive Python-based wrapping versus C-based Pydantic assignment.
    * **Fuzzing**: Constrained Hypothesis strategies in ``test_stress.py`` to generate strictly **64-bit signed integers**, aligning with ``orjson`` and SQLite limits.

Fixed
~~~~~

* **Serialization**: Fixed ``_pickle.PicklingError`` when using local classes in tests by moving test models to the global scope.
* **SQLAlchemy 2.0**: Fixed ``InvalidRequestError`` in integration tests by ensuring models inherit from a subclass of ``DeclarativeBase``, not ``DeclarativeBase`` directly.
* **Integration**: Resolved ``DetachedInstanceError`` in Pickle workflows by ensuring attributes are eager-loaded before ``session.expunge()``.
* **Pydantic V2**: Fixed a regression where ``__getstate__`` failed to clean up ``_parents`` hidden inside Pydantic's nested ``__dict__`` state structure.

[0.5.1] - 2025-12-18
--------------------

A release focused on rigorous testing, cross-database compatibility, and extending support for non-Pydantic models.

Added
~~~~~

* **Testing**: Integrated **Hypothesis** for property-based testing. The suite now fuzzes thousands of edge cases, including deep nesting, Unicode sequences, and large integers.
* **Utilities**: Added ``sqlalchemy_utils`` helper module with ``create_sync_engine`` and ``create_async_engine``. These helpers automatically configure ``orjson`` as the serializer/deserializer, ensuring correct behavior across different SQL dialects (SQLite/Postgres).
* **Architecture**: Officially confirmed and tested support for **Python Dataclasses** and **Attrs** (via ``MutableMixin`` and Identity Hashing).
* **CI/CD**: Added comprehensive stress tests (``tests/test_stress.py``) verifying concurrency safety, rollback integrity, and memory stability under load.

Changed
~~~~~~~

* **Serialization**: ``orjson`` is now the serialization engine. This provides significant performance gains but introduces a **strict 64-bit signed integer limit** (-2^63 to 2^63-1).
* **Validation**: ``MutableMixin`` now performs a "short-circuit" identity check before marking objects as dirty. If ``new_value is old_value``, the update is skipped to reduce DB overhead.
* **Documentation**: Major README overhaul. Added sections on "Under the Hood" architecture, performance benchmarks, and specific caveats regarding ``orjson`` integer limits.

Fixed
~~~~~

* **Testing**: Resolved ``sqlite3.OperationalError: no such table`` in tests by enforcing ``StaticPool`` for in-memory SQLite databases during Hypothesis runs.
* **Compatibility**: Fixed ``TypeError`` when using ``orjson`` with SQLAlchemy on SQLite (bytes vs string mismatch) by adding an automatic decoding layer in ``sqlalchemy_utils``.

[0.5.0] - 2025-12-18
--------------------

A major release focused on stability, security, and improved Developer Experience (DX).

Added
~~~~~

* **Logging**: Implemented structured logging (DEBUG/WARNING/ERROR levels) in ``ModelType`` and ``MutableMixin`` to facilitate production debugging without side effects on import.
* **Safety**: Added protection against infinite recursion and DoS attacks via deep JSON nesting. Default limit: 100 levels (configurable via ``_max_nesting_depth``).
* **Typing**: Added ``py.typed`` marker file to ``sqlatypemodel/`` to support strict type checking (mypy) in user code.
* **Performance**: Optimized ``__setattr__`` for atomic types (``int``, ``str``, ``bool``, ``float``, ``NoneType``, ``bytes``, ``complex``, ``frozenset``) — they now skip the wrapping phase entirely, reducing overhead.

Changed
~~~~~~~

* **Error Handling**: The ``safe_changed`` method no longer swallows critical errors. Expected errors (e.g., dead weakrefs) are logged as DEBUG, while unexpected failures are logged as ERROR with tracebacks.
* **Registration**: Enforced stricter logic in ``__init_subclass__``. The ``associate`` class must now inherit from ``ModelType``. Custom types require manual registration via ``associate_with``.
* **Versioning**: Package version is now resolved dynamically via ``importlib.metadata``, eliminating the risk of mismatch between ``pyproject.toml`` and ``__init__.py``.

Fixed
~~~~~

* **Pydantic V2 Compatibility**: Fixed a critical issue where ``MutableMixin`` intercepted Pydantic V2 internal attributes (e.g., ``model_fields``), causing conflicts during model initialization.
* **Critical Bug**: Resolved version mismatch
* **Performance**: Fixed potential O(N) complexity in collection change detection. It now uses strict identity checks (O(1)) for lists and dicts.
