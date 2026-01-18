"""Pickle state management and serialization helpers."""

from __future__ import annotations

from typing import Any

from sqlatypemodel.mixin._introspection_data import _LIB_ATTRS
from sqlatypemodel.util import constants


def cleanup_pickle_state(state: Any) -> Any:
    """Remove unpicklable attributes (like weakrefs) from the state dict.

    Args:
        state: The state object (usually a dict) to be cleaned.

    Returns:
        The cleaned state object safe for pickling.
    """
    if not isinstance(state, dict):
        return state

    # Optimize: Fast bulk removal if possible, otherwise individual pop
    # pop(k, None) is safe and fast
    for key in _LIB_ATTRS:
        state.pop(key, None)

    # Handle nested __dict__ which some pickle implementations use
    instance_dict = state.get("__dict__")
    if instance_dict and isinstance(instance_dict, dict):
        for key in _LIB_ATTRS:
            instance_dict.pop(key, None)

    return state


def manual_setstate(instance: Any, state: dict[str, Any]) -> None:
    """Manually restore state when parent class lacks __setstate__.

    Args:
        instance: The object instance to restore state into.
        state: The dictionary containing the state attributes.
    """
    # Optimize: Filter keys first to avoid repeated checks inside loop if
    # state is large. However, for typical object sizes, simple iteration is
    # faster than set operations
    for key, value in state.items():
        if key in _LIB_ATTRS:
            continue
        try:
            object.__setattr__(instance, key, value)
        except (AttributeError, TypeError):
            # Attribute might be read-only or descriptor that fails on set
            pass


def reset_trackable_state(instance: Any) -> None:
    """Reset library-specific tracking attributes to default values.

    This is typically called after unpickling to revive the object's
    change tracking capabilities.

    Args:
        instance: The object instance to reset.
    """
    # Optimize: Use EAFP (Easier to Ask for Forgiveness than Permission)
    # This avoids double lookup (hasattr + delattr)
    try:
        delattr(instance, "_parents_store")
    except AttributeError:
        pass

    try:
        delattr(instance, "_state_inst")
    except AttributeError:
        pass

    object.__setattr__(instance, "_change_suppress_level", 0)
    object.__setattr__(instance, "_pending_change", False)

    # Use getattr with default to avoid exception handling logic for
    # max_nesting_depth
    if getattr(instance, "_max_nesting_depth", None) is None:
        default_depth = getattr(
            instance.__class__,
            "_max_nesting_depth",
            constants.DEFAULT_MAX_NESTING_DEPTH,
        )
        object.__setattr__(instance, "_max_nesting_depth", default_depth)
