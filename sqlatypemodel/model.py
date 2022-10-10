"""
Simple model implementation, if you do not want use pydantic
"""

import json
from typing import Any, ClassVar, Dict, Set
from typing_extensions import dataclass_transform
from .protocols import JsonableModelProto


class Encoder(json.JSONEncoder):
    def encode(self, o: Any) -> str:
        if isinstance(o, JsonableModelProto):
            return o.json()
        return super().encode(o)


@dataclass_transform()
class Model(JsonableModelProto):
    ignore_upper: ClassVar[bool] = True

    def __init__(self, **kwargs: Any):
        self.__fields__: Set[str] = set()
        for k, v in kwargs.items():
            setattr(self, k, v)
            if self.ignore(k):
                continue
            self.__fields__.add(k)

    @classmethod
    def ignore(cls, name: str) -> bool:
        return (
            name.startswith('_')
            or name.endswith('__')
            or (
                cls.ignore_upper
                and name.isupper()
            )
        )

    def json(self) -> str:
        return json.dumps(
            self.dict(),
            cls=Encoder
        )

    def dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.__fields__}
