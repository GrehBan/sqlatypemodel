"""Custom SQLAlchemy Mutable types with hashing support."""

from __future__ import annotations

from typing import Any, TypeVar

from sqlalchemy.ext.mutable import MutableDict, MutableList, MutableSet

from sqlatypemodel.mixin.protocols import MutableMethods

_T = TypeVar("_T", bound=Any)
_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


class KeyableMutableList(MutableList[_T], MutableMethods):  # type: ignore[misc]
    """MutableList that uses identity hashing and custom change tracking."""

    pass


class KeyableMutableDict(MutableDict[_KT, _VT], MutableMethods):  # type: ignore[misc]
    """MutableDict that uses identity hashing and custom change tracking."""

    pass


class KeyableMutableSet(MutableSet[_T], MutableMethods):  # type: ignore[misc]
    """MutableSet that uses identity hashing and custom change tracking."""

    pass
