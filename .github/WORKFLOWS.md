# GitHub Workflows & PyPI Publishing Guide

This document describes the GitHub workflows configured for the sqlatypemodel project and how to set up automatic PyPI publishing.

## Workflows Overview

### 1. **tests.yml** - Comprehensive Testing
- **Trigger**: Push to `master`/`main`/`develop`, Pull Requests, Manual
- **Features**:
  - Tests on Python 3.10, 3.11, 3.12, 3.13, 3.14
  - PostgreSQL 15 and MySQL 8.0 services
  - Dependency caching for faster builds
  - Concurrent job cancellation (prevents redundant runs)
  - Code coverage reporting to Codecov
  - Linting (ruff), formatting (black), type checking (mypy)
- **Duration**: ~5-10 minutes per Python version
- **Status badge**: [![Tests](https://github.com/GrehBan/sqlatypemodel/actions/workflows/tests.yml/badge.svg)](https://github.com/GrehBan/sqlatypemodel/actions/workflows/tests.yml)

### 2. **lint.yml** - Code Quality Checks
- **Trigger**: Push to `master`/`main`/`develop`, Pull Requests, Manual
- **Features**:
  - Parallel linting jobs (ruff, black, mypy, pre-commit)
  - Fast feedback on code quality issues
  - Separate jobs for easier debugging
- **Duration**: ~3-5 minutes
- **Benefits**: Catches style/type issues before tests run

### 3. **publish.yml** - Automated PyPI Publishing
- **Trigger**: GitHub Release published, Manual workflow dispatch
- **Features**:
  - Builds distribution package (wheel + source)
  - Verifies version matches git tag
  - Publishes to TestPyPI (staging environment)
  - Publishes to PyPI (production)
  - Attaches build artifacts to GitHub Release
  - Supports manual dispatch for flexibility
- **Duration**: ~2-3 minutes
- **Security**: Uses GitHub Environments & branch protection

### 4. **security.yml** - Security & Dependency Analysis
- **Trigger**: Weekly schedule (Monday 9 AM UTC), Manual, Changes to dependencies
- **Features**:
  - Bandit security scanning
  - pip-audit vulnerability detection
  - Python version compatibility verification
  - Dependency analysis
- **Duration**: ~5-10 minutes
- **Frequency**: Automated weekly + on-demand

### 5. **docs.yml** - Documentation Building
- **Trigger**: Changes to docs, README, or CHANGELOG
- **Features**:
  - Builds Sphinx HTML documentation
  - Link checking with lychee
  - Documentation warnings detection
  - Artifacts uploaded for review
- **Duration**: ~3-5 minutes
- **Output**: `sphinx-documentation` artifact

---

## Setup Instructions

### Prerequisites

You need the following secrets configured in GitHub:

1. **`PYPI_API_TOKEN`** - PyPI production token
2. **`TEST_PYPI_API_TOKEN`** - TestPyPI staging token (optional)
3. **`CODECOV_TOKEN`** - Codecov integration token

### Step 1: Create PyPI API Tokens

#### For Production PyPI:
1. Go to https://pypi.org/account/
2. Create a new API token (full access or project-scoped)
3. Copy the token

#### For TestPyPI (recommended for staging):
1. Go to https://test.pypi.org/account/
2. Create a new API token
3. Copy the token

### Step 2: Add Secrets to GitHub

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Add secrets:
   - Name: `PYPI_API_TOKEN`, Value: `pypi-AgEIcHlwaS5vcmc...` (from PyPI)
   - Name: `TEST_PYPI_API_TOKEN`, Value: `pypi-AgEIdGVzdC5weXBp...` (from TestPyPI)
   - Name: `CODECOV_TOKEN`, Value: (from codecov.io)

### Step 3: Set Up Environments (Recommended)

1. Go to **Settings** → **Environments**
2. Create environment: **pypi**
   - Deployment branches: `main`, `master`
   - Reviewers: (optional, for approval)
3. Create environment: **testpypi** (optional)
   - Deployment branches: `develop`
   - No reviewers needed

### Step 4: Configure Branch Protection

1. Go to **Settings** → **Branches** → **Add rule** for `main`
2. Enable:
   - Require status checks to pass before merging
   - Require branches to be up to date
   - Select required checks (Tests, Lint, Type checks)
3. Repeat for other protected branches

---

## Publishing Workflow

### Automatic Publishing (Recommended)

1. **Create Release Tag**:
   ```bash
   git tag v0.8.2
   git push origin v0.8.2
   ```

2. **Create GitHub Release**:
   - Go to **Releases** → **Draft a new release**
   - Select the tag you created
   - Add release notes
   - Check "Set as latest release"
   - Click **Publish release**

3. **Automatic PyPI Publishing**:
   - `publish.yml` workflow triggers automatically
   - Verifies version matches tag
   - Builds distribution package
   - Publishes to PyPI
   - Attaches artifacts to release

### Manual Publishing (For Testing)

1. Go to **Actions** → **Publish to PyPI**
2. Click **Run workflow**
3. Choose environment:
   - `testpypi`: Publishes to test.pypi.org
   - `pypi`: Publishes to pypi.org (production)
4. Workflow executes immediately

---

## CI/CD Pipeline Flow

```
┌─────────────────────┐
│  Push to branch     │
└──────────┬──────────┘
           │
           ├──→ [Tests] → Coverage → Report to Codecov
           │
           ├──→ [Lint] → Ruff, Black, MyPy, Pre-commit
           │
           └──→ [Security] → Bandit, pip-audit (on changes)

┌─────────────────────┐
│  Create Release     │ (Manual)
└──────────┬──────────┘
           │
           ├──→ [Build] → Create wheel + source dist
           │
           ├──→ [Test PyPI] (optional) → Test installation
           │
           └──→ [Publish] → PyPI production
                 └──→ Attach artifacts to release
```

---

## Version Management

### Updating Version

1. **Update `pyproject.toml`**:
   ```toml
   [project]
   version = "0.8.3"
   ```

2. **Update `CHANGELOG.md`**:
   ```markdown
   ## [0.8.3] - 2026-01-18

   ### Added
   - New feature X
   - New feature Y

   ### Fixed
   - Bug fix A
   - Bug fix B
   ```

3. **Commit and tag**:
   ```bash
   git add pyproject.toml CHANGELOG.md
   git commit -m "chore: bump version to 0.8.3"
   git tag v0.8.3
   git push origin main v0.8.3
   ```

4. **Create release** on GitHub and publishing triggers automatically

### Version Requirements

- `pyproject.toml` version must match git tag (with optional `v` prefix)
- Example matches:
  - Tag: `v0.8.3`, Version: `0.8.3` ✓
  - Tag: `0.8.3`, Version: `0.8.3` ✓
  - Tag: `v0.8.3`, Version: `0.8.2` ✗ (will fail)

---

## Troubleshooting

### Publishing Failed: Token Invalid
- **Solution**: Verify `PYPI_API_TOKEN` is correct in GitHub secrets
- Check token hasn't expired on PyPI website
- Ensure token has project-scoped or full permissions

### Publishing Failed: Version Mismatch
- **Solution**: Ensure tag matches `pyproject.toml` version
- Examples:
  - ✓ Tag: `v0.8.3`, version: `0.8.3`
  - ✗ Tag: `v0.8.3`, version: `0.8.2`

### Tests Failed in Workflow
- Run tests locally: `poetry run pytest -v`
- Check Python version compatibility
- Review test logs in GitHub Actions

### Documentation Build Failed
- Verify Sphinx config: `docs/conf.py`
- Check `.rst` files for syntax errors
- Build locally: `cd docs && make html`

---

## Monitoring & Maintenance

### Weekly Tasks
- Monitor security scan results (runs Mondays 9 AM UTC)
- Review Dependabot alerts
- Check codecov.io for coverage trends

### Monthly Tasks
- Review and update dependencies
- Update Python versions if needed
- Audit workflows for efficiency

### Release Process
1. Test locally: `poetry run pytest`
2. Update version and changelog
3. Create git tag
4. Push to GitHub
5. Create GitHub Release
6. Monitor publishing workflow

---

## Best Practices

### Before Releasing

```bash
# 1. Run all tests locally
poetry run pytest -v

# 2. Run linting
poetry run ruff check src/sqlatypemodel tests
poetry run black --check src/sqlatypemodel tests
poetry run mypy src/sqlatypemodel

# 3. Build distribution
poetry build

# 4. Test with TestPyPI (manual workflow dispatch)
# Verify installation works

# 5. Update version and changelog
# git tag and push
```

### After Releasing

- Monitor PyPI package page for proper display
- Test installation: `pip install sqlatypemodel==<version>`
- Verify documentation on readthedocs.io (if configured)
- Announce release on social media/forums

---

## Environment Variables & Secrets

| Secret | Type | Description |
|--------|------|-------------|
| `PYPI_API_TOKEN` | Secret | PyPI production API token |
| `TEST_PYPI_API_TOKEN` | Secret | TestPyPI staging API token |
| `CODECOV_TOKEN` | Secret | Codecov coverage reporting token |

All secrets are masked in workflow logs and available only to authorized runs.

---

## Performance Optimization

### Caching Strategy
- **Poetry cache**: Speeds up dependency installation
- **pip cache**: Reduces package download time
- **Docker layer caching**: Uses alpine images for smaller base

### Concurrency Settings
- Only one test run per branch at a time
- New commits automatically cancel previous runs
- Reduces build queue and saves CI minutes

### Matrix Strategy
- Fail-fast: `false` to run all Python versions even if one fails
- Parallelization: Faster feedback on test results

---

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [PyPI Upload Documentation](https://packaging.python.org/tutorials/packaging-projects/)
- [Poetry Documentation](https://python-poetry.org/docs/)
- [Sphinx Documentation](https://www.sphinx-doc.org/)

---

## Support & Questions

For issues or questions:
1. Check GitHub Actions logs
2. Review this guide
3. Open an issue on the repository
4. Check GitHub Actions community forums

---

**Last Updated**: 2026-01-18
**Workflows Version**: 1.0
**Status**: ✅ Production Ready
