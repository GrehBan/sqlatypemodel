"""Main Mixin module providing mutation tracking capabilities."""

from __future__ import annotations

import abc
import inspect
import logging
from contextlib import AbstractContextManager
from typing import TYPE_CHECKING, Any, TypeVar, cast
from weakref import WeakKeyDictionary

from sqlalchemy.ext.mutable import Mutable

from sqlatypemodel.mixin import events, inspection, serialization, wrapping
from sqlatypemodel.mixin._introspection_data import (
    _ATOMIC_TYPES,
    _PYDANTIC_CLASS_ACCESS_ONLY,
)
from sqlatypemodel.mixin.protocols import _COLLECTION_TYPES, MutableMethods
from sqlatypemodel.mixin.state import MutableState
from sqlatypemodel.util import constants

__all__ = ("BaseMutableMixin", "MutableMixin", "LazyMutableMixin")

logger = logging.getLogger(__name__)

M = TypeVar("M", bound="BaseMutableMixin")


class BaseMutableMixin(MutableMethods, Mutable, abc.ABC):  # type: ignore[misc]
    """Abstract Base Class for Mutable Mixins.

    Implements change tracking using State-based parent references. This
    class serves as the foundation for both Eager and Lazy mutation tracking
    strategies. It handles the interception of attribute access and
    assignment to detect changes in nested mutable structures.
    """

    _max_nesting_depth: int = constants.DEFAULT_MAX_NESTING_DEPTH
    _change_suppress_level: int = 0
    _pending_change: bool = False

    _parents_store: WeakKeyDictionary[MutableState[Any], str | int | None]

    if not TYPE_CHECKING:

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            """Initialize the mixin with default tracking state."""
            object.__setattr__(self, "_change_suppress_level", 0)
            object.__setattr__(self, "_pending_change", False)
            super().__init__(*args, **kwargs)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Register subclass with SQLAlchemy ModelType.

        Automatically registers the subclass with the associated SQLAlchemy
        type unless `auto_register=False` is passed.

        Args:
            **kwargs: Keyword arguments passed to __init_subclass__.
                Includes:

                - auto_register (bool): Whether to register with ModelType.
                  Defaults to True.
                - associate (type[ModelType]): Specific ModelType to
                  associate with.
        """
        auto_register = kwargs.pop("auto_register", True)
        associate_cls = kwargs.pop("associate", None)

        if not auto_register or inspect.isabstract(cls):
            super().__init_subclass__(**kwargs)
            return

        from sqlatypemodel.model_type import ModelType

        associate = associate_cls or ModelType

        if not issubclass(associate, ModelType):
            raise TypeError(
                f"associate must be a subclass of ModelType, got {associate!r}"
            )

        cast("type[ModelType[Any]]", associate).register_mutable(cls)
        super().__init_subclass__(**kwargs)

    def changed(self) -> None:
        """Notify observers that this object has changed.

        This method signals to SQLAlchemy that the object has been modified.
        It respects the change suppression level to support batched updates.
        """
        if not events.mark_change_or_defer(self):  # type: ignore[arg-type]
            return None
        return super().changed()

    def batch_changes(self) -> AbstractContextManager[None]:
        """Context manager to batch multiple changes.

        Prevents multiple `changed()` notifications during a block of code.
        Notifications are coalesced and sent once when the block exits.

        Returns:
            A context manager that suppresses change notifications.
        """
        return events.batch_change_suppression(self)  # type: ignore[arg-type]

    def _should_skip_attr(self, attr_name: str) -> bool:
        """Check if an attribute should be skipped during wrapping.

        Args:
            attr_name: The name of the attribute to check.

        Returns:
            True if the attribute should be ignored, False otherwise.
        """
        return inspection.ignore_attr_name(type(self), attr_name)

    def _restore_tracking(self, _seen: dict[int, Any] | None = None) -> None:
        """Restore tracking for the object (abstract method).

        Args:
            _seen: Optional dictionary to track visited objects during
                recursion.
        """
        raise NotImplementedError

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restore object state from pickle.

        Args:
            state: The dictionary state to restore.
        """
        parent_setstate = getattr(super(), "__setstate__", None)
        if parent_setstate:
            try:
                parent_setstate(state)
            except (TypeError, AttributeError, ValueError) as e:
                logger.debug("Parent __setstate__ failed, falling back: %s", e)
                serialization.manual_setstate(self, state)
            except Exception as e:
                logger.warning(
                    "Unexpected error in parent __setstate__: %s", e
                )
                serialization.manual_setstate(self, state)
        else:
            serialization.manual_setstate(self, state)

        serialization.reset_trackable_state(self)
        self._restore_tracking()

    def __getstate__(self) -> dict[str, Any]:
        """Prepare object state for pickling.

        Returns:
            A dictionary representing the object state.
        """
        state: dict[str, Any] = {}
        parent_handled = False
        parent_getstate = getattr(super(), "__getstate__", None)
        if parent_getstate:
            try:
                parent_state = parent_getstate()
                if isinstance(parent_state, dict):
                    state.update(parent_state)
                    parent_handled = True
                elif parent_state is not None:
                    return dict(
                        serialization.cleanup_pickle_state(parent_state)
                    )
            except (TypeError, AttributeError) as e:
                logger.debug("Parent __getstate__ failed: %s", e)
            except Exception as e:
                logger.warning(
                    "Unexpected error in parent __getstate__: %s", e
                )

        if not parent_handled:
            state.update(inspection.extract_attrs_to_scan(self))

        return dict(serialization.cleanup_pickle_state(state))

    def _notify_if_changed(self, old_value: Any, new_value: Any) -> None:
        """Helper to notify change if value actually changed."""
        if old_value is constants.MISSING or inspection.should_notify_change(
            old_value, new_value
        ):
            self.changed()

    def __setattr__(self, name: str, value: Any) -> None:
        """Set an attribute with automatic change tracking.

        Intercepts attribute assignment to wrap mutable values and notify
        SQLAlchemy of changes.

        Args:
            name: The name of the attribute.
            value: The value to set.
        """
        if self._should_skip_attr(name):
            super().__setattr__(name, value)
            return

        # Get old value (fast path)
        try:
            old_value = object.__getattribute__(self, name)
        except AttributeError:
            old_value = constants.MISSING

        # Short-circuit: if value hasn't changed, return early
        if old_value is value:
            return

        # Atomic type assignment (fast path)
        if type(value) in _ATOMIC_TYPES:
            object.__setattr__(self, name, value)
            if (old_value is not constants.MISSING and old_value != value) or (
                old_value is constants.MISSING
            ):
                self.changed()
            return

        # Get state once (avoid repeated calls)
        state = self._state  # type: ignore[misc]

        with state._lock:
            # Mutable/untracked type (needs wrapping)
            if wrapping.is_mutable_and_untracked(value):
                wrapped_value = wrapping.wrap_mutable(self, value, key=name)
                try:
                    parents = object.__getattribute__(
                        wrapped_value, "_parents"
                    )
                    parents[state] = name
                except AttributeError:
                    pass

                object.__setattr__(self, name, wrapped_value)
                self._notify_if_changed(old_value, wrapped_value)
                return

            # Already trackable (has _parents)
            try:
                parents = object.__getattribute__(value, "_parents")
                parents[state] = name
                object.__setattr__(self, name, value)
                self._notify_if_changed(old_value, value)
                return
            except AttributeError:
                pass

            # Regular attribute (no wrapping needed)
            object.__setattr__(self, name, value)
            self._notify_if_changed(old_value, value)

    @classmethod
    def coerce(cls: type[M], key: str, value: Any) -> M | None:
        """Coerce value into the Mixin type.

        Used by SQLAlchemy to convert raw values into the mutable type.

        Args:
            key: The key being coerced.
            value: The value to coerce.

        Returns:
            The coerced value or None.
        """
        if value is None:
            return None
        if isinstance(value, cls):
            return value
        if isinstance(value, _COLLECTION_TYPES):
            return cast(M, value)

        if isinstance(value, dict) and hasattr(cls, "model_validate"):
            try:
                validate_func = getattr(cls, "model_validate")
                return cast(M, validate_func(value))
            except Exception as e:
                logger.warning(
                    "Failed to coerce dict to %s: %s", cls.__name__, e
                )

        return cast(M, value)


class MutableMixin(BaseMutableMixin, auto_register=False):
    """Standard (Eager) Implementation of MutableMixin.

    This implementation eagerly scans and wraps all mutable fields upon
    initialization. It is suitable for write-heavy workloads or when fields
    are accessed frequently.
    """

    if not TYPE_CHECKING:

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            """Initialize and immediately restore tracking."""
            super().__init__(*args, **kwargs)
            self._restore_tracking()

    def _restore_tracking(self, _seen: dict[int, Any] | None = None) -> None:
        """Recursively scan and wrap all fields.

        Args:
            _seen: Optional dictionary to track visited objects.
        """
        try:
            wrapping.scan_and_wrap_fields(self, _seen=_seen)
            # Also ensure all children are linked to our new state after pickle
            wrapping.relink_descendants(self, _seen=_seen)
        except Exception as e:
            logger.warning("Failed to restore tracking: %s", e)


class LazyMutableMixin(BaseMutableMixin, auto_register=False):
    """Lazy Implementation of MutableMixin.

    This implementation defers the wrapping of mutable fields until they are
    first accessed. It is highly optimized for read-heavy workloads where only
    a subset of fields might be accessed.
    """

    def _restore_tracking(self, _seen: dict[int, Any] | None = None) -> None:
        """Restore tracking links after unpickling.

        For lazy mixin, this only needs to relink already-wrapped objects.

        Args:
            _seen: Optional dictionary to track visited objects.
        """
        # For lazy mixin, we only need to restore links for
        # already-wrapped objects
        try:
            wrapping.relink_descendants(self, _seen=_seen)
        except Exception as e:
            logger.warning("Failed to restore lazy tracking: %s", e)

    def __getattribute__(self, name: str) -> Any:
        """Retrieve attribute with Just-In-Time wrapping

        Wraps mutable attributes in tracking proxies upon first access.

        Args:
            name: The name of the attribute to retrieve.

        Returns:
            The attribute value, possibly wrapped in a tracking proxy.
        """
        # 1. Primary Fast Path: skip all internal/special attributes
        # immediately
        if name.startswith("_"):
            # We must let Pydantic and other libs handle their own
            # private/internal attrs
            if name in _PYDANTIC_CLASS_ACCESS_ONLY:
                return getattr(type(self), name)

            # Fast return for our own internal storage names
            if name in (
                "_parents_store",
                "_state_inst",
                "_parents",
                "_state",
            ):
                return object.__getattribute__(self, name)

            # For other '_' names, fallback to standard behavior
            return object.__getattribute__(self, name)

        value = object.__getattribute__(self, name)

        # 2. Secondary Fast Path: if it's already wrapped or atomic, return it
        # type(value) in _ATOMIC_TYPES is O(1) frozenset lookup
        if type(value) in _ATOMIC_TYPES:
            return value

        # Check if already a Mutable collection (which has _parents)
        # Use direct attribute check to avoid hasattr overhead
        try:
            object.__getattribute__(value, "_parents")
            return value
        except AttributeError:
            pass

        # 3. Slow Path: check if we should ignore it
        # This call is cached internally in inspection module
        if inspection.ignore_attr_name(type(self), name):
            return value

        # 4. Wrapping Path
        if not wrapping.is_mutable_and_untracked(value):
            return value

        with self._state._lock:
            # Re-check if it was wrapped while waiting for the lock
            current_val = object.__getattribute__(self, name)
            if current_val is not value:
                return current_val

            wrapped = wrapping.wrap_mutable(self, value, key=name)

            if wrapped is not value:
                object.__setattr__(self, name, wrapped)
            return wrapped
