"""Custom SQLAlchemy Mutable types with hashing support."""

from typing import Any, TypeVar

from sqlalchemy.ext.mutable import MutableDict, MutableList, MutableSet

from sqlatypemodel.mixin.protocols import MutableMethods

_T = TypeVar("_T", bound=Any)
_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


class KeyableMutableList(MutableMethods, MutableList[_T]):
    """MutableList that uses identity hashing and custom change tracking."""
    pass


class KeyableMutableDict(MutableMethods, MutableDict[_KT, _VT]):
    """MutableDict that uses identity hashing and custom change tracking."""
    pass



class KeyableMutableSet(MutableMethods, MutableSet[_T]):
    """MutableSet that uses identity hashing and custom change tracking."""
    pass