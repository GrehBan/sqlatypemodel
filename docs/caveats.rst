Caveats & Restrictions
======================

While ``sqlatypemodel`` is robust, there are technical limitations you should be aware of.

64-bit Integer Limit
--------------------

The core serialization engine, ``orjson``, adheres to strict 64-bit signed integer limits (`-2^63` to `2^63-1`).

*   **Behavior**: If you try to serialize a Python ``int`` larger than this range (e.g., `2**100`), ``orjson`` will raise an error.
*   **Mitigation**: The library automatically catches this error and falls back to the standard ``json`` module, which is slower but supports arbitrary precision integers.
*   **Impact**: Performance penalty for records containing huge integers.

Mixed Types in Lazy Collections
-------------------------------

``LazyMutableMixin`` uses runtime inspection to decide whether to wrap an item.

*   **Scenario**: ``my_list = [ModelA(), {"key": "val"}, 123]``
*   **Impact**: When iterating this list, the JIT wrapper must inspect the type of *each* item individually.
*   **Recommendation**: For maximum performance, keep collections uniform (e.g., ``List[int]`` or ``List[Model]``).

Thread Safety
-------------

The library's internal state tracking is thread-safe (protected by ``RLock``). However:

*   **SQLAlchemy Sessions are NOT thread-safe**. You should generally not share a session or attached objects across threads.
*   **Conflict Resolution**: If two threads modify the same object attribute concurrently, the last write wins in memory. The database update depends on transaction isolation levels.

SQLAlchemy Dialects
-------------------

*   **PostgreSQL**: Fully supported (uses ``JSONB`` by default).
*   **MySQL**: Fully supported (uses ``JSON``).
*   **SQLite**: Fully supported (stores as JSON string).
*   **Others**: Should work if they support a JSON type, but advanced querying features might vary.

Pydantic V2 "Extra" Fields
--------------------------

If you use `model_config = {"extra": "allow"}`, the extra fields are stored in `__pydantic_extra__`.
``sqlatypemodel`` correctly tracks mutations in these fields, but accessing them might be slightly slower than defined fields due to Pydantic's internal structure.

Pre-commit Hook Requirements
-----------------------------

Before pushing code, ensure all pre-commit hooks pass locally:

.. code-block:: bash

    pre-commit run --all-files

**Common Issues:**
- **Black format errors**: Auto-fixed; run again after fixing
- **MyPy errors**: Must be manually fixed; may require type annotations
- **Ruff errors**: Auto-fixed; run again if issues persist
- **Large files**: Commit won't proceed if file > 5MB

See `CONTRIBUTING.md <https://github.com/GrehBan/sqlatypemodel/blob/master/CONTRIBUTING.md>`_ for details.

Python Version Support
----------------------

Supported: **3.10, 3.11, 3.12, 3.13, 3.14**

*   Older versions (3.9 and below) lack union syntax (`X | Y`), required for type hints
*   Features like `match` (3.10+) and structural pattern matching are used in tests
*   Tested on each version via GitHub Actions

MyPy Strict Mode
----------------

The library is checked with `mypy --strict`:

*   All functions must have type hints
*   No implicit `Any` types allowed
*   Type: ignore comments must specify the error code (e.g., `# type: ignore[misc]`)
*   See `.pre-commit-config.yaml <https://github.com/GrehBan/sqlatypemodel/blob/master/.pre-commit-config.yaml>`_ for configuration
