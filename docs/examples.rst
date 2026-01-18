Examples
========

This directory contains ready-to-run examples demonstrating the key features of ``sqlatypemodel``.

Quick Start
-----------

Install dependencies:

.. code-block:: bash

    poetry install --all-extras
    # OR
    pip install pydantic attrs sqlalchemy aiosqlite orjson

Run any example:

.. code-block:: bash

    python 01_pydantic_basic.py

Available Examples
------------------

1.  **01_pydantic_basic.py**: Basic setup with Pydantic and SQLAlchemy.
2.  **02_lazy_loading.py**: Demonstrates the performance boost of ``LazyMutableMixin``.
3.  **03_dataclasses.py**: Integration with standard Python dataclasses.
4.  **04_attrs.py**: Integration with the ``attrs`` library.
5.  **05_async_sqlalchemy.py**: Usage with SQLAlchemy's ``AsyncSession``.
6.  **06_nested_collections.py**: Tracking deep mutations in lists/dicts.
7.  **07_pickle_celery.py**: Serialization and task queue compatibility.
8.  **comparison_bench.py**: Detailed benchmark script comparing Eager vs Lazy loading performance and memory usage.

Safety & Testing
----------------

All examples use SQLite in-memory databases (no external database setup required).

Examples are tested as part of the CI/CD pipeline. See `.github/WORKFLOWS.md <https://github.com/GrehBan/sqlatypemodel/blob/master/.github/WORKFLOWS.md>`_ for details.

Run examples in tests:

.. code-block:: bash

    poetry run pytest examples/ -v

Performance Benchmarks
----------------------

Run the comparison benchmark locally:

.. code-block:: bash

    python comparison_bench.py

This compares:
- Lazy vs Eager loading speeds
- Memory usage differences
- Initialization performance
- Real-world DB workflow performance
