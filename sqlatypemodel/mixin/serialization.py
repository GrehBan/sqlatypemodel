"""Pickle state management and serialization helpers."""

from typing import Any

from sqlatypemodel.util import constants


class ForceHashMixin:
    """Mixin to enforce object identity hashing.

    This ensures that objects can be used in weak references even if their
    default hashing behavior is modified or disabled (e.g., by Pydantic).
    """

    __hash__ = object.__hash__

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        """Ensure __hash__ is set to identity hash upon creation.

        Args:
            *args: Positional arguments for instance creation.
            **kwargs: Keyword arguments for instance creation.

        Returns:
            A new instance of the class.
        """
        if getattr(cls, "__hash__", None) is None:
            cls.__hash__ = ForceHashMixin.__hash__ # type: ignore [method-assign]
        return super().__new__(cls)


def cleanup_pickle_state(state: Any) -> Any:
    """Remove unpicklable attributes (like weakrefs) from the state dict.

    Args:
        state: The state object (usually a dict) to be cleaned.

    Returns:
        The cleaned state object safe for pickling.
    """
    if not isinstance(state, dict):
        return state

    keys_to_remove = constants._LIB_ATTRS
    for key in keys_to_remove:
        state.pop(key, None)

    if "__dict__" in state and isinstance(state["__dict__"], dict):
        for key in keys_to_remove:
            state["__dict__"].pop(key, None)

    return state


def manual_setstate(instance: Any, state: dict[str, Any]) -> None:
    """Manually restore state when parent class lacks __setstate__.

    Args:
        instance: The object instance to restore state into.
        state: The dictionary containing the state attributes.
    """
    for key, value in state.items():
        if key in constants._LIB_ATTRS:
            continue
        try:
            object.__setattr__(instance, key, value)
        except Exception:
            pass


def reset_trackable_state(instance: Any) -> None:
    """Reset library-specific tracking attributes to default values.

    This is typically called after unpickling to revive the object's
    change tracking capabilities.

    Args:
        instance: The object instance to reset.
    """
    if hasattr(instance, "_parents_store"):
        delattr(instance, "_parents_store")

    object.__setattr__(instance, "_change_suppress_level", 0)
    object.__setattr__(instance, "_pending_change", False)

    if not hasattr(instance, "_max_nesting_depth"):
        default_depth = getattr(
            instance.__class__,
            "_max_nesting_depth",
            constants.DEFAULT_MAX_NESTING_DEPTH,
        )
        object.__setattr__(instance, "_max_nesting_depth", default_depth)