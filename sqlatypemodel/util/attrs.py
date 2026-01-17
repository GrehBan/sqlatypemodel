"""
Wrapper around attrs.define that sets safe defaults for SQLAlchemy
Mutable models.

Defaults applied:
  - slots=False: Required for MutableMixin to inject tracking state.
  - eq=False: Required for MutableMixin's identity-based hashing.
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
    def define(cls: type[T]) -> type[T]: ...

    @overload
    def define(*args: Any, **kwargs: Any) -> Callable[[type[T]], type[T]]: ...

    def define(*args: Any, **kwargs: Any) -> Any:

        kwargs.setdefault("slots", False)
        kwargs.setdefault("eq", False)

        return attrs.define(*args, **kwargs)
