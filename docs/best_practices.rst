Best Practices
==============

To get the most out of ``sqlatypemodel``, follow these guidelines.

Performance
-----------

1.  **Choose the Right Mixin**:
    *   Use ``LazyMutableMixin`` for large documents where you only access a few fields. It's significantly faster to load from the DB (5.1x faster initialization).
    *   Use ``MutableMixin`` for small documents or when you iterate over the entire object graph anyway.

2.  **Use Uniform Collections**:
    *   Avoid lists with mixed types (e.g., ``[1, "a", Model()]``). While supported, it forces the lazy loader to inspect every item individually, slowing down access.
    *   Prefer typed Pydantic fields: ``tags: list[str]``.

3.  **Batch Mutations**:
    *   If adding many items to a list in a loop, use ``batch_changes()`` to avoid notifying SQLAlchemy on every iteration.

    .. code-block:: python

        with model.batch_changes():
            for i in range(1000):
                model.items.append(i)

4.  **Leverage orjson**:
    *   Always install with ``pip install sqlatypemodel[fast]`` for maximum performance.
    *   orjson is significantly faster than standard json for serialization/deserialization.

Safety
------

1.  **Use Safe Wrappers for Dataclasses**:
    *   Standard ``dataclasses`` on Python 3.12+ can have initialization issues with mutable defaults.
    *   Use ``sqlatypemodel.util.dataclasses.dataclass`` instead.

2.  **Avoid Shared References**:
    *   Don't share the same mutable list object between two different models.
    *   The library's tracking graph assumes a tree structure (parent -> child).
    *   Shared children ("diamond dependencies") are supported via multiple parents logic, but can be confusing.

3.  **Concurrency**:
    *   While the library handles internal state thread-safety, SQLAlchemy Sessions are not thread-safe.
    *   Keep session scope local to the thread/task.

4.  **Pre-commit Hooks**:
    *   Always run pre-commit before pushing: ``pre-commit run --all-files``
    *   This ensures code quality and prevents CI failures.

Serialization
--------------

1.  **Use `orjson`**:
    *   Install with ``pip install sqlatypemodel[fast]``. It handles serialization much faster than the standard library.
    *   ~40% performance improvement over standard json.

2.  **Watch Integer Limits**:
    *   If your application deals with integers larger than 64-bit (e.g., crypto IDs), be aware that ``orjson`` might fail.
    *   The library handles this by falling back to standard ``json``, but it's a performance hit.

3.  **Pickle Support**:
    *   Full pickle compatibility for Celery/Redis caching.
    *   Mutation tracking is automatically restored upon deserialization.

Testing
-------

1.  **Run Local Tests**:
    *   Always run tests locally before pushing: ``poetry run pytest -v``
    *   Coverage should stay at 100%: ``poetry run pytest --cov=sqlatypemodel``

2.  **Use Database Tests**:
    *   Set up local PostgreSQL/MySQL for database integration tests.
    *   Tests automatically skip if databases unavailable.

3.  **CI/CD Coverage**:
    *   The GitHub Actions workflow tests on Python 3.10-3.14 automatically.
    *   All tests must pass before merge to master.

Code Quality
------------

1.  **Type Hints**:
    *   Always include type hints in new code.
    *   MyPy strict mode is enforced: ``poetry run mypy src/sqlatypemodel``

2.  **Follow Code Style**:
    *   Black + Ruff are enforced: ``poetry run ruff check --fix && poetry run black``
    *   Line length: 79 characters
    *   No bare excepts, unused imports, or undefined names

3.  **Documentation**:
    *   Docstrings for all public APIs
    *   Include examples for complex functions
    *   Update RST docs for major features

4.  **Logging**:
    *   Use Python's standard ``logging`` module
    *   Include context for debugging
    *   Avoid excessive logging in performance-critical paths

Deployment
----------

1.  **Automated Releases**:
    *   Releases are automated via GitHub Actions (see `.github/WORKFLOWS.md`).
    *   Just tag a release and it publishes to PyPI automatically.

2.  **Version Bumping**:
    *   Update ``pyproject.toml`` and ``CHANGELOG.md``
    *   Use semantic versioning (MAJOR.MINOR.PATCH)
    *   Tag with ``git tag v1.2.3``

3.  **Monitoring**:
    *   Check CI/CD status: https://github.com/GrehBan/sqlatypemodel/actions
    *   Security scans run weekly
    *   Coverage tracked automatically
