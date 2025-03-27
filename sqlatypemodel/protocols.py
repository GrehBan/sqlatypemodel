from typing import Protocol, TypeVar, runtime_checkable

from sqlalchemy.engine.default import DefaultDialect

T = TypeVar("T")


@runtime_checkable
class PydanticModelProto(Protocol):
    def model_dump(self) -> str: ...

    @classmethod
    def model_validate(
        cls, value: "PydanticModelProto"
    ) -> "PydanticModelProto": ...
