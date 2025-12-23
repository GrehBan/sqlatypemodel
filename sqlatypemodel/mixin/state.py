import weakref

from typing import Any, TypeVar, Generic

T = TypeVar("T")


class MutableState(Generic[T]):
    """Immutable wrapper for parent references in the change tracking graph.
        
        This class solves the 'unhashable parent' problem by acting as a hashable
        token that holds a weak reference to the parent object. It allows ANY object
        (even unhashable ones like lists or frozen=False dataclasses) to participate
        in the parent tracking mechanism.
        
        Attributes:
            ref: A weak reference to the parent object.
            attr_name: The attribute name on the parent where the child is stored (if applicable).
    """
    def __init__(
            self,
            ref: weakref.ReferenceType[T],
    ) -> None:
        self.ref = ref

    def __hash__(self) -> int:
        return id(self)
        
    def __eq__(self, other: Any) -> bool:
        return self is other
    
    def get_parent(self) -> T | None:
        return self.ref()
    
    @classmethod
    def wrap(cls: type[MutableState[T]], parent: T) -> MutableState:
        return cls(
            ref=weakref.ref(parent),
        )
