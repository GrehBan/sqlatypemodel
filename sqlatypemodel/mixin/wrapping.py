"""Recursive wrapping logic for mutable structures."""

from __future__ import annotations

import types
from typing import Any, cast

from sqlalchemy.ext.mutable import MutableDict, MutableList, MutableSet

from sqlatypemodel.mixin import events, inspection
from sqlatypemodel.mixin._introspection_data import _ATOMIC_TYPES
from sqlatypemodel.mixin.protocols import Trackable
from sqlatypemodel.mixin.state import MutableState
from sqlatypemodel.mixin.types import (
    KeyableMutableDict,
    KeyableMutableList,
    KeyableMutableSet,
)
from sqlatypemodel.util import constants


def get_or_create_state(parent: Trackable | Any) -> MutableState[Any]:
    """Retrieves or creates a MutableState identity token (optimized)."""
    # Direct object.__getattribute__ is faster than getattr + hasattr
    try:
        state = object.__getattribute__(parent, "_state")
        return cast(MutableState[Any], state)
    except AttributeError:
        pass

    # Not found, create and store
    state = MutableState(parent)
    # Use _state_inst if _state already exists (Pydantic case)
    key = (
        "_state_inst"
        if object.__getattribute__(parent, "__dict__")
        and "_state" in parent.__dict__
        else "_state"
    )
    object.__setattr__(parent, key, state)
    return state


def wrap_mutable(
    parent: Trackable | Any,
    value: Any,
    _seen: dict[int, Any] | None = None,
    depth: int = 0,
    key: str | int | None = None,
) -> Any:
    """Recursively wrap collections and trackable objects (optimized)."""
    # Fast path: None and atomic types (short-circuit early)
    if value is None or type(value) in _ATOMIC_TYPES:
        return value

    # Pre-compute state once
    parent_state = get_or_create_state(parent)

    # Check if we've already wrapped this object (cache hit)
    obj_id = id(value)
    if _seen is None:
        _seen = {}
    elif obj_id in _seen:
        # Cache hit: reuse wrapped object and update link
        wrapped_cached = _seen[obj_id]
        parent_state.link(wrapped_cached, key)
        return wrapped_cached

    # Check depth limit early
    max_depth = getattr(
        parent, "_max_nesting_depth", constants.DEFAULT_MAX_NESTING_DEPTH
    )
    if depth > max_depth:
        return value

    # Check if already trackable (fast hasattr substitute)
    if hasattr(value, "_parents"):
        _seen[obj_id] = value
        wrapped_model = _wrap_trackable(value, _seen, depth, key)
        parent_state.link(value, key)
        return wrapped_model

    # Check if already a Mutable type (SQLAlchemy)
    if isinstance(value, MutableList | MutableDict | MutableSet):
        _seen[obj_id] = value
        # Patch changed method if needed
        if getattr(value, "changed", None) is not events.safe_changed:
            object.__setattr__(
                value, "changed", types.MethodType(events.safe_changed, value)
            )
        parent_state.link(value, key)
        return value

    # Only now check and wrap standard types
    value_type = type(value)
    wrapped: Any
    if value_type is list:
        wrapped = _wrap_list(value, _seen, depth, key)
    elif value_type is dict:
        wrapped = _wrap_dict(value, _seen, depth, key)
    elif value_type is set:
        wrapped = _wrap_set(value, _seen, depth, key)
    else:
        return value

    parent_state.link(wrapped, key)
    return wrapped


def _wrap_trackable(
    value: Trackable,
    _seen: dict[int, Any],
    depth: int,
    key: str | int | None,
) -> Trackable:
    """Wrap a trackable object and scan its children (optimized)."""
    attrs = inspection.extract_attrs_to_scan(value)
    value_cls = type(value)

    # Pre-compute ignore set for this class to avoid repeated lookups
    for attr_name, attr_val in attrs.items():
        # Direct check instead of function call where possible
        if attr_name.startswith("_"):
            continue
        if inspection.ignore_attr_name(value_cls, attr_name):
            continue

        wrapped_attr = wrap_mutable(
            value, attr_val, _seen, depth + 1, key=attr_name
        )

        if wrapped_attr is not attr_val:
            object.__setattr__(value, attr_name, wrapped_attr)

    return value


def _wrap_list(
    value: list[Any],
    _seen: dict[int, Any],
    depth: int,
    key: str | int | None,
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
    value: dict[Any, Any],
    _seen: dict[int, Any],
    depth: int,
    key: str | int | None,
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
    value: set[Any],
    _seen: dict[int, Any],
    depth: int,
    key: str | int | None,
) -> MutableSet[Any]:
    """Wrap a standard set into a KeyableMutableSet."""
    wrapped: KeyableMutableSet[Any] = KeyableMutableSet()
    _seen[id(value)] = wrapped

    for item in value:
        wrapped.add(wrap_mutable(wrapped, item, _seen, depth + 1, key=None))

    return wrapped


def is_mutable_and_untracked(obj: Any) -> bool:
    """Check if object needs wrapping OR patching (O(1) fast path)."""
    # Early return for None
    if obj is None:
        return False

    t = type(obj)

    # Most common case: atomic types (str, int, etc)
    # This is O(1) frozenset lookup
    if t in _ATOMIC_TYPES:
        return False

    # Collections: test exact type first (faster than isinstance)
    if t is list or t is dict or t is set:
        return True

    # Already wrapped trackable objects
    # Use direct attribute lookup to avoid hasattr overhead
    try:
        object.__getattribute__(obj, "_parents")
        return False
    except AttributeError:
        pass

    # SQLAlchemy Mutable types (rare case, check last)
    if isinstance(obj, MutableList | MutableDict | MutableSet):
        return getattr(obj, "changed", None) is not events.safe_changed

    # Pydantic models (common but more expensive check)
    return inspection.is_pydantic(obj)


def relink_descendants(
    parent: Any, _seen: dict[int, Any] | None = None
) -> None:
    """Recursively re-link already wrapped objects to their current parent."""
    if _seen is None:
        _seen = {}

    self_id = id(parent)
    if self_id in _seen:
        return
    _seen[self_id] = parent

    state = getattr(parent, "_state", None)
    if not isinstance(state, MutableState):
        return

    attrs = inspection.extract_attrs_to_scan(parent)
    for attr_name, attr_value in attrs.items():
        if inspection.ignore_attr_name(type(parent), attr_name):
            continue

        if hasattr(attr_value, "_relink_to_parent"):
            attr_value._relink_to_parent(state, attr_name)
            relink_descendants(attr_value, _seen=_seen)
        elif isinstance(attr_value, MutableList | MutableDict | MutableSet):
            # Collections also need relinking
            if hasattr(attr_value, "_parents"):
                attr_value._parents[state] = attr_name
                # And scan their items
                from sqlatypemodel.mixin.protocols import MutableMixinProto

                if isinstance(attr_value, MutableList):
                    coll_state = getattr(attr_value, "_state", None)
                    if isinstance(coll_state, MutableState):
                        for i, item in enumerate(attr_value):
                            if isinstance(item, MutableMixinProto):
                                item._relink_to_parent(coll_state, i)
                elif isinstance(attr_value, MutableDict):
                    coll_state = getattr(attr_value, "_state", None)
                    if isinstance(coll_state, MutableState):
                        for k, v in attr_value.items():
                            if isinstance(v, MutableMixinProto):
                                v._relink_to_parent(coll_state, k)


def scan_and_wrap_fields(
    parent: Any, _seen: dict[int, Any] | None = None
) -> None:
    """Iterate over object fields and wrap mutable ones (optimized)."""
    if _seen is None:
        _seen = {}

    self_id = id(parent)
    if self_id in _seen:
        return
    _seen[self_id] = parent

    attrs = inspection.extract_attrs_to_scan(parent)
    parent_cls = type(parent)

    for attr_name, attr_value in attrs.items():
        # Fast skip checks
        if attr_value is None:
            continue
        if attr_name.startswith("_"):
            continue
        if inspection.ignore_attr_name(parent_cls, attr_name):
            continue

        try:
            wrapped = wrap_mutable(parent, attr_value, _seen, key=attr_name)

            if wrapped is not attr_value:
                object.__setattr__(parent, attr_name, wrapped)

            # Recursively restore tracking on wrapped object
            if hasattr(wrapped, "_restore_tracking"):
                wrapped._restore_tracking(_seen=_seen)
        except Exception:
            # Silently skip problematic attributes
            pass
