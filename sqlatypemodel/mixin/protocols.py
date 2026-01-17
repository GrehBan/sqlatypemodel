from __future__ import annotations

from typing import Any, Protocol, TypeVar, cast, runtime_checkable
from weakref import WeakKeyDictionary

from sqlalchemy.ext.mutable import MutableDict, MutableList, MutableSet

from sqlatypemodel.mixin import events
from sqlatypemodel.mixin.state import MutableState

__all__ = ("Trackable", "MutableMethods", "MutableMixinProto")

T = TypeVar("T", bound="Trackable")

_COLLECTION_TYPES: tuple[type, ...] = (
    MutableList,
    MutableDict,
    MutableSet,
)


@runtime_checkable
class Trackable(Protocol):
    """Protocol describing a trackable object.

    This protocol defines the interface required for objects that support
    change tracking within the library.
    """

    @property
    def _parents(
        self: T,
    ) -> WeakKeyDictionary[MutableState[Any], str | int | None]: ...

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

    def _restore_tracking(self, _seen: dict[int, Any] | None = None) -> None:
        """Restore change tracking mechanisms (e.g., after unpickling).

        Args:
            _seen: A dictionary mapping id(original) -> wrapped_instance
                for cycle detection.
        """
        ...

    def _relink_to_parent(
        self, parent_state: MutableState[Any], key: str | int | None
    ) -> None:
        """Force relink this object to a new parent state token."""
        ...


class MutableMethods:
    @property
    def _parents(
        self,
    ) -> WeakKeyDictionary[MutableState[Any], str | int | None]:
        """Retrieve or initialize the parents WeakKeyDictionary."""

        try:
            return cast(
                "WeakKeyDictionary[MutableState[Any], str | int | None]",
                object.__getattribute__(self, "_parents_store"),
            )
        except AttributeError:
            val: WeakKeyDictionary[MutableState[Any], str | int | None] = (
                WeakKeyDictionary()
            )
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
                MutableState[T], object.__getattribute__(self, "_state_inst")
            )
        except AttributeError:
            val = MutableState(self)
            object.__setattr__(self, "_state_inst", val)
            return val

    def changed(self) -> None:
        """Notify parents using the library's safe propagation logic."""
        events.safe_changed(self)

    def _relink_to_parent(
        self, parent_state: MutableState[Any], key: str | int | None
    ) -> None:
        """Force relink this object to a new parent state token."""
        self._parents[parent_state] = key
