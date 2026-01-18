"""Recursive wrapping logic for mutable structures."""

from __future__ import annotations

import logging
import threading
import types
from typing import Any, cast

from sqlalchemy.ext.mutable import MutableDict, MutableList, MutableSet

from sqlatypemodel.mixin import events, inspection
from sqlatypemodel.mixin._introspection_data import _ATOMIC_TYPES
from sqlatypemodel.mixin.protocols import MutableMixinProto, Trackable
from sqlatypemodel.mixin.state import MutableState
from sqlatypemodel.mixin.types import (
    KeyableMutableDict,
    KeyableMutableList,
    KeyableMutableSet,
)
from sqlatypemodel.util import constants

logger = logging.getLogger(__name__)

_STATE_CREATION_LOCK = threading.Lock()


def get_or_create_state(parent: Trackable | Any) -> MutableState[Any]:
    """Retrieves or creates a MutableState identity token (optimized)."""
    # Double-checked locking pattern for performance
    state = getattr(parent, "_state", None)
    if state is not None:
        return cast(MutableState[Any], state)

    with _STATE_CREATION_LOCK:
        # Re-check inside lock
        state = getattr(parent, "_state", None)
        if state is not None:
            return cast(MutableState[Any], state)

        state = MutableState(parent)
        parent_dict = getattr(parent, "__dict__", None)
        key = "_state"
        if parent_dict is not None and "_state" in parent_dict:
            key = "_state_inst"

        object.__setattr__(parent, key, state)
        return state


def _wrap_list(
    value: list[Any],
    _seen: dict[int, Any],
    depth: int,
    key: str | int | None,
    max_depth: int,
) -> MutableList[Any]:
    """Wrap a standard list into a KeyableMutableList."""
    wrapped: KeyableMutableList[Any] = KeyableMutableList(value)
    _seen[id(value)] = wrapped

    for i, item in enumerate(wrapped):
        new_val = wrap_mutable(
            wrapped, item, _seen, depth + 1, key=i, max_depth_limit=max_depth
        )
        if new_val is not item:
            list.__setitem__(wrapped, i, new_val)

    return wrapped


def _wrap_dict(
    value: dict[Any, Any],
    _seen: dict[int, Any],
    depth: int,
    key: str | int | None,
    max_depth: int,
) -> MutableDict[Any, Any]:
    """Wrap a standard dict into a KeyableMutableDict."""
    wrapped: KeyableMutableDict[Any, Any] = KeyableMutableDict(value)
    _seen[id(value)] = wrapped

    for k, v in wrapped.items():
        new_val = wrap_mutable(
            wrapped, v, _seen, depth + 1, key=k, max_depth_limit=max_depth
        )
        if new_val is not v:
            dict.__setitem__(wrapped, k, new_val)

    return wrapped


def _wrap_set(
    value: set[Any],
    _seen: dict[int, Any],
    depth: int,
    key: str | int | None,
    max_depth: int,
) -> MutableSet[Any]:
    """Wrap a standard set into a KeyableMutableSet."""
    wrapped: KeyableMutableSet[Any] = KeyableMutableSet()
    _seen[id(value)] = wrapped

    for item in value:
        wrapped.add(
            wrap_mutable(
                wrapped,
                item,
                _seen,
                depth + 1,
                key=None,
                max_depth_limit=max_depth,
            )
        )

    return wrapped


# Dispatch table for standard types
_WRAP_DISPATCH = {
    list: _wrap_list,
    dict: _wrap_dict,
    set: _wrap_set,
}


def wrap_mutable(
    parent: Trackable | Any,
    value: Any,
    _seen: dict[int, Any] | None = None,
    depth: int = 0,
    key: str | int | None = None,
    max_depth_limit: int | None = None,
) -> Any:
    """Recursively wrap collections and trackable objects (optimized)."""
    if value is None or type(value) in _ATOMIC_TYPES:
        return value

    parent_state = get_or_create_state(parent)
    obj_id = id(value)

    if _seen is None:
        _seen = {}
    elif obj_id in _seen:
        wrapped_cached = _seen[obj_id]
        parent_state.link(wrapped_cached, key)
        return wrapped_cached

    # Resolve max_depth_limit if not provided (start of recursion)
    if max_depth_limit is None:
        max_depth_limit = getattr(
            parent, "_max_nesting_depth", constants.DEFAULT_MAX_NESTING_DEPTH
        )

    if depth > max_depth_limit:
        return value

    return _handle_wrapping(
        parent_state, value, _seen, depth, key, max_depth_limit
    )


def _handle_wrapping(
    parent_state: MutableState[Any],
    value: Any,
    _seen: dict[int, Any],
    depth: int,
    key: str | int | None,
    max_depth: int,
) -> Any:
    """Internal router for different wrapping strategies."""
    obj_id = id(value)

    # 1. Trackable models (Pydantic, etc.)
    if getattr(value, "_parents", None) is not None:
        _seen[obj_id] = value
        _wrap_trackable(value, _seen, depth, max_depth)
        parent_state.link(value, key)
        return value

    # 2. Already wrapped collections
    if isinstance(value, MutableList | MutableDict | MutableSet):
        _seen[obj_id] = value
        if getattr(value, "changed", None) is not events.safe_changed:
            object.__setattr__(
                value, "changed", types.MethodType(events.safe_changed, value)
            )
        parent_state.link(value, key)
        return value

    # 3. Standard collections (list, dict, set)
    wrapper_func = _WRAP_DISPATCH.get(type(value))  # type: ignore[call-overload]
    if wrapper_func:
        wrapped = wrapper_func(value, _seen, depth, key, max_depth)
        parent_state.link(wrapped, key)
        return wrapped

    return value


def _wrap_trackable(
    value: Trackable,
    _seen: dict[int, Any],
    depth: int,
    max_depth: int,
) -> Trackable:
    """Wrap a trackable object and scan its children (optimized)."""
    attrs = inspection.extract_attrs_to_scan(value)
    value_cls = type(value)

    for attr_name, attr_val in attrs.items():
        if attr_name.startswith("_") or inspection.ignore_attr_name(
            value_cls, attr_name
        ):
            continue

        wrapped_attr = wrap_mutable(
            value,
            attr_val,
            _seen,
            depth + 1,
            key=attr_name,
            max_depth_limit=max_depth,
        )

        if wrapped_attr is not attr_val:
            object.__setattr__(value, attr_name, wrapped_attr)

    return value


def is_mutable_and_untracked(obj: Any) -> bool:
    """Check if object needs wrapping OR patching (O(1) fast path)."""
    if obj is None:
        return False

    t = type(obj)
    if t in _ATOMIC_TYPES:
        return False

    if t is list or t is dict or t is set:
        return True

    if getattr(obj, "_parents", None) is not None:
        return False

    if isinstance(obj, MutableList | MutableDict | MutableSet):
        return getattr(obj, "changed", None) is not events.safe_changed

    return inspection.is_pydantic(obj)


def _relink_collection(
    parent_state: MutableState[Any],
    attr_name: str | int,
    collection: MutableList[Any] | MutableDict[Any, Any] | MutableSet[Any],
) -> None:
    """Relink a collection and its items to their states (internal)."""
    if not hasattr(collection, "_parents"):
        return

    collection._parents[parent_state] = attr_name

    coll_state = getattr(collection, "_state", None)
    if not isinstance(coll_state, MutableState):
        return

    if isinstance(collection, MutableList):
        for i, item in enumerate(collection):
            if isinstance(item, MutableMixinProto):
                item._relink_to_parent(coll_state, i)
    elif isinstance(collection, MutableDict):
        for k, v in collection.items():
            if isinstance(v, MutableMixinProto):
                v._relink_to_parent(coll_state, k)


def _relink_attribute(
    parent_state: MutableState[Any],
    attr_name: str | int,
    attr_value: Any,
    _seen: dict[int, Any],
) -> None:
    """Relink a single attribute to its parent state (internal)."""
    if hasattr(attr_value, "_relink_to_parent"):
        attr_value._relink_to_parent(parent_state, attr_name)
        relink_descendants(attr_value, _seen=_seen)
        return

    if isinstance(attr_value, MutableList | MutableDict | MutableSet):
        _relink_collection(parent_state, attr_name, attr_value)


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
    parent_type = type(parent)
    for attr_name, attr_value in attrs.items():
        if inspection.ignore_attr_name(parent_type, attr_name):
            continue
        _relink_attribute(state, attr_name, attr_value, _seen)


def _scan_and_wrap_single_field(
    parent: Any,
    attr_name: str,
    attr_value: Any,
    _seen: dict[int, Any],
    max_depth: int,
) -> None:
    """Wrap a single field if necessary (internal)."""
    if attr_value is None or attr_name.startswith("_"):
        return
    if inspection.ignore_attr_name(type(parent), attr_name):
        return

    try:
        wrapped = wrap_mutable(
            parent,
            attr_value,
            _seen,
            key=attr_name,
            max_depth_limit=max_depth,
        )

        if wrapped is not attr_value:
            object.__setattr__(parent, attr_name, wrapped)

        if hasattr(wrapped, "_restore_tracking"):
            wrapped._restore_tracking(_seen=_seen)
    except (AttributeError, TypeError) as e:
        logger.debug("Failed to wrap attribute %s: %s", attr_name, e)
    except Exception as e:
        logger.warning(
            "Unexpected error wrapping attribute %s: %s", attr_name, e
        )


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

    # Resolve max_depth once at root scan
    max_depth = getattr(
        parent, "_max_nesting_depth", constants.DEFAULT_MAX_NESTING_DEPTH
    )

    for attr_name, attr_value in attrs.items():
        _scan_and_wrap_single_field(
            parent, attr_name, attr_value, _seen, max_depth
        )
