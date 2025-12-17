"""SQLAlchemy Mutable mixin for automatic change tracking."""
from __future__ import annotations

import types
from typing import TYPE_CHECKING, Any, TypeVar

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

M = TypeVar("M", bound="MutableMixin")

_PYDANTIC_INTERNAL_ATTRS: frozenset[str] = frozenset({
    "_parents",
    "__weakref__",
    "__pydantic_private__",
    "__pydantic_extra__",
    "__pydantic_fields_set__",
    "__pydantic_validator__",
    "__pydantic_decorators__",
    "model_config",
    "model_fields",
    "__pydantic_fields__",
    "__pydantic_serializer__",
})


def safe_changed(self):
    """Custom changed() implementation injected into Mutable collections."""
    # 1. Propagate to MutableMixin parents
    for parent, key in list(self._parents.items()):
        if hasattr(parent, "changed"):
            parent.changed()
            continue
            
        # 2. Propagate to SQLAlchemy ORM parents
        if (obj := getattr(parent, "obj", None)) and callable(obj):
            from sqlalchemy.orm.attributes import flag_modified
            try:
                flag_modified(obj(), key)
            except Exception:
                pass


class MutableMixin(Mutable):
    """Mixin for SQLAlchemy mutable types with automatic change tracking."""

    __hash__ = object.__hash__

    def changed(self) -> None:
        """Notify SQLAlchemy of mutations."""
        safe_changed(self)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        from .model_type import ModelType
        associate: type[ModelType] = kwargs.pop("associate", ModelType)
        associate.register_mutable(cls)
        super().__init_subclass__(**kwargs)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in _PYDANTIC_INTERNAL_ATTRS:
            super().__setattr__(name, value)
            return

        wrapped_value = self._wrap_mutable(value)
        old_value = getattr(self, name, None)

        if old_value is wrapped_value:
            return

        super().__setattr__(name, wrapped_value)
        try:
            stored_value = getattr(self, name)
            if stored_value is not wrapped_value:
                if isinstance(wrapped_value, (MutableList, MutableDict, MutableSet)):
                    object.__setattr__(self, name, wrapped_value)
        except AttributeError:
            pass

        # 4. Notify change
        if self._should_notify_change(old_value, wrapped_value):
            self.changed()

    def _wrap_mutable(self, value: Any, seen: set[int] | None = None) -> Any:
        if seen is None:
            seen = set()

        obj_id = id(value)
        if obj_id in seen:
            return value
        seen.add(obj_id)

        if isinstance(value, MutableMixin):
            return self._wrap_mutable_mixin(value, seen)

        if isinstance(value, (MutableList, MutableDict, MutableSet)):
            if getattr(value, "changed", None) != safe_changed:
                value.changed = types.MethodType(safe_changed, value)
            value._parents[self] = None
            return value

        if isinstance(value, list):
            return self._wrap_list(value, seen)
        if isinstance(value, dict):
            return self._wrap_dict(value, seen)
        if isinstance(value, (set, frozenset)):
            return self._wrap_set(value, seen)

        return value

    def _wrap_mutable_mixin(self, value: MutableMixin, seen: set[int]) -> MutableMixin:
        value._parents[self] = None
        obj_dict = getattr(value, "__dict__", {})
        for attr_name, attr_value in obj_dict.items():
            if attr_name not in _PYDANTIC_INTERNAL_ATTRS:
                wrapped = self._wrap_mutable(attr_value, seen)
                if wrapped is not attr_value:
                    super(MutableMixin, value).__setattr__(attr_name, wrapped)
        return value

    def _wrap_list(self, value: list, seen: set[int]) -> MutableList:
        wrapped = MutableList([self._wrap_mutable(item, seen) for item in value])
        wrapped.changed = types.MethodType(safe_changed, wrapped)
        wrapped._parents[self] = None
        return wrapped

    def _wrap_dict(self, value: dict, seen: set[int]) -> MutableDict:
        wrapped = MutableDict({
            k: self._wrap_mutable(v, seen) for k, v in value.items()
        })
        wrapped.changed = types.MethodType(safe_changed, wrapped)
        wrapped._parents[self] = None
        return wrapped

    def _wrap_set(self, value: set | frozenset, seen: set[int]) -> MutableSet:
        wrapped = MutableSet({
            self._wrap_mutable(item, seen) for item in value
        })
        wrapped.changed = types.MethodType(safe_changed, wrapped)
        wrapped._parents[self] = None
        return wrapped

    @staticmethod
    def _should_notify_change(old_value: Any, new_value: Any) -> bool:
        if old_value is new_value:
            return False
        if isinstance(old_value, (MutableList, MutableDict, MutableSet)):
            return True
        try:
            return old_value != new_value
        except Exception:
            return True

    @classmethod
    def coerce(cls: type[M], key: str, value: Any) -> M | None:
        if value is None:
            return None
        if isinstance(value, cls):
            return value
        if isinstance(value, (MutableList, MutableDict, MutableSet)):
            return value  # type: ignore[return-value]
        if isinstance(value, dict) and hasattr(cls, "model_validate"):
            try:
                return cls.model_validate(value)  # type: ignore[attr-defined]
            except Exception:
                pass
        return value  # type: ignore[return-value]