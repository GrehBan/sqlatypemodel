from typing import TYPE_CHECKING, Any

try:
    import attrs
except ImportError:
    raise ImportError(
        "To use 'sqlatypemodel.util.attrs', you must install the 'attrs' library.\n"
        "Try: pip install attrs"
    )

if TYPE_CHECKING:
    define = attrs.define

else:
    def define(*args: Any, **kwargs: Any) -> Any:
        """
        Wrapper around attrs.define that sets safe defaults for SQLAlchemy Mutable models.
        
        Defaults applied:
          - slots=False: Required for MutableMixin to inject tracking state.
          - eq=False: Required for MutableMixin's identity-based hashing.
        """
        kwargs.setdefault("slots", False)
        kwargs.setdefault("eq", False)
        
        return attrs.define(*args, **kwargs)
