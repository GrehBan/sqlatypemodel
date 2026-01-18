"""Static constants and configuration for the library."""

from __future__ import annotations

from typing import Final

from ._sentinel import MISSING

DEFAULT_MAX_NESTING_DEPTH: Final[int] = 100

__all__ = (
    "MISSING",
    "DEFAULT_MAX_NESTING_DEPTH",
)
