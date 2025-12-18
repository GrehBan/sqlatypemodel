# sqlatypemodel

[![Tests](https://github.com/GrehBan/sqlatypemodel/actions/workflows/tests.yml/badge.svg)](https://github.com/GrehBan/sqlatypemodel/actions/workflows/tests.yml)
[![PyPI version](https://badge.fury.io/py/sqlatypemodel.svg)](https://badge.fury.io/py/sqlatypemodel)
[![Python versions](https://img.shields.io/pypi/pyversions/sqlatypemodel.svg)](https://pypi.org/project/sqlatypemodel/)

**Typed JSON fields for SQLAlchemy with automatic mutation tracking.**

By default, SQLAlchemy does not detect in-place changes inside JSON columns. `sqlatypemodel` solves this problem, allowing you to work with strictly typed Python objects (Pydantic, Dataclasses, Attrs, or custom classes) while ensuring all changes are automatically saved to the database.

Under the hood, it uses **`orjson`**, ensuring extreme performance and native support for `datetime`, `UUID`, and `numpy`.

## ✨ Key Features

* **Seamless Integration:** Store Pydantic models directly in SQLAlchemy columns.
* **Universal Support:** Works with **Pydantic (V1 & V2)**, **Dataclasses**, **Attrs**, and custom classes.
* **Protocol Based:** Does not require strict inheritance from `BaseModel`—any class implementing `model_dump`/`model_validate` works.
* **Mutation Tracking:** Built-in `MutableMixin` detects deep changes (e.g., `user.data.list.append("item")`) and flags the row for update.
* **High Performance:**
* **Powered by `orjson`:** Rust-based serialization is 10x-50x faster than standard `json`.
* **O(1) Wrapping:** Smart "short-circuit" logic prevents re-wrapping already tracked collections.
* **Atomic Optimization:** Skips overhead for atomic types (`int`, `str`, `bool`).



## The Problem

By default, SQLAlchemy considers JSON columns immutable unless you replace the entire object.

```python
# ❌ NOT persisted by default SQLAlchemy
user.settings.theme = "dark"
user.tags.append("new")
session.commit() # Nothing happens!

```

## The Solution

With `sqlatypemodel`, in-place mutations are tracked automatically:

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

*Note: `orjson` is installed automatically as a required dependency.*

## Quick Start (Pydantic)

This is the most common use case. `MutableMixin` and `ModelType` work together to handle everything.

```python
from typing import List
from pydantic import BaseModel, Field
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from sqlatypemodel import ModelType, MutableMixin

# 1. Define your Pydantic Model
# Note: MutableMixin MUST be the first parent class.
class UserSettings(MutableMixin, BaseModel):
    theme: str = "light"
    notifications: bool = True
    tags: List[str] = Field(default_factory=list)

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

## Handling Raw Lists and Dicts

⚠️ **Important:** `ModelType` requires a Pydantic-compatible model to know how to serialize data to JSON. You cannot pass a raw `List[int]` or `Dict` directly to `ModelType` without a wrapper, as it raises a `ValueError`.

**Incorrect:**

```python
# ❌ Will raise ValueError: Cannot resolve serialization for List
col: Mapped[List[int]] = mapped_column(ModelType(List[int]))

```

**Correct (Use a Wrapper):**

```python
class ListWrapper(MutableMixin, BaseModel):
    items: List[int] = Field(default_factory=list)

class MyEntity(Base):
    # ...
    # ✅ Works perfectly
    raw_list: Mapped[ListWrapper] = mapped_column(
        ModelType(ListWrapper), 
        default_factory=ListWrapper
    )

# Usage:
entity.raw_list.items.append(1)

```

## 🔧 Under the Hood: Architecture

`sqlatypemodel` is designed for high-load production environments where stability across different databases is critical.

### 1. `orjson` Power

We use `orjson` for serialization. This isn't just about raw speed (though it is ~50x faster than `json`). It provides native support for types that normally break standard JSON serializers: `datetime`, `UUID`, `numpy` arrays, and `dataclasses`.

### 2 Utilities: Easy Engine Configuration

To use the full power of `sqlatypemodel` (support for `datetime`, `UUID`, high performance), SQLAlchemy must be configured to use `orjson` instead of the standard `json` library.

Instead of manually passing serializer functions every time you create an engine, you can use our helper functions.

**Why use this?**

1. **Less Boilerplate:** You don't need to import `orjson` and define lambdas manually.
2. **Consistency:** Guarantees that serialization and deserialization are symmetric and configured correctly for the library.

### Example

**The Hard Way (Standard SQLAlchemy):**

```python
import orjson
from sqlalchemy import create_engine

def fast_dumps(obj):
    return orjson.dumps(obj).decode("utf-8")

# You have to repeat this configuration everywhere
engine = create_engine(
    "postgresql://user:pass@localhost/db",
    json_serializer=fast_dumps,
    json_deserializer=orjson.loads
)

```

**The Easy Way (sqlatypemodel):**

```python
from sqlatypemodel.sqlalchemy_utils import create_sync_engine

# Automatically configured with orjson
engine = create_sync_engine("postgresql://user:pass@localhost/db")

```

We also support `asyncio`:

```python
from sqlatypemodel.sqlalchemy_utils import create_async_engine

engine = await create_async_engine("postgresql+asyncpg://...")

```

## Advanced Usage

`sqlatypemodel` is not limited to Pydantic. You can use it with any class.

### Python Dataclasses

Standard dataclasses are supported, but you **must enable identity hashing** (`__hash__ = object.__hash__`) because standard dataclasses are unhashable by default when mutable, and `sqlatypemodel` requires parent tracking.

```python
from dataclasses import dataclass, asdict

@dataclass
class Config(MutableMixin):
    retries: int
    host: str
    # REQUIRED: Restore identity hashing for change tracking
    __hash__ = object.__hash__

# Usage
config_col: Mapped[Config] = mapped_column(
    ModelType(
        Config,
        json_dumps=asdict,
        json_loads=lambda d: Config(**d)
    )
)

```

### Attrs

If you use the `attrs` library, disable equality-based hashing (`eq=False`) or explicitly set hash logic.

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

## ⚠️ Important Caveats

### 64-bit Integer Limit (`orjson`)

Since `orjson` (written in Rust) is used for serialization, the library strictly adheres to **64-bit signed integer limits** (from `-2^63` to `2^63 - 1`).
Python supports arbitrary-precision integers, but if you try to save an integer larger than 64-bit into a JSON column, `SerializationError` will be raised. This is a trade-off for performance and database compatibility.

### Identity Hashing

To correctly bubble up change events from children to parents, `MutableMixin` requires **identity-based hashing** (`object.__hash__`). Do not use these models as keys in a `dict` or elements in a `set` if your logic relies on value equality.

## Verification & Stress Testing

Reliability is paramount. We include a forensic-grade stress test suite (`tests/stress_test.py`) that anyone can run.

The suite performs:

1. **Hypothesis (Property-based testing):** Generates thousands of edge cases, including complex Unicode strings, deep nesting, and random object graphs.
2. **Concurrency Test:** Verifies the absence of race conditions when writing to the DB from multiple threads.
3. **Rollback Integrity:** Guarantees that upon transaction rollback, the Python object state in memory is correctly reset.

### Run it yourself:

```bash
poetry run pytest tests/test_stress.py

```

## License

MIT