from __future__ import annotations

from typing import Protocol, runtime_checkable
from weakref import WeakKeyDictionary

__all__ = ("Trackable",)


@runtime_checkable
class Trackable(Protocol):
    """Protocol describing a MutableMixin instance.

    This protocol defines the interface required for objects that support
    change tracking within the library.
    """

    _parents: WeakKeyDictionary
    _max_nesting_depth: int
    _change_suppress_level: int
    _pending_change: bool

    def changed(self) -> None:
        """Mark the object as changed and propagate the notification."""
        ...

    def _restore_tracking(self, _seen: set[int] | None = None) -> None:
        """Restore change tracking mechanisms (e.g., after unpickling).

        Args:
            _seen: A set of object IDs already processed to prevent recursion.
        """
        ...