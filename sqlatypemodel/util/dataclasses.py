"""Safe wrapper for Python dataclasses."""

import dataclasses
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    dataclass = dataclasses.dataclass
else:
    def dataclass(*args: Any, **kwargs: Any) -> Any:
        """
        A wrapper around standard dataclasses that enforces safe defaults
        for MutableMixin compatibility.

        Enforces:
        - eq=False: To use Identity Equality (is) instead of Value Equality (==).
          This prevents recursion loops and crashes in WeakKeyDictionary
          during initialization.
        - slots=False: To allow MutableMixin to inject tracking attributes
          (like _parents_store) at runtime.
        """
        kwargs.setdefault("slots", False)
        kwargs.setdefault("eq", False)
        return dataclasses.dataclass(*args, **kwargs)
