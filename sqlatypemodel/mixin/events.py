"""Change notification logic and signal propagation."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy.orm import attributes

from sqlatypemodel.mixin.protocols import Trackable

logger = logging.getLogger(__name__)

flag_modified = attributes.flag_modified


def safe_changed(
    self: Trackable, max_failures: int = 10, max_retries: int = 3
) -> None:
    """Safely notify parent objects about changes.

    Handles race conditions when the `_parents` dictionary is modified
    during iteration by using a snapshot-and-retry approach.

    Args:
        self: The trackable instance that changed.
        max_failures: Maximum allowed propagation failures before stopping.
        max_retries: Maximum attempts to snapshot parents dictionary.
    """
    if not hasattr(self, "_parents"):
        return

    parents_snapshot: tuple[tuple[Any, str | None], ...] | None = None

    for retry in range(max_retries):
        try:
            parents_snapshot = tuple(self._parents.items())
            break
        except RuntimeError:
            if retry == max_retries - 1:
                logger.warning(
                    "Race condition in %s: failed to snapshot _parents.",
                    self.__class__.__name__,
                )
                return
            continue
        except AttributeError:
            return

    if not parents_snapshot:
        return

    failure_count = 0

    for parent, key in parents_snapshot:
        if failure_count >= max_failures:
            break

        if parent is None:
            continue

        changed_method = getattr(parent, "changed", None)
        if callable(changed_method):
            try:
                changed_method()
                continue
            except Exception as e:
                logger.error(
                    "Failed to propagate change to parent %s: %s",
                    type(parent),
                    e,
                )
                failure_count += 1
                continue

        obj_ref = getattr(parent, "obj", None)
        if obj_ref is not None and callable(obj_ref):
            try:
                instance = obj_ref()
                if instance is not None:
                    if key:
                        flag_modified(instance, key)
            except (ReferenceError, AttributeError):
                failure_count += 1
            except Exception as e:
                logger.error("Error flagging modified on SA model: %s", e)
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