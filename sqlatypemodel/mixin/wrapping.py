"""Recursive wrapping logic for mutable structures."""

from __future__ import annotations

import types
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.mutable import MutableDict, MutableList, MutableSet

from sqlatypemodel.mixin import events, inspection
from sqlatypemodel.mixin.types import (
    KeyableMutableDict,
    KeyableMutableList,
    KeyableMutableSet,
)
from sqlatypemodel.util import constants

if TYPE_CHECKING:
    from sqlatypemodel.mixin.protocols import Trackable


def wrap_mutable(
    parent: Any,
    value: Any,
    seen: set[int] | None = None,
    depth: int = 0,
    key: Any = None,
) -> Any:
    """Recursively wrap collections and trackable objects.

    Args:
        parent: The parent object owning the value.
        value: The value to wrap.
        seen: A set of object IDs to detect cycles.
        depth: Current recursion depth.
        key: The attribute name or index where the value is stored.

    Returns:
        The wrapped value (or original if no wrapping needed).
    """
    if not is_mutable_and_untracked(value):
        return value

    if seen is None:
        seen = set()

    obj_id = id(value)
    if obj_id in seen:
        if hasattr(value, "_parents"):
            value._parents[parent] = key
        return value

    max_depth = getattr(
        parent, "_max_nesting_depth", constants.DEFAULT_MAX_NESTING_DEPTH
    )
    if depth > max_depth:
        return value

    seen.add(obj_id)

    if isinstance(value, (MutableList, MutableDict, MutableSet)):
        return _rewrap_mutable_collection(parent, value, key)

    if hasattr(value, "_parents"):
        return _wrap_trackable(parent, value, seen, depth + 1, key)

    value_type = type(value)
    if value_type is list:
        return _wrap_list(parent, value, seen, depth + 1, key)
    if value_type is dict:
        return _wrap_dict(parent, value, seen, depth + 1, key)
    if value_type is set:
        return _wrap_set(parent, value, seen, depth + 1, key)

    return value


def _rewrap_mutable_collection(parent: Any, value: Any, key: Any) -> Any:
    """Re-parent an existing Mutable collection and ensure it is patched.

    Args:
        parent: The new parent object.
        value: The mutable collection.
        key: The key at which the collection is stored.

    Returns:
        The updated mutable collection.
    """
    if getattr(value, "changed", None) is not events.safe_changed:
        value.changed = types.MethodType(events.safe_changed, value)

    value._parents[parent] = key
    return value


def _wrap_trackable(
    parent: Any, value: Trackable, seen: set[int], depth: int, key: Any
) -> Trackable:
    """Wrap a trackable object and scan its children.

    Args:
        parent: The parent object.
        value: The trackable object.
        seen: Cycle detection set.
        depth: Recursion depth.
        key: The attribute name.

    Returns:
        The wrapped trackable object.
    """
    value._parents[parent] = key

    attrs = inspection.extract_attrs_to_scan(value)
    value_cls = type(value)

    for attr_name, attr_val in attrs.items():
        if inspection.ignore_attr_name(value_cls, attr_name):
            continue

        wrapped = wrap_mutable(value, attr_val, seen, depth, key=attr_name)

        if wrapped is not attr_val:
            object.__setattr__(value, attr_name, wrapped)

    return value


def _wrap_list(
    parent: Any, value: list[Any], seen: set[int], depth: int, key: Any
) -> MutableList[Any]:
    """Wrap a standard list into a KeyableMutableList.

    Args:
        parent: The parent object.
        value: The source list.
        seen: Cycle detection set.
        depth: Recursion depth.
        key: The attribute name/index.

    Returns:
        A new KeyableMutableList containing wrapped items.
    """
    wrapped = KeyableMutableList(value)
    wrapped.changed = types.MethodType(events.safe_changed, wrapped)
    wrapped._parents[parent] = key

    for i, item in enumerate(wrapped):
        new_val = wrap_mutable(wrapped, item, seen, depth, key=i)
        if new_val is not item:
            list.__setitem__(wrapped, i, new_val)

    return wrapped


def _wrap_dict(
    parent: Any, value: dict[Any, Any], seen: set[int], depth: int, key: Any
) -> MutableDict[Any, Any]:
    """Wrap a standard dict into a KeyableMutableDict.

    Args:
        parent: The parent object.
        value: The source dict.
        seen: Cycle detection set.
        depth: Recursion depth.
        key: The attribute name/index.

    Returns:
        A new KeyableMutableDict containing wrapped items.
    """
    wrapped = KeyableMutableDict(value)
    wrapped.changed = types.MethodType(events.safe_changed, wrapped)
    wrapped._parents[parent] = key

    for k, v in wrapped.items():
        new_val = wrap_mutable(wrapped, v, seen, depth, key=k)
        if new_val is not v:
            dict.__setitem__(wrapped, k, new_val)

    return wrapped


def _wrap_set(
    parent: Any, value: set[Any], seen: set[int], depth: int, key: Any
) -> MutableSet[Any]:
    """Wrap a standard set into a KeyableMutableSet.

    Args:
        parent: The parent object.
        value: The source set.
        seen: Cycle detection set.
        depth: Recursion depth.
        key: The attribute name/index.

    Returns:
        A new KeyableMutableSet containing wrapped items.
    """
    wrapped = KeyableMutableSet()
    wrapped.changed = types.MethodType(events.safe_changed, wrapped)
    wrapped._parents[parent] = key

    for item in value:
        wrapped.add(wrap_mutable(wrapped, item, seen, depth, key=None))

    return wrapped


def is_mutable_and_untracked(obj: Any) -> bool:
    """Check if object needs wrapping OR patching.

    Args:
        obj: The object to inspect.

    Returns:
        True if the object is mutable and not yet correctly tracked/patched.
    """
    if obj is None or type(obj) in constants._ATOMIC_TYPES:
        return False

    if hasattr(obj, "_parents"):
        if getattr(obj, "changed", None) is not events.safe_changed:
            return True
        return False

    return isinstance(obj, (list, dict, set)) or inspection.is_pydantic(obj)


def scan_and_wrap_fields(parent: Any, _seen: set[int] | None = None) -> None:
    """Iterate over object fields and wrap mutable ones.

    Args:
        parent: The object to scan.
        _seen: Cycle detection set.
    """
    if _seen is None:
        _seen = set()

    self_id = id(parent)
    if self_id in _seen:
        return
    _seen.add(self_id)

    attrs = inspection.extract_attrs_to_scan(parent)
    for attr_name, attr_value in attrs.items():
        if (
            inspection.ignore_attr_name(type(parent), attr_name)
            or attr_value is None
        ):
            continue
        try:
            wrapped = wrap_mutable(parent, attr_value, _seen, key=attr_name)

            if wrapped is not attr_value:
                object.__setattr__(parent, attr_name, wrapped)

            if hasattr(wrapped, "_parents"):
                wrapped._parents[parent] = attr_name

            if hasattr(wrapped, "_restore_tracking"):
                wrapped._restore_tracking(_seen=_seen)
        except Exception:
            pass