"""Wrapper for attrs models.

This module provides a wrapper around `attrs.define` that ensures compatibility
with `MutableMixin` by enforcing safe defaults.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar, overload

T = TypeVar("T")

try:
    import attrs
except ImportError:
    raise ImportError(
        "To use 'sqlatypemodel.util.attrs', you must install the "
        "'attrs' library.\n"
        "Try: pip install attrs"
    )

if TYPE_CHECKING:
    define = attrs.define

else:

    @overload
    def define(cls: type[T]) -> type[T]:
        ...

    @overload
    def define(*args: Any, **kwargs: Any) -> Callable[[type[T]], type[T]]:
        ...

    def define(*args: Any, **kwargs: Any) -> Any:
        """Define an attrs class with safe defaults for mutation tracking.

        This wrapper enforces:

        - `eq=False`: Uses identity equality (`is`) instead of value equality.
          This ensures correct behavior with `WeakKeyDictionary` and prevents
          recursion loops.
        - `slots=False`: Allows `MutableMixin` to inject tracking attributes
          (like `_parents`) at runtime.

        Args:
            *args: Positional arguments passed to `attrs.define`.
            **kwargs: Keyword arguments passed to `attrs.define`.

        Returns:
            The decorated class.
        """
        kwargs.setdefault("slots", False)
        kwargs.setdefault("eq", False)

        return attrs.define(*args, **kwargs)
