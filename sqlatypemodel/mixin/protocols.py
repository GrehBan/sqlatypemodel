from __future__ import annotations

from typing import Any, Protocol, TypeVar, cast, runtime_checkable
from weakref import WeakKeyDictionary

from sqlatypemodel.mixin import events
from sqlatypemodel.mixin.state import MutableState

__all__ = ("Trackable", "MutableMethods", "MutableMixinProto")

T = TypeVar("T", bound="Trackable")



@runtime_checkable
class Trackable(Protocol):
    """Protocol describing a trackable object.

    This protocol defines the interface required for objects that support
    change tracking within the library.
    """

    @property
    def _parents(self: T) -> WeakKeyDictionary[MutableState[T], Any]: ...

    def changed(self) -> None:
        """Mark the object as changed and propagate the notification."""
        ...


@runtime_checkable
class MutableMixinProto(Trackable, Protocol):
    """Protocol describing a MutableMixin instance.

    This protocol defines the interface required for objects that support
    change tracking within the library.
    """

    _max_nesting_depth: int
    _change_suppress_level: int
    _pending_change: bool

    @property
    def _state(self: T) -> MutableState[T]: ...

    def _restore_tracking(self, _seen: Any | None = None) -> None:
        """Restore change tracking mechanisms (e.g., after unpickling).

        Args:
            _seen: A dictionary mapping id(original) -> wrapped_instance for cycle detection.
        """
        ...


class MutableMethods:
    @property
    def _parents(self) -> WeakKeyDictionary[MutableState[Any], Any]:
        """Retrieve or initialize the parents WeakKeyDictionary."""

        try:
            return cast(
                "WeakKeyDictionary[MutableState[Any], Any]",
                object.__getattribute__(self, "_parents_store")
            )
        except AttributeError:
            val: WeakKeyDictionary[MutableState[Any], Any] = WeakKeyDictionary()
            object.__setattr__(self, "_parents_store", val)
            return val

    @property
    def _state(self: T) -> MutableState[T]:
        """
        Unique identity token for this object. 
        Created lazily and stored strongly.
        """

        try:
            return cast(
                MutableState[T],
                object.__getattribute__(self, "_state_inst")
            )
        except AttributeError:
            val = MutableState(self)
            object.__setattr__(self, "_state_inst", val)
            return val


    def changed(self) -> None:
        """Notify parents using the library's safe propagation logic."""
        events.safe_changed(self)