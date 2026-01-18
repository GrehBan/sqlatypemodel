from __future__ import annotations

import threading
import weakref
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from sqlatypemodel.mixin.protocols import Trackable

T = TypeVar("T")


class MutableState(Generic[T]):
    """Immutable wrapper for parent references in the change tracking graph.

    This class acts as a hashable token representing the identity of a
    trackable object. It solves the 'unhashable parent' problem by holding
    a weak reference to the parent object, allowing any object (even
    unhashable ones like lists or unfreezed dataclasses) to participate
    in the parent tracking mechanism.

    Attributes:
        ref: A weak reference to the parent object.
    """

    __slots__ = ("ref", "_lock", "__weakref__")

    def __init__(self, obj: T) -> None:
        """Initialize the mutable state token.

        Args:
            obj: The parent object to create a weak reference for.
        """
        self.ref: weakref.ReferenceType[T] = weakref.ref(obj)
        self._lock = threading.RLock()

    def obj(self) -> T | None:
        """Return the parent object from the weak reference.

        This method fulfills the SQLAlchemy Mutable parent protocol,
        allowing this state token to be used directly in SQLAlchemy's
        `_parents` dictionary.

        Returns:
            The dereferenced parent object, or None if it has been collected.
        """
        return self.ref()

    def link(self, child: Trackable | Any, key: str | int | None) -> None:
        """Establish a tracking connection between this state and a child.

        Registers this `MutableState` instance in the child's `_parents`
        dictionary. This enables the child to bubble up mutation events
        to the parent.

        The operation is thread-safe using a recursive lock.

        Args:
            child: The child object that should track this parent state.
            key: The attribute name or collection index where the child is
                stored within the parent.
        """
        if not hasattr(child, "_parents"):
            return

        with self._lock:
            child._parents[self] = key

    def unlink(self, child: Trackable | Any) -> None:
        """Break the tracking connection between this state and a child.

        Removes this `MutableState` instance from the child's `_parents`
        dictionary.

        The operation is thread-safe using a recursive lock.

        Args:
            child: The child object to disconnect from this parent state.
        """
        if not hasattr(child, "_parents"):
            return

        with self._lock:
            child._parents.pop(self, None)
