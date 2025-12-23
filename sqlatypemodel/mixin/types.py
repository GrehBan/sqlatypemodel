"""Custom SQLAlchemy Mutable types with hashing support."""

from typing import TypeVar, Any
from weakref import WeakKeyDictionary

from sqlalchemy.ext.mutable import MutableDict, MutableList, MutableSet

from sqlatypemodel.mixin import events
from sqlatypemodel.mixin.protocols import MutableMethods

_T = TypeVar("_T", bound=Any)
_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


class KeyableMutableList(MutableMethods, MutableList[_T]):  # type: ignore[misc]
    """MutableList that uses identity hashing and custom change tracking."""
    pass


class KeyableMutableDict(MutableMethods, MutableDict[_KT, _VT]):  # type: ignore[misc]
    """MutableDict that uses identity hashing and custom change tracking."""
    pass



class KeyableMutableSet(MutableMethods, MutableSet[_T]):  # type: ignore[misc]
    """MutableSet that uses identity hashing and custom change tracking."""
    pass