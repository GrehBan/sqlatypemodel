from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from weakref import WeakKeyDictionary

from sqlatypemodel.mixin import events

__all__ = ("Trackable",)


@runtime_checkable
class Trackable(Protocol):
    """Protocol describing a MutableMixin instance.

    This protocol defines the interface required for objects that support
    change tracking within the library.
    """

    _max_nesting_depth: int
    _change_suppress_level: int
    _pending_change: bool

    @property
    def _parents(self) -> WeakKeyDictionary[Any, Any]: ...
    
    def changed(self) -> None:
        """Mark the object as changed and propagate the notification."""
        ...

    def _restore_tracking(self, _seen: Any | None = None) -> None:
        """Restore change tracking mechanisms (e.g., after unpickling).

        Args:
            _seen: A dictionary mapping id(original) -> wrapped_instance for cycle detection.
        """
        ...


class MutableMethods:
    @property
    def _parents(self) -> WeakKeyDictionary[Any, Any]:
        """Retrieve or initialize the parents WeakKeyDictionary."""

        try:
            return object.__getattribute__(self, "_parents_store")
        except AttributeError:
            val = WeakKeyDictionary()
            object.__setattr__(self, "_parents_store", val)
        return val

    def changed(self) -> None:
        """Notify parents using the library's safe propagation logic."""
        events.safe_changed(self)
