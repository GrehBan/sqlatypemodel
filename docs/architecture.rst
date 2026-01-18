Architecture & Internals
==========================

This document explains the internal design of ``sqlatypemodel``, focusing on how it achieves reliable mutation tracking without performance penalties or compatibility issues.

State-Based Tracking
--------------------

The core innovation of ``sqlatypemodel`` is **State-Based Tracking**.

Legacy Approach (The "Old Way")
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Most SQLAlchemy mutable extensions rely on:
1.  **Identity Hashing**: Requires objects to be hashable and their hash to rely on identity (``id()``). This breaks value-based objects like standard Pydantic models or ``eq=True`` dataclasses.
2.  **Monkey Patching**: Modifying ``__eq__`` or ``__hash__`` at runtime, leading to confusing bugs.

Our Approach (The "State" Way)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We introduce a lightweight, immutable token called ``MutableState``.

.. code-block:: python

    class MutableState(Generic[T]):
        __slots__ = ("ref", "_lock", "__weakref__")
        # ...

1.  **The Parent** (your model) holds a strong reference to its own ``MutableState``.
2.  **Children** (lists, dicts, nested models) hold a **Weak Reference** to the parent's state in a specialized ``_parents`` dictionary.

Graph Structure
~~~~~~~~~~~~~~~

.. code-block:: text

    User Entity (SQLAlchemy Model)
       |
       +-- settings (Pydantic Model) <-- [Strong Ref] -- _state (Token A)
             |
             +-- tags (MutableList)
                   |
                   +-- _parents: { Token A: "tags" }

When ``tags.append("new")`` is called:
1.  The list detects the change.
2.  It iterates over ``_parents``.
3.  It finds ``Token A``.
4.  It resolves ``Token A`` back to the ``UserSettings`` object.
5.  It calls ``UserSettings.changed()``.
6.  The signal bubbles up to the SQLAlchemy Entity.

**Benefits:**
*   **Universal Compatibility**: Works with *any* object, hashable or not.
*   **Garbage Collection Safe**: Weak references prevent circular dependency memory leaks.
*   **Thread Safe**: Internal locking (`RLock`) ensures graph integrity during concurrent mutations.

Lazy Loading & JIT Wrapping
---------------------------

To achieve high performance, ``LazyMutableMixin`` defers initialization.

1.  **Zero-Cost Init**: When loaded from the DB, the object is a standard Pydantic model (or dataclass) holding raw data. No wrappers are created.
2.  **__getattribute__ Hook**: We intercept attribute access.
3.  **JIT Wrapping**:
    *   If you access ``user.settings.tags``, we check if it's already wrapped.
    *   If not, we verify it's a mutable type (list/dict).
    *   We create a ``KeyableMutableList`` wrapper on the fly.
    *   We link it to the parent state.
    *   We cache it for future access.

**Optimization**:
*   **Cold/Hot Paths**: Atomic types (int, str) are returned immediately (Hot Path). Wrappers are only created for mutable collections (Cold Path).
*   **Type Dispatch**: We use a pre-computed dispatch table to avoid long ``isinstance`` chains.

Serialization (orjson)
----------------------

We use ``orjson`` for serialization because it is significantly faster than the standard library.

*   **Dumps**: ``orjson.dumps`` returns bytes. We decode to string for SQLAlchemy compatibility (unless on Postgres which accepts bytes).
*   **Loads**: We support both bytes and strings.
*   **Fallback**: If ``orjson`` fails (e.g., extremely large integers > 64-bit), we transparently fall back to standard ``json``.

Recursion & Safety
------------------

Deeply nested structures can cause recursion errors. We enforce a ``_max_nesting_depth`` (default 100) to prevent StackOverflow errors during traversal.

Circular References
-------------------

The library supports graph isomorphism. If your object graph has cycles (A -> B -> A), the wrapping logic detects this using a ``_seen`` dictionary (tracking object IDs) and reuses existing wrappers instead of entering an infinite loop.

Code Quality & Testing
-----------------------

**Pre-commit Hooks:**
All code is validated via pre-commit hooks before commit:
- Black code formatting (79 char line length)
- Ruff linting (import sorting, error checking)
- MyPy type checking (strict mode)
- File cleanup (trailing whitespace, EOF markers)

**CI/CD Pipelines:**
All code is tested via GitHub Actions:

1. **tests.yml**: Tests on Python 3.10-3.14 with PostgreSQL and MySQL
2. **lint.yml**: Code quality checks (ruff, black, mypy, pre-commit)
3. **security.yml**: Weekly security scanning
4. **docs.yml**: Sphinx documentation building
5. **publish.yml**: Automated PyPI publishing on release

See `.github/WORKFLOWS.md <https://github.com/GrehBan/sqlatypemodel/blob/master/.github/WORKFLOWS.md>`_ for details.

**Test Coverage:**
- 100% coverage on source code
- Unit tests for all core components
- Integration tests with PostgreSQL, MySQL, SQLite
- Performance benchmarks (Lazy vs Eager)
- Concurrency tests (thread safety)
- Property-based tests (Hypothesis)
