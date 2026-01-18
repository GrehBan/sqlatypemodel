Installation
============

You can install ``sqlatypemodel`` via pip:

.. code-block:: bash

    pip install sqlatypemodel

To ensure you have high-performance dependencies like ``orjson`` (recommended):

.. code-block:: bash

    pip install sqlatypemodel[fast]

With Development Dependencies
------------------------------

For development, clone the repository and install with all dependencies:

.. code-block:: bash

    git clone https://github.com/GrehBan/sqlatypemodel.git
    cd sqlatypemodel
    pip install poetry
    poetry install --all-extras

Or without Poetry:

.. code-block:: bash

    pip install -e ".[dev,docs,fast]"

Requirements
------------

*   **Python**: 3.10, 3.11, 3.12, 3.13, 3.14
*   **SQLAlchemy**: 2.0+
*   **Pydantic**: v2 (optional, but recommended)
*   **Dataclasses**: Built-in (3.7+)
*   **Attrs**: (optional) For using with attrs models
*   **orjson**: (Optional but Recommended) For fast serialization

Optional Dependencies
---------------------

.. code-block:: bash

    # For performance (orjson)
    pip install sqlatypemodel[fast]

    # For development
    pip install sqlatypemodel[dev]

    # For documentation building
    pip install sqlatypemodel[docs]

    # For all extras
    pip install sqlatypemodel[all]

Supported Databases
--------------------

SQLAlchemy supports multiple databases. sqlatypemodel works with:

*   **PostgreSQL** 9.6+
*   **MySQL** 5.7+ / MariaDB 10.3+
*   **SQLite** 3.8+
*   **Oracle** 11.2+
*   Any other SQLAlchemy-supported database

Integration with CI/CD
----------------------

sqlatypemodel is tested on every commit with:

*   GitHub Actions (5 Python versions)
*   Multiple databases (PostgreSQL, MySQL)
*   Full test coverage
*   Security scanning
*   Type checking (MyPy strict)

See `.github/WORKFLOWS.md <https://github.com/GrehBan/sqlatypemodel/blob/master/.github/WORKFLOWS.md>`_ for details.
