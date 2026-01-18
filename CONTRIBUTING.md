# Contributing to sqlatypemodel

Thank you for your interest in contributing to `sqlatypemodel`! We welcome bug reports, feature requests, and pull requests.

## Development Setup

We use [Poetry](https://python-poetry.org/) for dependency management and packaging with a modern `src/` layout.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/GrehBan/sqlatypemodel.git
    cd sqlatypemodel
    ```

2.  **Install dependencies:**
    ```bash
    poetry install --all-extras
    ```

3.  **Activate virtual environment:**
    ```bash
    poetry shell
    ```

4.  **Verify setup:**
    ```bash
    # Run pre-commit to ensure everything is working
    pre-commit run --all-files

    # Run tests to verify functionality
    poetry run pytest -v
    ```

## Code Quality

We use a strict set of tools to ensure code quality. Please run these before submitting a PR.

### Pre-commit Hooks

We use [pre-commit](https://pre-commit.com/) to automatically run code quality checks:

```bash
# Install pre-commit hooks
pre-commit install

# Run all hooks
pre-commit run --all-files
```

Hooks run automatically on each commit and include:
- **trailing-whitespace**: Fix trailing whitespace
- **end-of-file-fixer**: Ensure files end with newline
- **check-yaml**: Validate YAML files
- **check-toml**: Validate TOML files
- **check-added-large-files**: Prevent large files
- **ruff**: Linting and import sorting
- **ruff-format**: Code formatting
- **mypy**: Type checking (strict mode)

### Linting & Formatting

We use [Ruff](https://github.com/astral-sh/ruff) for both linting and formatting in a unified toolchain.

```bash
# Check for linting issues
poetry run ruff check src/sqlatypemodel tests

# Auto-fix linting issues
poetry run ruff check src/sqlatypemodel tests --fix

# Check formatting (without changing files)
poetry run ruff format --check src/sqlatypemodel tests

# Apply formatting
poetry run ruff format src/sqlatypemodel tests
```

**Note**: Ruff handles both linting and formatting. There's no separate Black step needed.

### Type Checking

We use [Mypy](https://mypy.readthedocs.io/) in strict mode.

```bash
poetry run mypy src/sqlatypemodel
```

### Testing

We use [Pytest](https://docs.pytest.org/).

```bash
# Run all tests
poetry run pytest -v

# Run with coverage
poetry run pytest -v --cov=sqlatypemodel --cov-report=term-missing

# Run specific test file
poetry run pytest tests/unit/test_model_type.py -v

# Run benchmarks
poetry run pytest -v -m benchmark

# Run integration tests (requires PostgreSQL/MySQL)
poetry run pytest -v -m integration
```

*Note: Some integration tests require PostgreSQL or MySQL. You can run them if you set the appropriate environment variables, otherwise they will be skipped.*

## GitHub Workflows

Our CI/CD pipeline is fully automated. See [.github/WORKFLOWS.md](.github/WORKFLOWS.md) for complete information.

**Available Workflows:**
- **tests.yml** - Comprehensive testing on Python 3.10-3.14 with PostgreSQL & MySQL
- **lint.yml** - Code quality checks (ruff, ruff-format, mypy, pre-commit)
- **publish.yml** - Automated PyPI publishing on release ⭐
- **security.yml** - Weekly security scanning (Bandit, pip-audit)
- **docs.yml** - Automatic documentation building

All checks must pass before merging to main branch.

## Pull Request Guidelines

1.  **Fork** the repository and create a feature branch.
2.  **Run pre-commit hooks** locally before committing:
    ```bash
    pre-commit run --all-files
    ```
3.  **Add tests** for your new feature or bug fix.
4.  **Update documentation** if necessary.
5.  **Run all checks** locally:
    ```bash
    # Linting and formatting
    poetry run ruff check src/sqlatypemodel tests --fix
    poetry run ruff format src/sqlatypemodel tests

    # Type checking
    poetry run mypy src/sqlatypemodel

    # Tests
    poetry run pytest -v
    ```
6.  **Submit** the Pull Request with a clear description.

## Release Process

(For maintainers)

See [.github/WORKFLOWS.md](.github/WORKFLOWS.md) for automated release process.

**Manual Release Steps:**
1. Update version in `pyproject.toml` (e.g., `0.8.3`)
2. Update `CHANGELOG.md` with release notes
3. Commit: `git commit -m "chore: bump version to 0.8.3"`
4. Tag: `git tag v0.8.3 && git push origin v0.8.3`
5. Create GitHub Release (UI)
6. ✅ Automated: `publish.yml` workflow triggers
   - Builds distribution package
   - Verifies version matches tag
   - Publishes to PyPI
   - Attaches artifacts to release

**Result:** Package live on PyPI in ~2-3 minutes!

## Code Standards

- **Style**: Ruff (lint + format enforced by pre-commit)
- **Types**: Mypy (strict mode enforced)
- **Imports**: Ruff (with isort integration)
- **Line Length**: 79 characters
- **Python**: 3.10+
- **Tests**: 100% coverage on new code

## Questions or Issues?

- Open an issue on [GitHub](https://github.com/GrehBan/sqlatypemodel/issues)
- Check existing documentation in [docs/](docs/)
- Review [.github/WORKFLOWS.md](.github/WORKFLOWS.md) for CI/CD info

Thank you for contributing! 🎉
