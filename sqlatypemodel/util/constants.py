"""Static constants and configuration for the library."""

import datetime
import uuid
from decimal import Decimal
from typing import Final

from sqlalchemy.ext.mutable import MutableDict, MutableList, MutableSet

DEFAULT_MAX_NESTING_DEPTH: Final[int] = 100

MISSING: Final[object] = object()

_ATOMIC_TYPES: Final[frozenset[type]] = frozenset(
    {
        str,
        int,
        float,
        bool,
        type(None),
        bytes,
        complex,
        frozenset,
        uuid.UUID,
        datetime.date,
        datetime.time,
        Decimal,
    }
)

_COLLECTION_TYPES: Final[tuple[type, ...]] = (
    MutableList,
    MutableDict,
    MutableSet,
)

_STARTSWITCH_SKIP_ATTRS: Final[tuple[str, ...]] = (
    "_",
    "_sa_",
    "__pydantic_",
    "_abc_",
    "__private_",
    "_pydantic_",
)

_LIB_ATTRS: Final[frozenset[str]] = frozenset(
    {
        "_parents",
        "_max_nesting_depth",
        "_change_suppress_level",
        "_pending_change",
        "_parents_store",
    }
)

_PYDANTIC_ATTRS: Final[frozenset[str]] = frozenset(
    {
        "model_config",
        "model_fields",
        "model_computed_fields",
        "model_extra",
        "model_fields_set",
        "model_post_init",
        "model_construct",
        "model_copy",
        "model_dump",
        "model_dump_json",
        "model_json_schema",
        "model_validate",
        "model_validate_json",
        "model_validate_strings",
        "model_rebuild",
        "__fields__",
        "__pydantic_private__",
        "__pydantic_extra__",
        "__pydantic_fields_set__",
        "__fields_set__",
        "__config__",
        "__validators__",
        "__pre_root_validators__",
        "__post_root_validators__",
        "__schema_cache__",
        "__json_encoder__",
        "__custom_root_type__",
        "__private_attributes__",
        "__values__",
        "dict",
        "json",
        "copy",
        "parse_obj",
        "parse_raw",
        "parse_file",
        "from_orm",
        "schema",
        "schema_json",
        "construct",
        "validate",
        "update_forward_refs",
    }
)

_DATACLASS_ATTRS: Final[frozenset[str]] = frozenset(
    {
        "__dataclass_fields__",
        "__dataclass_params__",
        "__post_init__",
    }
)

_ATTRS_ATTRS: Final[frozenset[str]] = frozenset(
    {
        "__attrs_attrs__",
        "__attrs_own_setattr__",
        "__attrs_post_init__",
        "__attrs_init__",
    }
)

_PYDANTIC_CLASS_ACCESS_ONLY: Final[frozenset[str]] = frozenset(
    {
        "model_fields",
        "model_config",
        "model_computed_fields",
        "__pydantic_core_schema__",
        "__pydantic_validator__",
        "__pydantic_serializer__",
        "__pydantic_decorators__",
        "__pydantic_generic_metadata__",
        "__pydantic_parent_namespace__",
        "__fields__",
        "__config__",
        "__validators__",
        "__pre_root_validators__",
        "__post_root_validators__",
        "__schema_cache__",
        "__json_encoder__",
        "__custom_root_type__",
        "__signature__",
    }
)

_SKIP_ATTRS: Final[frozenset[str]] = frozenset(
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
        "__match_args__",  # Often present in modern python classes
        "_sa_instance_state",
        "_sa_adapter",
        "registry",
        "metadata",
    }
    | _LIB_ATTRS
    | _PYDANTIC_ATTRS
    | _DATACLASS_ATTRS
    | _ATTRS_ATTRS
)