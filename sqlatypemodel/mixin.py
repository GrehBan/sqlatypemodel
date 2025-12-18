"""SQLAlchemy Mutable mixin for automatic change tracking."""
from __future__ import annotations

import inspect
import logging
import types
from typing import TYPE_CHECKING, Any, TypeVar, cast

from sqlalchemy.ext.mutable import (
    Mutable,
    MutableDict,
    MutableList,
    MutableSet,
)

if TYPE_CHECKING:
    from .model_type import ModelType

__all__ = [
    "MutableMixin",
]

logger = logging.getLogger(__name__)

M = TypeVar("M", bound="MutableMixin")

_PYDANTIC_INTERNAL_ATTRS: frozenset[str] = frozenset(
    {
        "_parents",
        "__weakref__",
        "model_config",
        "model_fields",
    }
)

# FIX: Исправлен синтаксис аннотации типа
_ATOMIC_TYPES: tuple[type, ...] = (
    str,
    int,
    float,
    bool,
    type(None),
    bytes,
    complex,
    frozenset,
)
DEFAULT_MAX_NESTING_DEPTH = 100


def safe_changed(self: Any, max_failures: int = 10) -> None:
    """Safely notify parent objects about changes, handling dead weak references.

    This function iterates through the `_parents` of the mutable object and
    triggers their change notification mechanisms. It catches and logs errors
    related to dead weak references or missing attributes to prevent
    runtime crashes during state propagation.

    Args:
        self: The mutable instance triggering the change.
        max_failures: The maximum number of notification failures allowed
            before stopping propagation. Defaults to 10.
    """
    try:
        parents_snapshot = tuple(self._parents.items())
    except (RuntimeError, AttributeError):
        return

    failure_count = 0

    for parent, key in parents_snapshot:
        if failure_count >= max_failures:
            break

        if parent is None:
            continue

        if hasattr(parent, "changed"):
            parent.changed()
            continue

        obj_ref = getattr(parent, "obj", None)
        if obj_ref is None or not callable(obj_ref):
            continue
        try:
            instance = obj_ref()
            if instance is None:
                logger.debug(
                    "Weak reference to parent "
                    "instance is dead, cannot flag change"
                )
                continue

            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(instance, key)

        except (ReferenceError, AttributeError) as e:
            logger.error(
                "Cannot flag change for %s.%s: "
                "weak reference dead or attribute missing",
                parent.__class__.__name__,
                key,
                e,
                exc_info=True,
            )
            failure_count += 1
        except Exception as e:
            logger.error(
                "Unexpected error in safe_changed() for %s.%s: %s",
                parent.__class__.__name__,
                key,
                e,
                exc_info=True,
            )
            failure_count += 1


class MutableMixin(Mutable):
    """Mixin for SQLAlchemy mutable types with automatic change tracking.

    This class provides the logic to intercept attribute changes,
    wrap mutable collections (lists, dicts, sets) into their SQLAlchemy-aware
    counterparts, and notify the ORM when changes occur deeply within the structure.
    """

    __hash__ = object.__hash__

    def changed(self) -> None:
        """Mark the object as changed and propagate the event to parents."""
        logger.debug("Change detected in %s instance", self.__class__.__name__)
        safe_changed(self)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Automatically register the subclass with the associated SQLAlchemy ModelType.

        Args:
            **kwargs: Configuration arguments.
                - auto_register (bool): If True, registers the class. Default True.
                - associate (type): Specific ModelType to associate with.

        Raises:
            TypeError: If the associated class is not a subclass of ModelType.
        """
        auto_register = kwargs.pop("auto_register", True)
        associate_cls = kwargs.pop("associate", None)

        if inspect.isabstract(cls):
            super().__init_subclass__(**kwargs)
            return

        if not auto_register:
            super().__init_subclass__(**kwargs)
            return

        from .model_type import ModelType

        associate = associate_cls or ModelType

        if not issubclass(associate, ModelType):
            raise TypeError(
                f"associate must be a subclass "
                f"of ModelType, got {associate!r}. "
                f"To use a custom TypeDecorator that "
                f"does not inherit from ModelType, "
                f"set 'auto_register=False' and register manually."
            )

        cast("type[ModelType[Any]]", associate).register_mutable(cls)
        super().__init_subclass__(**kwargs)

    def _scan_and_wrap_fields(self) -> None:
        """Recursively scan and wrap all attributes to ensure change tracking.

        This is typically called after deserialization from the database to ensure
        that the entire object graph is monitored for changes. It bypasses
        Pydantic validation for performance and compatibility.
        """
        # Prevent circular reference infinite loops
        seen = {id(self)}
        obj_dict = getattr(self, "__dict__", {})

        for attr_name, attr_value in obj_dict.items():
            if attr_name in _PYDANTIC_INTERNAL_ATTRS:
                continue

            wrapped = self._wrap_mutable(attr_value, seen)

            if wrapped is not attr_value:
                # Use object.__setattr__ to bypass Pydantic validation
                object.__setattr__(self, attr_name, wrapped)

    def __setattr__(self, name: str, value: Any) -> None:
        """Intercept attribute assignment to automatically wrap mutable structures.

        This method:
        1. Skips Pydantic internal attributes.
        2. Optimizes atomic types (int, str, etc.) by setting them directly.
        3. Wraps mutable collections (list, dict) in SQLAlchemy Mutable wrappers.
        4. Notifies SQLAlchemy of changes if the value actually changed.

        Args:
            name: The name of the attribute being set.
            value: The value being assigned.
        """
        # 1. Skip Pydantic internals and special attributes
        if (
            name.startswith(("__pydantic_", "_abc_", "__private_"))
            or name in _PYDANTIC_INTERNAL_ATTRS
        ):
            super().__setattr__(name, value)
            return

        # FIX: Removed redundant check for _PYDANTIC_INTERNAL_ATTRS here

        # 2. Optimization for atomic types
        if isinstance(value, _ATOMIC_TYPES):
            old_value = getattr(self, name, None)
            # Atomic types don't need wrapping, set directly
            super().__setattr__(name, value)

            if self._should_notify_change(old_value, value):
                self.changed()
            return

        # 3. Wrap mutable structures
        wrapped_value = self._wrap_mutable(value)
        old_value = getattr(self, name, None)

        if old_value is wrapped_value:
            return

        # 4. Set the wrapped value
        super().__setattr__(name, wrapped_value)

        # 5. SQLAlchemy / Pydantic consistency check
        try:
            stored_value = getattr(self, name)
            if stored_value is not wrapped_value:
                if isinstance(
                    wrapped_value, MutableList | MutableDict | MutableSet
                ):
                    object.__setattr__(self, name, wrapped_value)
        except AttributeError:
            pass

        # 6. Notify change
        if self._should_notify_change(old_value, wrapped_value):
            logger.debug(
                "%s.%s changed from %r to %r",
                self.__class__.__name__,
                name,
                old_value,
                wrapped_value,
            )
            self.changed()

    def _wrap_mutable(
        self,
        value: Any,
        seen: set[int] | None = None,
        depth: int = 0,
    ) -> Any:
        """Recursively convert Python collections into SQLAlchemy Mutable counterparts.

        Args:
            value: The value to inspect and wrap.
            seen: A set of object IDs already processed (to handle cycles).
            depth: Current recursion depth.

        Returns:
            The wrapped value (MutableList, MutableDict, etc.) or the original
            value if it doesn't need wrapping.
        """
        if seen is None:
            seen = set()

        obj_id = id(value)
        if obj_id in seen:
            if isinstance(value, MutableMixin):
                value._parents[self] = None
            return value

        if depth > DEFAULT_MAX_NESTING_DEPTH:
            return value

        seen.add(obj_id)

        if isinstance(value, MutableMixin):
            return self._wrap_mutable_mixin(value, seen, depth + 1)

        if isinstance(value, MutableList | MutableDict | MutableSet):
            return self._rewrap_mutable_collection(value)

        if isinstance(value, list):
            return self._wrap_list(value, seen, depth + 1)
        if isinstance(value, dict):
            return self._wrap_dict(value, seen, depth + 1)
        if isinstance(value, set | frozenset):
            return self._wrap_set(value, seen, depth + 1)
        return value

    def _rewrap_mutable_collection(
        self,
        value: MutableList[Any] | MutableDict[Any, Any] | MutableSet[Any],
    ) -> MutableList[Any] | MutableDict[Any, Any] | MutableSet[Any]:
        """Re-parent an existing Mutable collection to the current instance.

        Args:
            value: The existing mutable collection.

        Returns:
            The mutable collection with updated parenting and change handler.
        """
        if getattr(value, "changed", None) is not safe_changed:
            value.changed = types.MethodType(safe_changed, value)  # type: ignore[method-assign]

        value._parents[self] = None
        return value

    def _wrap_mutable_mixin(
        self, value: MutableMixin, seen: set[int], depth: int
    ) -> MutableMixin:
        """Wrap a nested MutableMixin instance and its attributes.

        Args:
            value: The nested MutableMixin instance.
            seen: Set of processed object IDs.
            depth: Recursion depth.

        Returns:
            The wrapped MutableMixin instance.
        """
        value._parents[self] = None
        obj_dict: dict[str, Any] = getattr(value, "__dict__", {})
        for attr_name, attr_value in obj_dict.items():
            if attr_name not in _PYDANTIC_INTERNAL_ATTRS:
                wrapped = self._wrap_mutable(attr_value, seen, depth)
                if wrapped is not attr_value:
                    super(MutableMixin, value).__setattr__(attr_name, wrapped)
        return value

    def _wrap_list(
        self, value: list[Any], seen: set[int], depth: int
    ) -> MutableList[Any]:
        """Convert a standard list to a SQLAlchemy MutableList.

        Args:
            value: The input list.
            seen: Set of processed object IDs.
            depth: Recursion depth.

        Returns:
            A MutableList containing wrapped elements.
        """
        wrapped = MutableList(
            [self._wrap_mutable(item, seen, depth) for item in value]
        )
        wrapped.changed = types.MethodType(safe_changed, wrapped)  # type: ignore[method-assign]
        wrapped._parents[self] = None
        return wrapped

    def _wrap_dict(
        self, value: dict[Any, Any], seen: set[int], depth: int
    ) -> MutableDict[Any, Any]:
        """Convert a standard dict to a SQLAlchemy MutableDict.

        Args:
            value: The input dictionary.
            seen: Set of processed object IDs.
            depth: Recursion depth.

        Returns:
            A MutableDict containing wrapped values.
        """
        wrapped = MutableDict(
            {k: self._wrap_mutable(v, seen, depth) for k, v in value.items()}
        )
        wrapped.changed = types.MethodType(safe_changed, wrapped)  # type: ignore[method-assign]
        wrapped._parents[self] = None
        return wrapped

    def _wrap_set(
        self, value: set[Any] | frozenset[Any], seen: set[int], depth: int
    ) -> MutableSet[Any]:
        """Convert a standard set or frozenset to a SQLAlchemy MutableSet.

        Args:
            value: The input set or frozenset.
            seen: Set of processed object IDs.
            depth: Recursion depth.

        Returns:
            A MutableSet containing wrapped elements.
        """
        wrapped = MutableSet(
            {self._wrap_mutable(item, seen, depth) for item in value}
        )
        wrapped.changed = types.MethodType(safe_changed, wrapped)  # type: ignore[method-assign]
        wrapped._parents[self] = None
        return wrapped

    @staticmethod
    def _should_notify_change(old_value: Any, new_value: Any) -> bool:
        """Determine if a change notification is necessary.

        Always returns True for mutable collections or if the equality check fails.

        Args:
            old_value: The previous value of the attribute.
            new_value: The new value being assigned.

        Returns:
            True if the change should trigger a notification, False otherwise.
        """
        if old_value is new_value:
            return False

        if isinstance(
            old_value,
            list
            | dict
            | set
            | frozenset
            | MutableList
            | MutableDict
            | MutableSet,
        ):
            return True

        try:
            return bool(old_value != new_value)
        except Exception:
            return True

    @classmethod
    def coerce(cls: type[M], key: str, value: Any) -> M | None:
        """SQLAlchemy hook to convert a raw Python value into the MutableMixin type.

        This method is called by SQLAlchemy when assigning a value to a column.
        It attempts to validate dictionaries using `model_validate` if available.

        Args:
            key: The name of the column.
            value: The raw value to convert.

        Returns:
            An instance of MutableMixin (or subclass), or None.
        """
        if value is None:
            return None
        if isinstance(value, cls):
            return value
        if isinstance(value, MutableList | MutableDict | MutableSet):
            return value  # type: ignore[return-value]
        if isinstance(value, dict) and hasattr(cls, "model_validate"):
            try:
                return cast(M, cls.model_validate(value))  # type: ignore[attr-defined]
            except Exception as e:
                logger.warning(
                    "Failed to coerce dict to %s using model_validate",
                    cls.__name__,
                    e,
                    exc_info=True,
                )
        return cast(M, value)
