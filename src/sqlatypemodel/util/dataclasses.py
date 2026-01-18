"""Safe wrapper for Python dataclasses.

This module provides a wrapper around `dataclasses.dataclass` that ensures
compatibility with `MutableMixin` by enforcing safe defaults.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar, overload

T = TypeVar("T")

if TYPE_CHECKING:
    dataclass = dataclasses.dataclass
else:

    @overload
    def dataclass(cls: type[T]) -> type[T]:
        ...

    @overload
    def dataclass(*args: Any, **kwargs: Any) -> Callable[[type[T]], type[T]]:
        ...

    def dataclass(*args: Any, **kwargs: Any) -> Any:
        """Create a dataclass with safe defaults for mutation tracking.

        This wrapper enforces:

        - `eq=False`: Uses identity equality (`is`) instead of value equality.
          This prevents recursion loops during initialization and ensures
          correct behavior with `WeakKeyDictionary`.
        - `slots=False`: Allows `MutableMixin` to inject tracking attributes
          (like `_parents`) at runtime.

        Args:
            *args: Positional arguments passed to `dataclasses.dataclass`.
            **kwargs: Keyword arguments passed to `dataclasses.dataclass`.

        Returns:
            The decorated class.
        """
        kwargs.setdefault("slots", False)
        kwargs.setdefault("eq", False)
        return dataclasses.dataclass(*args, **kwargs)
