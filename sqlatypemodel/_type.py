import json
from typing import Callable, Union

import sqlalchemy as sa
from .protocols import ModelProto, PydanticModelProto
from sqlalchemy.engine.default import DefaultDialect


class ModelType(sa.types.TypeDecorator):
    impl = sa.JSON

    hashable = False
    cache_ok = True

    def __init__(self,
                 model: ModelProto,
                 json_encoder: Union[Callable[[ModelProto],
                                              str], str] = 'json',
                 *args, **kwargs):
        super(ModelType, self).__init__(*args, **kwargs)
        self.model = model
        if isinstance(model, PydanticModelProto):
            self.loads = model.Config.json_loads
        else:
            self.loads = json.loads
        if isinstance(json_encoder, str):
            self.encoder: Callable[[ModelProto],
                                   str] = getattr(self.model,
                                                  json_encoder)
        else:
            self.encoder = json_encoder

    def process_bind_param(self, value: ModelProto, dialect: DefaultDialect):
        return self.encoder(value)

    def process_result_value(self, value: str, dialect: DefaultDialect):
        return self.model(
            **self.loads(value)
        )
