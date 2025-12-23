"""Recursive wrapping logic for mutable structures."""

from __future__ import annotations

import types
from typing import Any, cast

from sqlalchemy.ext.mutable import MutableDict, MutableList, MutableSet

from sqlatypemodel.mixin import events, inspection
from sqlatypemodel.mixin.protocols import Trackable
from sqlatypemodel.mixin.state import MutableState
from sqlatypemodel.mixin.types import (
    KeyableMutableDict,
    KeyableMutableList,
    KeyableMutableSet,
)
from sqlatypemodel.util import constants


def get_or_create_state(parent: Any) -> MutableState[Any]:
    """Retrieves or creates a MutableState identity token for the given parent."""
    state = getattr(parent, "_state", constants.MISSING)
    if state is constants.MISSING:
        state = MutableState(parent)
        key = "_state_inst" if hasattr(parent, "_state") else "_state"
        object.__setattr__(parent, key, state)
    return cast(MutableState[Any], state)


def wrap_mutable(
    parent: Any,
    value: Any,
    _seen: dict[int, Any] | None = None,
    depth: int = 0,
    key: Any = None,
) -> Any:
    """Recursively wrap collections and trackable objects."""
    if not is_mutable_and_untracked(value):
        return value

    if _seen is None:
        _seen = {}

    obj_id = id(value)
    state = get_or_create_state(parent)

    if obj_id in _seen:
        wrapped = _seen[obj_id]
        state.link(wrapped, key)
        return wrapped

    max_depth = getattr(
        parent, "_max_nesting_depth", constants.DEFAULT_MAX_NESTING_DEPTH
    )
    if depth > max_depth:
        return value

    if hasattr(value, "_parents"):
        _seen[obj_id] = value
        wrapped = _wrap_trackable(value, _seen, depth, key)
        state.link(value, key)
        return wrapped

    if isinstance(value, MutableList | MutableDict | MutableSet):
        _seen[obj_id] = value
        if getattr(value, "changed", None) is not events.safe_changed:
             value.changed = types.MethodType(events.safe_changed, value) # type: ignore
        
        state.link(value, key)
        return value

    value_type = type(value)
    wrapped: Any = value

    if value_type is list:
        wrapped = _wrap_list(value, _seen, depth, key)
    elif value_type is dict:
        wrapped = _wrap_dict(value, _seen, depth, key)
    elif value_type is set:
        wrapped = _wrap_set(value, _seen, depth, key)
    else:
        return value

    # Link the newly created wrapper to the parent state
    state.link(wrapped, key)
    return wrapped


def _wrap_trackable(
        value: Trackable, _seen: dict[int, Any], depth: int, key: Any
) -> Trackable:
    """Wrap a trackable object and scan its children."""

    attrs = inspection.extract_attrs_to_scan(value)
    value_cls = type(value)

    for attr_name, attr_val in attrs.items():
        if inspection.ignore_attr_name(value_cls, attr_name):
            continue

        wrapped_attr = wrap_mutable(value, attr_val, _seen, depth + 1, key=attr_name)

        if wrapped_attr is not attr_val:
            object.__setattr__(value, attr_name, wrapped_attr)

    return value


def _wrap_list(
    value: list[Any], _seen: dict[int, Any], depth: int, key: Any
) -> MutableList[Any]:
    """Wrap a standard list into a KeyableMutableList."""
    wrapped: KeyableMutableList[Any] = KeyableMutableList(value)
    _seen[id(value)] = wrapped

    for i, item in enumerate(wrapped):
        new_val = wrap_mutable(wrapped, item, _seen, depth + 1, key=i)
        if new_val is not item:
            list.__setitem__(wrapped, i, new_val)

    return wrapped


def _wrap_dict(
        value: dict[Any, Any], _seen: dict[int, Any], depth: int, key: Any
) -> MutableDict[Any, Any]:
    """Wrap a standard dict into a KeyableMutableDict."""
    wrapped: KeyableMutableDict[Any, Any] = KeyableMutableDict(value)
    _seen[id(value)] = wrapped

    for k, v in wrapped.items():
        new_val = wrap_mutable(wrapped, v, _seen, depth + 1, key=k)
        if new_val is not v:
            dict.__setitem__(wrapped, k, new_val)

    return wrapped


def _wrap_set(
        value: set[Any], _seen: dict[int, Any], depth: int, key: Any
) -> MutableSet[Any]:
    """Wrap a standard set into a KeyableMutableSet."""
    wrapped: KeyableMutableSet[Any] = KeyableMutableSet()
    _seen[id(value)] = wrapped

    for item in value:
        wrapped.add(wrap_mutable(wrapped, item, _seen, depth + 1, key=None))

    return wrapped


def is_mutable_and_untracked(obj: Any) -> bool:
    """Check if object needs wrapping OR patching."""
    if obj is None or type(obj) in constants._ATOMIC_TYPES:
        return False
    return isinstance(obj, list | dict | set) or inspection.is_pydantic(obj)


def scan_and_wrap_fields(parent: Any, _seen: dict[int, Any] | None = None) -> None:
    """Iterate over object fields and wrap mutable ones."""
    if _seen is None:
        _seen = {}

    self_id = id(parent)
    if self_id in _seen:
        return
    _seen[self_id] = parent

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

            if hasattr(wrapped, "_restore_tracking"):
                wrapped._restore_tracking(_seen=_seen)
        except Exception:
            pass