"""Safe wrapper for Python dataclasses."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar, overload

T = TypeVar("T")

if TYPE_CHECKING:
    dataclass = dataclasses.dataclass
else:

    @overload
    def dataclass(cls: type[T]) -> type[T]: ...

    @overload
    def dataclass(
        *args: Any, **kwargs: Any
    ) -> Callable[[type[T]], type[T]]: ...

    def dataclass(*args: Any, **kwargs: Any) -> Any:
        """
        A wrapper around standard dataclasses that enforces safe defaults
        for MutableMixin compatibility.

        Enforces:
        - eq=False: To use Identity Equality (is) instead of Value
          Equality (==).
          This prevents recursion loops and crashes in WeakKeyDictionary
          during initialization.
        - slots=False: To allow MutableMixin to inject tracking attributes
          (like _parents_store) at runtime.
        """
        kwargs.setdefault("slots", False)
        kwargs.setdefault("eq", False)
        return dataclasses.dataclass(*args, **kwargs)
