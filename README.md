# Tool for use class-based models as data types in sqlalchemy


## Example

```python
from sqlatypemodel import ModelType
from pydantic import BaseModel
from sqlalchemy import Column
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.engine import create_engine
from sqlalchemy.orm.session import Session

Base = declarative_base()
engine = create_engine(...)


class MessageModel(BaseModel):
    text: str


class User(Base):
    ...

    message = Column(ModelType(model=MessageModel))


with Session(engine) as session:
    user = User(
        message=MessageModel(text="Hello")
    )
    session.add(user)
    session.commit()

```

## If you do not want use pydantic
    BUT - it is very simplified and dumb implementation of model
```python
...
from sqlatypemodel import Model


class MessageModel(Model):
    text: str
```
