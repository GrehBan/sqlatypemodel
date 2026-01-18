"""Protocols and base implementations for change tracking.

This module defines the protocols that trackable objects must implement,
as well as base implementations for common tracking functionality.
"""

from __future__ import annotations

import threading
from typing import Any, Protocol, TypeVar, cast, runtime_checkable
from weakref import WeakKeyDictionary

from sqlalchemy.ext.mutable import MutableDict, MutableList, MutableSet

from sqlatypemodel.mixin import events
from sqlatypemodel.mixin.state import MutableState

T = TypeVar("T", bound="Trackable")
_STATE_LOCK = threading.RLock()

_COLLECTION_TYPES: tuple[type, ...] = (
    MutableList,
    MutableDict,
    MutableSet,
)


@runtime_checkable
class Trackable(Protocol):
    """Protocol describing a trackable object.

    Objects adhering to this protocol must maintain a reference to their
    parents and provide a mechanism to signal changes.
    """

    @property
    def _parents(
        self: T,
    ) -> WeakKeyDictionary[MutableState[Any], str | int | None]:
        """A dictionary mapping parent states to the key/index in the
        parent."""
        ...

    def changed(self) -> None:
        """Mark the object as changed and propagate the notification."""
        ...


@runtime_checkable
class MutableMixinProto(Trackable, Protocol):
    """Protocol describing a fully functional MutableMixin instance.

    This includes internal state tracking attributes used by the library.
    """

    _max_nesting_depth: int
    _change_suppress_level: int
    _pending_change: bool

    @property
    def _state(self: T) -> MutableState[T]:
        """The immutable identity token for this object."""
        ...

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
        """Force relink this object to a new parent state token.

        Args:
            parent_state: The new parent's state token.
            key: The attribute name or index within the parent.
        """
        ...


class MutableMethods:
    """Base implementation of core tracking properties and methods.

    Provides the implementations for `_parents` and `_state` management,
    as well as the `changed()` signal propagation.
    """

    @property
    def _parents(
        self,
    ) -> WeakKeyDictionary[MutableState[Any], str | int | None]:
        """Retrieve or initialize the parents WeakKeyDictionary.

        Returns:
            A WeakKeyDictionary mapping parent states to keys.
        """
        try:
            return cast(
                "WeakKeyDictionary[MutableState[Any], str | int | None]",
                object.__getattribute__(self, "_parents_store"),
            )
        except AttributeError:
            val: WeakKeyDictionary[
                MutableState[Any], str | int | None
            ] = WeakKeyDictionary()
            object.__setattr__(self, "_parents_store", val)
            return val

    @property
    def _state(self: T) -> MutableState[T]:
        """Retrieve or initialize the unique identity token.

        Created lazily and stored strongly on the object.

        Returns:
            The MutableState token for this object.
        """
        try:
            return cast(
                MutableState[T], object.__getattribute__(self, "_state_inst")
            )
        except AttributeError:
            with _STATE_LOCK:
                # Re-check inside lock
                try:
                    return cast(
                        MutableState[T],
                        object.__getattribute__(self, "_state_inst"),
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
        """Force relink this object to a new parent state token.

        Args:
            parent_state: The new parent's state token.
            key: The attribute name or index within the parent.
        """
        self._parents[parent_state] = key
