import threading
import weakref
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class MutableState(Generic[T]):
    """Immutable wrapper for parent references in the change tracking graph.
        
        This class solves the 'unhashable parent' problem by acting as a hashable
        token that holds a weak reference to the parent object. It allows ANY object
        (even unhashable ones like lists or frozen=False dataclasses) to participate
        in the parent tracking mechanism.
        
        Attributes:
            ref: An object to create weak reference
    """
    def __init__(
            self,
            ref: T,
    ) -> None:
        self.ref: weakref.ReferenceType[T] = weakref.ref(ref)
        self._lock = threading.RLock()


    def link(self, child: Any, key: str | None) -> None:
        """Establishes a tracking connection between this state and a child object.

        This method registers the current `MutableState` instance in the child's
        `_parents` dictionary. This allows the child object to notify this parent 
        of any mutations using the provided key (attribute name or index).

        The operation is wrapped in a recursive lock (`RLock`) to ensure thread 
        safety and prevent race conditions when modifying the tracking graph 
        concurrently.

        Args:
            child: The child object that should track this parent state.
            key: The attribute name or collection index where the child is stored 
                within the parent.
        """
        if not hasattr(child, "_parents"):
            return
        with self._lock:
            child._parents[self] = key
    
    def unlink(self, child: Any) -> None:
        """Breaks the tracking connection between this state and a child object.

        Removes the current `MutableState` instance from the child's `_parents` 
        dictionary. Once unlinked, mutations within the child will no longer 
        trigger change notifications for this parent.

        The operation is thread-safe and uses a recursive lock to ensure atomic 
        removal of the relationship.

        Args:
            child: The child object to disconnect from this parent state.
        """
        if not hasattr(child, "_parents"):
            return
        with self._lock:
            child._parents.pop(self, None)
