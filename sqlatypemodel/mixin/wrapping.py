"""Recursive wrapping logic for mutable structures."""

from __future__ import annotations

import types
from typing import Any

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
    """Retrieves or creates a MutableState identity token for the given parent.

    This function ensures that a unique `MutableState` object exists for the
    parent instance. This state object represents the parent's identity in the
    change tracking graph and is used as a key in children's parent references.

    It attempts to store the state in the `_state` attribute. If that attribute
    is already defined (e.g., as a property in a protocol or mixin), it falls
    back to storing it in `_state_inst` to avoid conflicts.

    Args:
        parent: The object (e.g., Pydantic model, list, or dict) for which to
            retrieve or create the state.

    Returns:
        The MutableState wrapper associated with the parent object.
    """
    state = getattr(parent, "_state", None)
    if state is None:
        state = MutableState.wrap(parent)
        if hasattr(parent, "_state"):
            key = "_state_inst"
        else:
            key = "_state"
        object.__setattr__(parent, key, state)
    return state


def wrap_mutable(
    parent: Any,
    value: Any,
    _seen: dict[int, Any] | None = None,
    depth: int = 0,
    key: Any = None,
) -> Any:
    """Recursively wrap collections and trackable objects.

    Args:
        parent: The parent object owning the value.
        value: The value to wrap.
        _seen: A dictionary mapping id(original) -> wrapped_instance for cycle detection.
        depth: Current recursion depth.
        key: The attribute name or index where the value is stored.

    Returns:
        The wrapped value (or original if no wrapping needed).
    """
    if not is_mutable_and_untracked(value):
        return value

    if _seen is None:
        _seen = {}

    obj_id = id(value)

    state = get_or_create_state(parent)

    if obj_id in _seen:
        wrapped = _seen[obj_id]
        if hasattr(wrapped, "_parents"):
            wrapped._parents[state] = key
        return wrapped

    max_depth = getattr(
        parent, "_max_nesting_depth", constants.DEFAULT_MAX_NESTING_DEPTH
    )
    if depth > max_depth:
        return value

    if hasattr(value, "_parents"):
        _seen[obj_id] = value
        return _wrap_trackable(parent, value, _seen, depth + 1, key)

    if isinstance(value, MutableList | MutableDict | MutableSet):
        _seen[obj_id] = value
        if getattr(value, "changed", None) is not events.safe_changed and not hasattr(value, "_parents"):
             value.changed = types.MethodType(events.safe_changed, value) # type: ignore
        
        if hasattr(value, "_parents"):
             value._parents[state] = key
        return value

    value_type = type(value)
    if value_type is list:
        return _wrap_list(parent, value, _seen, depth + 1, key)
    if value_type is dict:
        return _wrap_dict(parent, value, _seen, depth + 1, key)
    if value_type is set:
        return _wrap_set(parent, value, _seen, depth + 1, key)

    return value


def _wrap_trackable(
    parent: Any, value: Trackable, _seen: dict[int, Any], depth: int, key: Any
) -> Trackable:
    """Wrap a trackable object and scan its children."""
    state = get_or_create_state(parent)
    value._parents[state] = key

    attrs = inspection.extract_attrs_to_scan(value)
    value_cls = type(value)

    for attr_name, attr_val in attrs.items():
        if inspection.ignore_attr_name(value_cls, attr_name):
            continue

        wrapped = wrap_mutable(value, attr_val, _seen, depth, key=attr_name)

        if wrapped is not attr_val:
            object.__setattr__(value, attr_name, wrapped)

    return value


def _wrap_list(
    parent: Any, value: list[Any], _seen: dict[int, Any], depth: int, key: Any
) -> MutableList[Any]:
    """Wrap a standard list into a KeyableMutableList."""
    wrapped: KeyableMutableList[Any] = KeyableMutableList(value)
    
    _seen[id(value)] = wrapped
    
    state = get_or_create_state(parent)
    wrapped._parents[state] = key

    for i, item in enumerate(wrapped):
        new_val = wrap_mutable(wrapped, item, _seen, depth, key=i)
        if new_val is not item:
            list.__setitem__(wrapped, i, new_val)

    return wrapped


def _wrap_dict(
    parent: Any, value: dict[Any, Any], _seen: dict[int, Any], depth: int, key: Any
) -> MutableDict[Any, Any]:
    """Wrap a standard dict into a KeyableMutableDict."""
    wrapped: KeyableMutableDict[Any, Any] = KeyableMutableDict(value)
    
    _seen[id(value)] = wrapped
    
    state = get_or_create_state(parent)
    wrapped._parents[state] = key

    for k, v in list(wrapped.items()):
        new_val = wrap_mutable(wrapped, v, _seen, depth, key=k)
        if new_val is not v:
            dict.__setitem__(wrapped, k, new_val)

    return wrapped


def _wrap_set(
    parent: Any, value: set[Any], _seen: dict[int, Any], depth: int, key: Any
) -> MutableSet[Any]:
    """Wrap a standard set into a KeyableMutableSet."""
    wrapped: KeyableMutableSet[Any] = KeyableMutableSet()
    
    _seen[id(value)] = wrapped
    
    state = get_or_create_state(parent)
    wrapped._parents[state] = key

    for item in value:
        wrapped.add(wrap_mutable(wrapped, item, _seen, depth, key=None))

    return wrapped


def is_mutable_and_untracked(obj: Any) -> bool:
    """Check if object needs wrapping OR patching."""
    if obj is None or type(obj) in constants._ATOMIC_TYPES:
        return False
    return isinstance(obj, list | dict | set) or inspection.is_pydantic(obj)


def scan_and_wrap_fields(parent: Any, _seen: Any | None = None) -> None:
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
            inspection.ignore_attr_name(type(parent), attr_name) # type: ignore [arg-type]
            or attr_value is None
        ):
            continue
        try:
            wrapped = wrap_mutable(parent, attr_value, _seen, key=attr_name)

            if wrapped is not attr_value:
                object.__setattr__(parent, attr_name, wrapped)

            if hasattr(wrapped, "_parents"):
                state = get_or_create_state(parent)
                wrapped._parents[state] = attr_name

            if hasattr(wrapped, "_restore_tracking"):
                wrapped._restore_tracking(_seen=_seen)
        except Exception:
            pass