# sqlatypemodel

[![Tests](https://github.com/GrehBan/sqlatypemodel/actions/workflows/tests.yml/badge.svg)](https://github.com/GrehBan/sqlatypemodel/actions/workflows/tests.yml)
[![PyPI version](https://badge.fury.io/py/sqlatypemodel.svg)](https://badge.fury.io/py/sqlatypemodel)
[![Python versions](https://img.shields.io/pypi/pyversions/sqlatypemodel.svg)](https://pypi.org/project/sqlatypemodel/)

**Typed JSON fields for SQLAlchemy with automatic mutation tracking.**

SQLAlchemy does not detect in-place changes inside JSON columns by default. `sqlatypemodel` fixes this, enabling you to work with fully typed Python objects (Pydantic, Dataclasses, Attrs, or custom classes) while ensuring all changes are automatically saved to the database.

## Key Features

* **Seamless Integration:** Store Pydantic models directly in SQLAlchemy columns.
* **Universal Support:** Works with **Pydantic (V1 & V2)**, **Dataclasses**, **Attrs**, and custom classes.
* **Mutation Tracking:** Built-in `MutableMixin` detects deep changes (e.g., `user.data.list.append("item")`) and flags the row for update.
* **High Performance:**
* **O(1) Wrapping:** Smart "short-circuit" logic prevents re-wrapping already tracked collections.
* **Optimized Updates:** Avoids expensive serialization (`model_dump`) on every attribute change, using fast identity checks instead.


* **Automatic Serialization:** Handles conversion to/from JSON automatically.

## The Problem

By default, SQLAlchemy considers JSON columns immutable unless you replace the entire object.

```python
# ❌ NOT persisted by default SQLAlchemy
user.settings.theme = "dark"
user.tags.append("new")
session.commit() # Nothing happens!

```

## The Solution

With `sqlatypemodel`, in-place mutations are tracked:

```python
# ✅ Persisted automatically
user.settings.theme = "dark"
user.tags.append("new")
session.commit() # UPDATE "users" SET ...

```

## Installation

```bash
pip install sqlatypemodel

```

## Performance Benchmarks

`sqlatypemodel` is designed for high-load production environments. We benchmarked assignment operations to ensure minimal overhead.

**Test Scenario:** Assigning a pre-filled list of **100,000 integers** to a model field.

| Operation | Complexity | Time (100k items) | Notes |
| --- | --- | --- | --- |
| **Naive Re-wrapping** | O(N) | ~0.15s+ | Recursively traversing and wrapping every item. |
| **sqlatypemodel** | **Optimized** | **<0.01s** | Uses identity checks to skip re-wrapping known collections. |
| **Change Detection** | **O(1)** | **Instant** | Uses `id()` comparison instead of deep equality checks. |

*Benchmarks run on Python 3.12, Pydantic V2.*

## Quick Start (Pydantic)

This is the most common use case. `MutableMixin` and `ModelType` work together to handle everything.

```python
from typing import List
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from sqlatypemodel import ModelType, MutableMixin

# 1. Define your Pydantic Model
# Note: MutableMixin MUST be the first parent class.
class UserSettings(MutableMixin, BaseModel):
    theme: str = "light"
    notifications: bool = True
    tags: List[str] = []

# 2. Define SQLAlchemy Entity
class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # 3. Use ModelType
    settings: Mapped[UserSettings] = mapped_column(ModelType(UserSettings))

# 4. Usage
engine = create_engine("sqlite:///")
Base.metadata.create_all(engine)

with Session(engine) as session:
    user = User(settings=UserSettings())
    session.add(user)
    session.commit()

    # --- Mutation Tracking ---
    # Modify fields directly:
    user.settings.theme = "dark"
    # Modify nested collections:
    user.settings.tags.append("python")
    
    session.commit() # Changes are saved automatically

```

## Advanced Usage

`sqlatypemodel` is not limited to Pydantic. You can use it with any class by providing `json_dumps` and `json_loads` (or by implementing `to_json`/`from_json` methods).

### Python Dataclasses

Standard dataclasses are supported, but you **must enable identity hashing** (`__hash__ = object.__hash__`) because standard dataclasses are unhashable by default when mutable, and `sqlatypemodel` requires hashing to track parent relationships.

```python
from dataclasses import dataclass, asdict

@dataclass
class Config(MutableMixin):
    retries: int
    host: str
    # REQUIRED: Restore identity hashing for change tracking
    __hash__ = object.__hash__

# Usage in SQLAlchemy
config_col: Mapped[Config] = mapped_column(
    ModelType(
        Config,
        json_dumps=asdict,
        json_loads=lambda d: Config(**d)
    )
)

```

### Attrs

If you use the `attrs` library, disable equality-based hashing (`eq=False`) or explicitly set hash logic to ensure the object is hashable by ID.

```python
import attrs

@attrs.define(eq=False) # eq=False enables identity hashing automatically
class AttrsConfig(MutableMixin):
    mode: str

# Usage
attrs_col: Mapped[AttrsConfig] = mapped_column(
    ModelType(
        AttrsConfig,
        json_dumps=attrs.asdict,
        json_loads=lambda d: AttrsConfig(**d)
    )
)

```

### Custom Classes

You can use any class. If it doesn't have `model_dump`/`model_validate` (like Pydantic), simply provide the serialization logic.

```python
class MyBucket(MutableMixin):
    def __init__(self, items):
        self.items = items
    
    def to_json(self):
        return {"items": self.items}

# Usage
bucket_col: Mapped[MyBucket] = mapped_column(
    ModelType(
        MyBucket,
        json_dumps=lambda x: x.to_json(),
        json_loads=lambda d: MyBucket(d["items"])
    )
)

```

## Important Caveats

### Identity Hashing

To support robust parent tracking (required for nested mutation detection), `MutableMixin` enforces **identity-based hashing** (`object.__hash__`) or requires you to enable it (for dataclasses).

* **Implication:** Two model instances with identical data will have *different* hashes.
* **Restriction:** Do not use these models as keys in `dict` or `set` if you rely on value equality for deduplication. Use lists or value-based comparison logic instead.

### In-Place Mutations & Sessions

For in-place mutations (like `user.data.list.append(1)`) to trigger a database update, the object must be attached to an active SQLAlchemy session. This is standard SQLAlchemy behavior for mutable types.

## License

MIT