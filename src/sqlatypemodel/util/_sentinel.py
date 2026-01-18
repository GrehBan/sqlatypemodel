from __future__ import annotations

"""Sentinel values for state tracking."""


class _MissingSentinel:
    def __repr__(self) -> str:
        return "MISSING"

    def __bool__(self) -> bool:
        return False


MISSING = _MissingSentinel()
DELETED = _MissingSentinel()
