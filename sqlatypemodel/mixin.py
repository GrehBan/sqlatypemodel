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

__all__ = (
    "MutableMixin",
)

logger = logging.getLogger(__name__)

M = TypeVar("M", bound="MutableMixin")

_ATOMIC_TYPES: frozenset[type] = frozenset(
    {
        str,
        int,
        float,
        bool,
        type(None),
        bytes,
        complex,
        frozenset,
    }
)

_STARTSWITCH_SKIP_ATTRS: tuple[str, ...] = (
    "_sa_",
    "__pydantic_",
    "_abc_",
    "__private_",
    "_pydantic_",
)

_PYTHON_INTERNAL_ATTRS: frozenset[str] = frozenset(
    {
        "__dict__",
        "__class__",
        "__weakref__",
        "__annotations__",
        "__slots__",
        "__module__",
        "__doc__",
        "__qualname__",
        "__orig_class__",
        "__args__",
        "__parameters__",
        "__signature__",
        "__dir__",
        "__hash__",
        "__eq__",
        "__repr__",
        "__str__",
        "__getattribute__",
        "__setattr__",
    }
)

_PYDANTIC_INTERNAL_ATTRS: frozenset[str] = frozenset(
    {
        "model_config",
        "model_fields",
        "model_computed_fields",
        "model_extra",
        "model_fields_set",
        "model_post_init",
        "__fields__",
        "__fields_set__",
        "__config__",
        "__validators__",
        "__pre_root_validators__",
        "__post_root_validators__",
        "__schema_cache__",
        "__json_encoder__",
        "__custom_root_type__",
        "__private_attributes__",
    }
)

_LIB_AND_SA_ATTRS: frozenset[str] = frozenset(
    {
        "_parents",
        "_max_nesting_depth",
        "_sa_instance_state",
        "_sa_adapter",
        "registry",
        "metadata",
    }
)

_SKIP_ATTRS: frozenset[str] = (
    _PYTHON_INTERNAL_ATTRS
    | _PYDANTIC_INTERNAL_ATTRS
    | _LIB_AND_SA_ATTRS
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
    _max_nesting_depth: int = DEFAULT_MAX_NESTING_DEPTH

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        """Ensure the class remains hashable even if decorators stripped it.

        Standard @dataclass and @attrs decorators set __hash__ to None
        if eq=True and frozen=False. We restore identity hashing here
        to ensure the object can be used in WeakKeyDictionary (_parents).
        """
        if cls.__hash__ is None:
            cls.__hash__ = object.__hash__
        return super().__new__(cls)

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

    def _should_skip_attr(self, attr_name: str) -> bool:
        """Check if the attribute should be skipped during scanning/wrapping.

        Optimized for speed: checks exact matches first (O(1)),
        then prefixes via tuple (optimized in C).
        """
        return (
            attr_name in _SKIP_ATTRS
            or attr_name.startswith(_STARTSWITCH_SKIP_ATTRS)
        )

    def _scan_and_wrap_fields(self) -> None:
        """Recursively scan and wrap all attributes to ensure change tracking.

        This is typically called after deserialization from the database to ensure
        that the entire object graph is monitored for changes. It bypasses
        Pydantic validation for performance and compatibility.
        """
        seen = {id(self)}

        for attr_name in dir(self):
            if self._should_skip_attr(attr_name):
                continue

            try:
                attr_value = getattr(self, attr_name, None)
            except Exception:
                continue

            if attr_value is None:
                continue
            
            if type(attr_value) in _ATOMIC_TYPES:
                continue

            wrapped = self._wrap_mutable(attr_value, seen)

            if wrapped is not attr_value:
                object.__setattr__(self, attr_name, wrapped)

    def __getstate__(self) -> Any:
        """Prepare state for pickling.
        
        Removes unpicklable WeakKeyDictionary and delegates to parent class.
        Compatible with Pydantic V2 which nests attributes in '__dict__'.
        """
        logger.debug("Preparing pickle state for %s", self.__class__.__name__)
        
        state: dict[str, Any] = {}
        parent_handled = False
        
        # 1. Try parent's __getstate__ first (Pydantic V2 / SQLAlchemy)
        if hasattr(super(), "__getstate__"):
            try:
                parent_state = super().__getstate__()  # type: ignore[misc]
                if parent_state is not None:
                    if isinstance(parent_state, dict):
                        state.update(parent_state)
                        parent_handled = True
                    else:
                        return parent_state
            except Exception as e:
                logger.debug(
                    "Parent __getstate__ failed or not compatible: %s", e
                )
        
        # 2. If parent didn't handle state, collect it ourselves
        if not parent_handled:
            if hasattr(self, "__dict__"):
                state.update(self.__dict__)
            
            if hasattr(self, "__slots__"):
                for slot in self.__slots__:
                    if slot in state:
                        continue
                    try:
                        state[slot] = getattr(self, slot)
                    except AttributeError:
                        pass
        
        # 3. Remove unpicklable tracking state (AGGRESSIVE CLEANUP)
        keys_to_remove = ("_parents", "_max_nesting_depth")
        
        # a) Remove from top level
        for key in keys_to_remove:
            state.pop(key, None)
            
        # b) [FIX] Remove from nested __dict__ (Pydantic V2 structure)
        if "__dict__" in state and isinstance(state["__dict__"], dict):
            for key in keys_to_remove:
                state["__dict__"].pop(key, None)
        
        return state


    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restore state from pickle.
        
        Re-initializes tracking state and delegates to parent class if needed.
        
        Args:
            state: Dictionary from __getstate__.
        """
        logger.debug("Restoring pickle state for %s", self.__class__.__name__)
        from weakref import WeakKeyDictionary
        
        # CRITICAL: Check if parent expects to handle __setstate__
        parent_handles_setstate = hasattr(super(), "__setstate__")
        
        if parent_handles_setstate:
            try:
                super().__setstate__(state)  # type: ignore[misc]
                
                object.__setattr__(self, "_parents", WeakKeyDictionary())
                
                if not hasattr(self, "_max_nesting_depth"):
                    object.__setattr__(
                        self, "_max_nesting_depth", 
                        self.__class__._max_nesting_depth
                    )
                
            except Exception as e:
                logger.warning(
                    "Parent __setstate__ failed for %s: %s. "
                    "Falling back to manual restoration.", 
                    self.__class__.__name__, e
                )
                self._manual_setstate(state)
        else:
            self._manual_setstate(state)
        
        try:
            self._scan_and_wrap_fields()
        except Exception as e:
            logger.debug(
                "Could not re-wrap fields after unpickle for %s: %s", 
                self.__class__.__name__, e
            )


    def _manual_setstate(self, state: dict[str, Any]) -> None:
        """Manually restore state when parent doesn't have __setstate__.
        
        This is a helper method extracted for clarity.
        
        Args:
            state: Dictionary of attributes to restore.
        """
        from weakref import WeakKeyDictionary
        
        for key, value in state.items():
            if key in ("_parents", "_max_nesting_depth"):
                continue
            
            try:
                object.__setattr__(self, key, value)
            except Exception as e:
                logger.debug(
                    "Could not restore attribute '%s' for %s: %s", 
                    key, self.__class__.__name__, e
                )
        
        object.__setattr__(self, "_parents", WeakKeyDictionary())
        
        if not hasattr(self, "_max_nesting_depth"):
            object.__setattr__(
                self, "_max_nesting_depth", 
                self.__class__._max_nesting_depth
            )

    def __setattr__(self, name: str, value: Any) -> None:
        """Intercept attribute assignment to automatically wrap mutable structures.

        This method:
        1. Skips internal attributes that should not be tracked.
        2. Optimizes atomic types (int, str, etc.) by setting them directly.
        3. Wraps mutable collections (list, dict) in SQLAlchemy Mutable wrappers.
        4. Notifies SQLAlchemy of changes if the value actually changed.

        Args:
            name: The name of the attribute being set.
            value: The value being assigned.
        """
        if self._should_skip_attr(name):
            super().__setattr__(name, value)
            return

        old_value = getattr(self, name, None)
        if old_value is value:
            return

        if isinstance(value, MutableMixin):
            value._parents[self] = name
            object.__setattr__(self, name, value)
            if self._should_notify_change(old_value, value):
                self.changed()
            return

        wrapped_value = self._wrap_mutable(value)

        object.__setattr__(self, name, wrapped_value)

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

        if depth > self._max_nesting_depth:
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
            value.changed = types.MethodType(safe_changed, value) # type: ignore[assignment]

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

        attrs_to_scan: set[str] = set()
        
        if hasattr(value, "__dict__"):
            attrs_to_scan.update(value.__dict__.keys())
        
        if hasattr(value, "__slots__"):
            attrs_to_scan.update(value.__slots__)

        for attr_name in attrs_to_scan:
            if self._should_skip_attr(attr_name):
                continue
            
            try:
                attr_value = getattr(value, attr_name)
            except Exception:
                continue

            if type(attr_value) in _ATOMIC_TYPES:
                continue

            wrapped = self._wrap_mutable(attr_value, seen, depth)
            
            if wrapped is not attr_value:
                object.__setattr__(value, attr_name, wrapped)
                
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
        wrapped.changed = types.MethodType(safe_changed, wrapped) # type: ignore[assignment]
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
        wrapped.changed = types.MethodType(safe_changed, wrapped) # type: ignore[assignment]
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
        wrapped.changed = types.MethodType(safe_changed, wrapped) # type: ignore[assignment]
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
        if (
            isinstance(value, dict)
            and hasattr(cls, "model_validate")
            and callable(cls.model_validate) # type: ignore[attr-defined]
        ):
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