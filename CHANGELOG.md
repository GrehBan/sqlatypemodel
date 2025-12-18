# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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