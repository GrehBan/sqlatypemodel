from typing import Any, Callable, Protocol, Type, runtime_checkable


class ModelProto(Protocol):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        ...


@runtime_checkable
class JsonableModelProto(ModelProto, Protocol):
    def json(self, *args: Any, **kwargs: Any) -> str:
        ...


class PydanticConfigProto(Protocol):
    json_loads: Callable[[str], Any]


@runtime_checkable
class PydanticModelProto(JsonableModelProto, Protocol):
    Config: Type[PydanticConfigProto]
