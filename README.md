# SQLAlchemy Model Type

Typed JSON fields for SQLAlchemy **with automatic mutation tracking**.

SQLAlchemy does not detect in-place changes inside JSON columns.
This library fixes that, while letting you work with fully typed Python models
(Pydantic, dataclasses, or custom classes).


## Key Features

* **Seamless Integration:** Store Pydantic models directly in SQLAlchemy columns.
* **Mutation Tracking:** Built-in `MutableMixin` ensures changes to fields (e.g., `user.config.theme = "dark"`) are automatically detected and saved.
* **Automatic Serialization:** Converts models to JSON dictionaries when saving.
* **Automatic Validation:** Validates and converts JSON back into Pydantic models when reading.
* **JSON Operator Support:** Fully compatible with SQLAlchemy JSON operators
  (e.g., `->`, `->>`), since data is stored as native JSON/JSONB.

## The Problem

```python
user.message.text = "Updated"
session.commit()  # ❌ NOT persisted by default SQLAlchemy
```

## The Solution

```python
user.message.text = "Updated"
session.commit()  # ✅ persisted with sqlatypemodel
```

## When NOT to use this library

- You need to run complex SQL queries over JSON fields
- Your data is highly relational and should be normalized
- You don't need mutation tracking for JSON columns

## Comparison

| Solution | Typed | Mutation Tracking | ORM-agnostic |
|--------|------|------------------|-------------|
| Raw JSON | ❌ | ❌ | ✅ |
| Custom TypeDecorator | ⚠️ | ⚠️ manual | ✅ |
| SQLModel | ✅ | ❌ | ❌ |
| **sqlatypemodel** | ✅ | ✅ | ✅ |


## Installation

```bash
pip install sqlatypemodel
```
## Quick Start

Below is a complete, runnable example demonstrating how to define a model, save it, and retrieve it.

### 1. Standard Pydantic Integration

```python
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, String
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase, Session
from sqlatypemodel import ModelType, MutableMixin

# 1. Setup SQLAlchemy (using in-memory SQLite for this demo)
engine = create_engine("sqlite:///")

class Base(DeclarativeBase):
    pass

# 2. Define your Pydantic Model with MutableMixin
# Note: MutableMixin must be the first parent class
class MessageModel(MutableMixin, BaseModel):
    text: str
    priority: int = Field(default=1)

# 3. Define your SQLAlchemy Entity
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    
    # 4. Use as_mutable to enable change tracking
    message: Mapped[MessageModel] = mapped_column(
        MessageModel.as_mutable(ModelType(MessageModel))
    )

# Create tables
Base.metadata.create_all(engine)

# 5. Usage
with Session(engine) as session:
    # --- Create ---
    new_user = User(
        name="Alice",
        message=MessageModel(text="Hello World", priority=5)
    )
    session.add(new_user)
    session.commit()

    # --- Update (Mutation) ---
    # Because of MutableMixin, this change is detected automatically!
    new_user.message.text = "Updated Text"
    session.commit()

    # --- Read ---
    stored_user = session.query(User).filter_by(name="Alice").first()
    print(f"Content: {stored_user.message.text}") 
    # Output: Updated Text
```
### 2. Custom Serialization (Legacy or Non-Pydantic Classes)

If you use standard Python dataclasses, legacy classes, or custom serialization logic, you can explicitly provide the json_dumps and json_loads arguments.

### Using Python Dataclasses

```python
from dataclasses import dataclass, asdict
from typing import Any

@dataclass
class ConfigData(MutableMixin):
    theme: str
    retries: int

def load_config(data: dict[str, Any]) -> ConfigData:
    return ConfigData(**data)

# Usage in SQLAlchemy model
# ...
settings: Mapped[ConfigData] = mapped_column(
    ConfigData.as_mutable(
        ModelType(
            ConfigData,
            json_dumps=asdict,      # Standard library function
            json_loads=load_config  # Custom loader function
        )
    )
)
```

### Using Custom Methods or Strings

You can point to serialization methods directly or refer to them by string name (useful if the methods are defined on the class itself).

```python
class CustomMessage(MutableMixin):
    def __init__(self, text: str, priority: int = 1):
        self.text = text
        self.priority = priority

    def to_json(self) -> dict[str, Any]:
        return {"text": self.text, "priority": self.priority}

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "CustomMessage":
        return cls(text=data["text"], priority=data["priority"])

# Usage in SQLAlchemy model
# ...
message: Mapped[CustomMessage] = mapped_column(
    CustomMessage.as_mutable(
        ModelType(
            CustomMessage,
            json_dumps="to_json",    # Will call instance.to_json()
            json_loads="from_json"   # Will call CustomMessage.from_json()
        )
    )
)
```
## Why use `MutableMixin`?
By default, SQLAlchemy only detects changes when you assign a new object to a column:

```python
# Without MutableMixin:
user.message.text = "New" # SQLAlchemy ignores this! 
session.commit()          # Nothing saved.

user.message = MessageModel(...) # This works (replaced entire object)
```

With `MutableMixin` and `.as_mutable()`, SQLAlchemy tracks attribute changes (via `__setattr__`), so modifying a single field works as expected:

```python
# With MutableMixin:
user.message.text = "New" # Detected!
session.commit()          # Saved to DB.
```

## Type Hinting

To ensure static analysis tools (mypy, PyCharm, VS Code) work correctly, separate the Python type from the Database configuration.

### Required Field:
```python
message: Mapped[MessageModel] = mapped_column(
    MessageModel.as_mutable(ModelType(MessageModel))
)
```
### Nullable Field:
```python
from typing import Optional

# Note: Use `| None` inside Mapped and `nullable=True` inside mapped_column
message: Mapped[Optional[MessageModel]] = mapped_column(
    MessageModel.as_mutable(ModelType(MessageModel)), 
    nullable=True
)
```

## How It Works

Under the hood, ModelType uses the SQLAlchemy TypeDecorator.

- `ModelType` (`TypeDecorator`): Handles the conversion between your Python Object and the JSON format stored in the database.

- `MutableMixin`: Intercepts attribute setting (`__setattr__`) on your object and calls `self.changed()`.

- SQLAlchemy Mutable Extension: Listens to the `changed()` signal and marks the specific row in the transaction as "dirty", ensuring it gets included in the next SQL UPDATE statement.
