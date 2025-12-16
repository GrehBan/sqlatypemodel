from typing import Any, Type, TypeVar
from sqlalchemy.ext.mutable import Mutable

M = TypeVar("M", bound="MutableMixin")


class MutableMixin(Mutable):
    """
    A mixin to enable change tracking for SQLAlchemy mutable types, specifically
    designed for use with Pydantic models.

    This mixin overrides `__setattr__` to automatically trigger SQLAlchemy's
    `self.changed()` event whenever an attribute is modified. This ensures that
    in-place modifications to the model (e.g., `model.field = value`) are
    detected by the SQLAlchemy session and persisted to the database upon commit.

    Usage:
        To use this mixin, inherit from it in your Pydantic model and register
        it with the SQLAlchemy column using `as_mutable()`.

        >>> class MyModel(MutableMixin, BaseModel):
        ...     field: int
        ...
        ... # In SQLAlchemy definition:
        ... col = mapped_column(MyModel.as_mutable(ModelType(MyModel)))
    """
    
    def __setattr__(self, name: str, value: Any) -> None:
        """
        Set an attribute on the instance and notify SQLAlchemy of the change.

        This method overrides the default attribute setting behavior to call
        `self.changed()`, marking the parent SQLAlchemy object as 'dirty'
        so that changes are saved during the next session commit.

        Args:
            name: The name of the attribute to set.
            value: The value to assign to the attribute.
        """
        if hasattr(self, '__dict__') and name in self.__dict__:
            old_value = self.__dict__.get(name)
            super().__setattr__(name, value)
            if old_value != value:
                self.changed()
        else:
            super().__setattr__(name, value)
    
    @classmethod
    def coerce(cls: Type[M], key: str, value: Any) -> M | None:
        """
        Convert a raw value into an instance of this class.

        This method is called by SQLAlchemy when a value is assigned to a
        mutable column. It ensures that the assigned value is properly converted
        to the tracked type. If the value is already an instance of this class,
        it is returned as-is.

        Args:
            key: The name of the column being assigned (used for error reporting).
            value: The raw value to convert.

        Returns:
            An instance of the class (M) or None if the input value is None.
            If conversion is not possible, it delegates to the superclass, which
            may raise a ValueError.
        """
        if value is None:
            return None

        if isinstance(value, cls):
            return value
        return super().coerce(key, value)