"""Main Mixin module."""
from __future__ import annotations

import abc
import inspect
import logging
from contextlib import AbstractContextManager
from typing import TYPE_CHECKING, Any, TypeVar, cast
from weakref import WeakKeyDictionary

from sqlalchemy.ext.mutable import Mutable

from sqlatypemodel.mixin import events, inspection, serialization, wrapping
from sqlatypemodel.mixin.protocols import MutableMethods
from sqlatypemodel.mixin.state import MutableState
from sqlatypemodel.util import constants

__all__ = ("BaseMutableMixin", "MutableMixin", "LazyMutableMixin")

logger = logging.getLogger(__name__)

M = TypeVar("M", bound="BaseMutableMixin")


class BaseMutableMixin(MutableMethods, Mutable, abc.ABC):
    """Abstract Base Class for Mutable Mixins.
    
    Implements change tracking using State-based parent references.
    """

    _max_nesting_depth: int = constants.DEFAULT_MAX_NESTING_DEPTH
    _change_suppress_level: int = 0
    _pending_change: bool = False
    _state: MutableState[BaseMutableMixin]
    
    _parents_store: WeakKeyDictionary[Any, Any]

    if not TYPE_CHECKING:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            """Initialize the mixin with default tracking state."""
            object.__setattr__(self, "_change_suppress_level", 0)
            object.__setattr__(self, "_pending_change", False)
            super().__init__(*args, **kwargs)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Register subclass with SQLAlchemy ModelType."""
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
        """Notify observers that this object has changed."""
        if not events.mark_change_or_defer(self):
            return None
        return super().changed()

    def batch_changes(self) -> AbstractContextManager[None]:
        """Context manager to batch multiple changes."""
        return events.batch_change_suppression(self)

    def _should_skip_attr(self, attr_name: str) -> bool:
        """Check if an attribute should be skipped during wrapping."""
        return inspection.ignore_attr_name(type(self), attr_name)

    def _restore_tracking(self, _seen: Any | None = None) -> None:
        """Restore tracking for the object (abstract method)."""
        raise NotImplementedError

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restore object state from pickle."""
        if hasattr(super(), "__setstate__"):
            try:
                super().__setstate__(state)  # type: ignore
            except Exception:
                serialization.manual_setstate(self, state)
        else:
            serialization.manual_setstate(self, state)

        serialization.reset_trackable_state(self)
        self._restore_tracking()

    def __getstate__(self) -> dict[str, Any]:
        """Prepare object state for pickling."""
        state: dict[str, Any] = {}
        parent_handled = False
        if hasattr(super(), "__getstate__"):
            try:
                parent_state = super().__getstate__()  # type: ignore
                if isinstance(parent_state, dict):
                    state.update(parent_state)
                    parent_handled = True
                elif parent_state is not None:
                    return dict(serialization.cleanup_pickle_state(parent_state))
            except Exception:
                pass

        if not parent_handled:
            state.update(inspection.extract_attrs_to_scan(self))

        return dict(serialization.cleanup_pickle_state(state))

    def __setattr__(self, name: str, value: Any) -> None:
        if self._should_skip_attr(name):
            super().__setattr__(name, value)
            return

        try:
            old_value = object.__getattribute__(self, name)
        except AttributeError:
            old_value = constants.MISSING

        if old_value is value:
            return

        if type(value) in constants._ATOMIC_TYPES:
            object.__setattr__(self, name, value)
            if (
                old_value is not constants.MISSING and old_value != value
            ) or old_value is constants.MISSING:
                self.changed()
            return

        if wrapping.is_mutable_and_untracked(value):
            wrapped_value = wrapping.wrap_mutable(self, value, key=name)
            
            if hasattr(wrapped_value, "_parents"):
                wrapped_value._parents[self._state] = name
            
            object.__setattr__(self, name, wrapped_value)
            if (
                old_value is constants.MISSING
                or inspection.should_notify_change(old_value, wrapped_value)
            ):
                self.changed()
            return

        if hasattr(value, "_parents"):
            value._parents[self._state] = name
            object.__setattr__(self, name, value)

            if (
                old_value is not constants.MISSING
                and inspection.should_notify_change(old_value, value)
            ) or old_value is constants.MISSING:
                self.changed()
            return

        object.__setattr__(self, name, value)

        if (
            old_value is not constants.MISSING
            and inspection.should_notify_change(old_value, value)
        ) or old_value is constants.MISSING:
            self.changed()
    
    @classmethod
    def coerce(cls: type[M], key: str, value: Any) -> M | None:
        """Coerce value into the Mixin type."""
        if value is None:
            return None
        if isinstance(value, cls):
            return value
        if isinstance(value, constants._COLLECTION_TYPES):
            return value  # type: ignore

        if isinstance(value, dict) and hasattr(cls, "model_validate"):
            try:
                return cast(M, cls.model_validate(value))  # type: ignore
            except Exception as e:
                logger.warning(
                    "Failed to coerce dict to %s: %s", cls.__name__, e
                )

        return cast(M, value)


class MutableMixin(BaseMutableMixin, auto_register=False):
    """Standard (Eager) Implementation of MutableMixin."""

    if not TYPE_CHECKING:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            """Initialize and immediately restore tracking."""
            super().__init__(*args, **kwargs)
            self._restore_tracking()

    def _restore_tracking(self, _seen: Any | None = None) -> None:
        """Recursively scan and wrap all fields."""
        try:
            wrapping.scan_and_wrap_fields(self, _seen=_seen)
        except Exception as e:
            logger.warning("Failed to restore tracking: %s", e)


class LazyMutableMixin(BaseMutableMixin, auto_register=False):
    """Lazy Implementation of MutableMixin."""

    def _restore_tracking(self, _seen: Any | None = None) -> None:
        """No-op for lazy mixin."""
        return

    def __getattribute__(self, name: str) -> Any:
        """Retrieve attribute with Just-In-Time wrapping."""
        if name in constants._PYDANTIC_CLASS_ACCESS_ONLY:
            return getattr(type(self), name)

        value = object.__getattribute__(self, name)

        if inspection.ignore_attr_name(type(self), name):
            return value

        if not wrapping.is_mutable_and_untracked(value):
            return value

        wrapped = wrapping.wrap_mutable(self, value, key=name)
        
        if wrapped is not value:
            object.__setattr__(self, name, wrapped)
        return wrapped