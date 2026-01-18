"""Introspection and validation logic for object attributes."""

from __future__ import annotations

from collections.abc import Hashable
from functools import lru_cache
from typing import Any, cast

from sqlalchemy.ext.mutable import MutableDict, MutableList, MutableSet

from sqlatypemodel.mixin._introspection_data import (
    _SKIP_ATTRS,
    _STARTSWITCH_SKIP_ATTRS,
)


def is_descriptor_property(descriptor: Any) -> bool:
    """Check if a descriptor is a property or read-only attribute.

    Args:
        descriptor: The attribute descriptor to check.

    Returns:
        True if the descriptor is a property or read-only, False otherwise.
    """
    if descriptor is None:
        return False
    if isinstance(descriptor, property):
        return True
    return hasattr(descriptor, "__get__") and not hasattr(
        descriptor, "__set__"
    )


def is_pydantic(obj: Any) -> bool:
    """Check if an object is a Pydantic model instance.

    Args:
        obj: The object to inspect.

    Returns:
        True if the object appears to be a Pydantic model.
    """
    cls = type(obj)
    return hasattr(cls, "model_fields") or hasattr(cls, "__fields__")


@lru_cache(maxsize=8192)
def _ignore_attr_name_inner(cls: type[Any], attr_name: str) -> bool:
    """Internal implementation with caching (increased cache size)."""
    # Fast checks first
    if attr_name in _SKIP_ATTRS:
        return True
    if attr_name.startswith(_STARTSWITCH_SKIP_ATTRS):
        return True

    # Expensive check: inspect class descriptor
    try:
        descriptor = getattr(cls, attr_name, None)
        if is_descriptor_property(descriptor) or callable(descriptor):
            return True
    except (AttributeError, TypeError):
        # Fallback for objects with broken getattr or unhashable types
        return False
    except Exception:
        # Unexpected error, assume not ignored for safety
        return False

    return False


def ignore_attr_name(cls: type[Any], attr_name: str) -> bool:
    """Fast check if an attribute should be ignored during scanning.

    This function uses caching to improve performance for repeated checks.

    Args:
        cls: The class of the object being inspected.
        attr_name: The name of the attribute.

    Returns:
        True if the attribute should be skipped, False otherwise.
    """
    # Cast to Hashable internally to satisfy mypy for lru_cache call
    return _ignore_attr_name_inner(cast(Hashable, cls), attr_name)


def extract_attrs_to_scan(instance: Any) -> dict[str, Any]:
    """Extract attributes from __dict__ and __slots__ for scanning (optimized).

    Args:
        instance: The object instance to extract attributes from.

    Returns:
        A dictionary mapping attribute names to their values.
    """
    attrs_to_scan: dict[str, Any] = {}

    # Try __dict__ first (most common case)
    try:
        obj_dict = object.__getattribute__(instance, "__dict__")
        if obj_dict:
            attrs_to_scan.update(obj_dict)
    except AttributeError:
        pass

    # Try __slots__ (less common)
    try:
        slots = object.__getattribute__(instance, "__slots__")
        if slots:
            for slot_name in slots:
                # Skip if already in __dict__
                if slot_name in attrs_to_scan:
                    continue
                try:
                    val = object.__getattribute__(instance, slot_name)
                    attrs_to_scan[slot_name] = val
                except AttributeError:
                    continue
    except AttributeError:
        pass

    return attrs_to_scan


def should_notify_change(old_value: Any, new_value: Any) -> bool:
    """Determine if a change notification is necessary (optimized).

    Args:
        old_value: The previous value of the attribute.
        new_value: The new value being assigned.

    Returns:
        True if a change notification should be fired, False otherwise.
    """
    # Identity check first (fastest)
    if old_value is new_value:
        return False

    # Mutable types always require notification
    # Use isinstance for accuracy (includes subclasses)
    if isinstance(
        old_value,
        list | dict | set | MutableList | MutableDict | MutableSet,
    ):
        return True

    # Equality check (might be expensive for custom objects)
    try:
        return bool(old_value != new_value)
    except (TypeError, ValueError):
        # If comparison is not supported between these types, assume change
        return True
    except Exception:
        # Unexpected error during comparison
        return True
