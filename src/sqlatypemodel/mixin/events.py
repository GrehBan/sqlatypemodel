"""Change notification logic and signal propagation."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import attributes

from sqlatypemodel.mixin.protocols import Trackable
from sqlatypemodel.mixin.state import MutableState

logger = logging.getLogger(__name__)

flag_modified = attributes.flag_modified


def _get_parents_snapshot(
    obj: Trackable, parents_dict: dict[Any, Any], max_retries: int
) -> list[tuple[Any, Any]] | None:
    """Safely take a snapshot of the parents dictionary."""
    for retry in range(max_retries):
        try:
            return list(parents_dict.items())
        except RuntimeError:
            if retry == max_retries - 1:
                logger.warning(
                    "Race condition in %s: failed to snapshot _parents.",
                    obj.__class__.__name__,
                )
                return None
        except AttributeError:
            return None
    return None


def _try_propagate_via_changed(parent: Any) -> bool | None:
    """Try to call 'changed' method.

    Returns True/False if handled, None otherwise."""
    changed_method = getattr(parent, "changed", None)
    if changed_method is not None:
        try:
            changed_method()
            return True
        except Exception as e:
            logger.error(
                "Failed to propagate change to parent %s: %s",
                type(parent),
                e,
                exc_info=True,
            )
            return False
    return None


def _try_propagate_via_obj_method(parent: Any, key: Any) -> bool | None:
    """Try to call 'obj' method (SQLAlchemy InstanceState)."""
    obj_method = getattr(parent, "obj", None)
    if obj_method is not None and callable(obj_method):
        try:
            instance = obj_method()
            if instance is not None and key:
                flag_modified(instance, key)
            return True
        except Exception as e:
            logger.error("Error flagging modified on SA model: %s", e)
            return False
    return None


def _try_propagate_via_flag_modified(parent: Any, key: Any) -> bool:
    """Last resort: flag_modified on parent directly."""
    if key:
        try:
            flag_modified(parent, key)
            return True
        except InvalidRequestError as e:
            logger.error("Error flagging modified on SA model: %s", e)
            return False
    return True


def _propagate_to_parent(parent_ref: Any, key: Any) -> bool:
    """Propagate change to a single parent. Returns True on success."""
    # Dereference MutableState (common case, check first)
    if isinstance(parent_ref, MutableState):
        parent = parent_ref.ref()
    else:
        parent = parent_ref

    if parent is None:
        return True

    # Try each strategy in order
    res = _try_propagate_via_changed(parent)
    if res is not None:
        return res

    res = _try_propagate_via_obj_method(parent, key)
    if res is not None:
        return res

    return _try_propagate_via_flag_modified(parent, key)


def safe_changed(
    obj: Trackable, max_failures: int = 10, max_retries: int = 3
) -> None:
    """Safely notify parent objects about changes (optimized).

    Handles race conditions when the `_parents` dictionary is modified
    during iteration by using a snapshot-and-retry approach.

    Args:
        obj: The trackable instance that changed.
        max_failures: Maximum allowed propagation failures before stopping.
        max_retries: Maximum attempts to snapshot parents dictionary.
    """
    try:
        parents_dict = object.__getattribute__(obj, "_parents")
    except AttributeError:
        return

    parents_snapshot = _get_parents_snapshot(obj, parents_dict, max_retries)
    if not parents_snapshot:
        return

    failure_count = 0
    for parent_ref, key in parents_snapshot:
        if failure_count >= max_failures:
            break

        if not _propagate_to_parent(parent_ref, key):
            failure_count += 1


@contextmanager
def batch_change_suppression(instance: Trackable) -> Iterator[None]:
    """Context manager to suppress change notifications.

    Increments a suppression counter. If modifications occur while suppressed,
    a single notification is fired upon exiting the outermost context.

    Args:
        instance: The trackable object to suppress notifications for.

    Yields:
        None
    """
    current_level = getattr(instance, "_change_suppress_level", 0)
    object.__setattr__(instance, "_change_suppress_level", current_level + 1)

    if not hasattr(instance, "_pending_change"):
        object.__setattr__(instance, "_pending_change", False)

    try:
        yield
    finally:
        new_level = getattr(instance, "_change_suppress_level", 1) - 1
        new_level = max(0, new_level)
        object.__setattr__(instance, "_change_suppress_level", new_level)

        if new_level == 0:
            is_pending = getattr(instance, "_pending_change", False)
            if is_pending:
                object.__setattr__(instance, "_pending_change", False)
                safe_changed(instance)


def mark_change_or_defer(instance: Trackable) -> bool:
    """Check if a change should be emitted or deferred.

    Args:
        instance: The trackable object.

    Returns:
        True if the change signal should be emitted immediately,
        False if it was suppressed/deferred.
    """
    suppress_level = getattr(instance, "_change_suppress_level", 0)

    if suppress_level > 0:
        object.__setattr__(instance, "_pending_change", True)
        return False

    return True
