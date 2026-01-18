Contributing
=============

Thank you for your interest in contributing to ``sqlatypemodel``!

Development Setup
-----------------

We use `Poetry <https://python-poetry.org/>`_ for dependency management with a modern ``src/`` layout.

1.  **Clone the repository:**

    .. code-block:: bash

        git clone https://github.com/GrehBan/sqlatypemodel.git
        cd sqlatypemodel

2.  **Install dependencies:**

    .. code-block:: bash

        poetry install --all-extras

3.  **Activate environment:**

    .. code-block:: bash

        poetry shell

4.  **Verify setup:**

    .. code-block:: bash

        # Run pre-commit to ensure everything is working
        pre-commit run --all-files

        # Run tests to verify functionality
        poetry run pytest -v

Code Quality
------------

We enforce strict quality standards using pre-commit hooks and GitHub Actions CI/CD.

Pre-commit Hooks
~~~~~~~~~~~~~~~~

We use `pre-commit <https://pre-commit.com/>`_ to catch issues before commit:

.. code-block:: bash

    # Install pre-commit
    pre-commit install

    # Run all hooks
    pre-commit run --all-files

Hooks include:

- **trailing-whitespace**: Fix trailing whitespace
- **end-of-file-fixer**: Ensure files end with newline
- **check-yaml**: Validate YAML files
- **check-toml**: Validate TOML files
- **check-added-large-files**: Prevent large files
- **ruff**: Linting and import sorting
- **ruff-format**: Code formatting
- **mypy**: Type checking (strict mode)

Linting & Formatting
~~~~~~~~~~~~~~~~~~~~

We use **Ruff** for both linting and formatting in a unified toolchain.

.. code-block:: bash

    # Check for linting issues
    poetry run ruff check src/sqlatypemodel tests

    # Auto-fix linting issues
    poetry run ruff check src/sqlatypemodel tests --fix

    # Check formatting (without changing files)
    poetry run ruff format --check src/sqlatypemodel tests

    # Apply formatting
    poetry run ruff format src/sqlatypemodel tests

**Note**: Ruff handles both linting and formatting. There's no separate Black step needed.

Type Checking
~~~~~~~~~~~~~

We use **MyPy** in strict mode.

.. code-block:: bash

    poetry run mypy src/sqlatypemodel

Testing
-------

We use **Pytest** with comprehensive test coverage.

.. code-block:: bash

    # Run unit tests
    poetry run pytest -v

    # Run with coverage
    poetry run pytest -v --cov=sqlatypemodel --cov-report=term-missing

    # Run specific test
    poetry run pytest tests/unit/test_model_type.py -v

    # Run benchmarks
    poetry run pytest -v -m benchmark

    # Run integration tests (requires PostgreSQL/MySQL)
    poetry run pytest -v -m integration

CI/CD Workflows
---------------

All code is automatically tested and linted via GitHub Actions:

- **tests.yml**: Tests on Python 3.10-3.14 with PostgreSQL and MySQL
- **lint.yml**: Ruff, Ruff-format, MyPy, and pre-commit checks
- **publish.yml**: Automatic PyPI publishing on release
- **security.yml**: Weekly security scanning
- **docs.yml**: Documentation building and link checking

See `.github/WORKFLOWS.md <https://github.com/GrehBan/sqlatypemodel/blob/master/.github/WORKFLOWS.md>`_ for detailed information.

Pull Request Process
--------------------

1.  Fork the repo and create a feature branch from ``master``
2.  Install pre-commit hooks: ``pre-commit install``
3.  Make your changes
4.  Run pre-commit: ``pre-commit run --all-files``
5.  Add tests for new features
6.  Update documentation as needed
7.  Run all checks locally:

    .. code-block:: bash

        poetry run ruff check src/sqlatypemodel tests --fix
        poetry run ruff format src/sqlatypemodel tests
        poetry run mypy src/sqlatypemodel
        poetry run pytest -v

8.  Submit a Pull Request with a clear description
9.  All checks must pass before merge

Release Process
---------------

(For maintainers)

Releases are automated via GitHub Actions. See `.github/WORKFLOWS.md <https://github.com/GrehBan/sqlatypemodel/blob/master/.github/WORKFLOWS.md>`_ for details.

**Quick Release:**

1. Update version in ``pyproject.toml``
2. Update ``CHANGELOG.md``
3. Commit and push: ``git push origin master``
4. Create GitHub Release (UI)
5. ✅ Automated: Package published to PyPI in ~2-3 minutes!

Code Standards
--------------

- **Style**: Ruff (lint + format enforced by pre-commit)
- **Types**: MyPy strict mode
- **Imports**: Ruff with isort integration
- **Line Length**: 79 characters
- **Python**: 3.10+
- **Coverage**: 100% on new code

Getting Help
------------

- Open an issue: https://github.com/GrehBan/sqlatypemodel/issues
- Check documentation: https://github.com/GrehBan/sqlatypemodel/blob/master/docs/
- Review examples: https://github.com/GrehBan/sqlatypemodel/blob/master/examples/

Thank you for contributing! 🎉
