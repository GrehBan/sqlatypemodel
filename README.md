# sqlatypemodel

[![Tests](https://github.com/GrehBan/sqlatypemodel/actions/workflows/tests.yml/badge.svg)](https://github.com/GrehBan/sqlatypemodel/actions/workflows/tests.yml)
[![PyPI version](https://badge.fury.io/py/sqlatypemodel.svg)](https://badge.fury.io/py/sqlatypemodel)
[![Python versions](https://img.shields.io/pypi/pyversions/sqlatypemodel.svg)](https://pypi.org/project/sqlatypemodel/)

**Typed JSON fields for SQLAlchemy with automatic mutation tracking.**

SQLAlchemy typically requires you to replace the entire JSON object to trigger an update. `sqlatypemodel` changes that. It allows you to work with strictly typed Python objects (Pydantic, Dataclasses, Attrs, or custom classes) while ensuring every change—no matter how deep—is automatically saved to the database.

It is powered by **`orjson`**, offering blazing-fast performance and native support for `datetime`, `UUID`, and `numpy`.

Now with full support for **Pickle**, making it perfect for **Celery** tasks and caching.

## ✨ Key Features

* **Seamless Integration:** Store Pydantic models directly in SQLAlchemy columns.
* **Universal Support:** Works with **Pydantic (V1 & V2)**, **Dataclasses**, **Attrs**, and custom classes.
* **Pickle & Cache Ready:** Objects can be pickled, sent to Celery workers, or cached in Redis without losing tracking capabilities.
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
from sqlatypemodel.sqlalchemy_utils import create_sync_engine

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
# Use our helper to get an orjson-optimized engine
engine = create_sync_engine("sqlite:///") 
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

## Celery & Caching Support (Pickle)

One of the hardest challenges with SQLAlchemy models is passing them to background tasks (like Celery) or caching them. Standard mutable tracking often breaks during serialization.

`sqlatypemodel` solves this. You can safely pickle your models:

```python
import pickle

# 1. User is loaded from DB
user = session.get(User, 1)

# 2. Serialize and send to a worker (e.g. RabbitMQ/Redis)
payload = pickle.dumps(user)

# --- In Worker Process ---

# 3. Deserialize
worker_user = pickle.loads(payload)

# 4. Modify
worker_user.settings.theme = "worker_updated"

# 5. Send back or Merge
session.merge(worker_user)
session.commit() # Updates are saved!

```

## Handling Lists and Dicts

⚠️ **Important:** `ModelType` expects a structured model. Do not pass raw `List[int]` or `Dict` directly to `ModelType`. Wrap them in a model.

**Incorrect:**

```python
# ❌ Will raise ValueError
col: Mapped[List[int]] = mapped_column(ModelType(List[int]))

```

**Correct:**

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

```

## 🔧 Under the Hood: Architecture

### 1. `orjson` Power

We use `orjson` for serialization. It is ~50x faster than `json` and supports types that normally break standard serializers: `datetime`, `UUID`, `numpy` arrays, and `dataclasses`.

### 2. Utilities: Easy Engine Configuration

To use the full power of `sqlatypemodel`, your SQLAlchemy Engine must be configured to use `orjson`. We provide helpers to do this automatically:

```python
from sqlatypemodel.sqlalchemy_utils import create_sync_engine, create_async_engine

# Sync (SQLite, Postgres, etc.)
engine = create_sync_engine("postgresql://user:pass@localhost/db")

# Async (asyncpg, aiosqlite)
engine = await create_async_engine("postgresql+asyncpg://...")

```

## Advanced Usage

`sqlatypemodel` is not limited to Pydantic.

### Python Dataclasses

We automatically patch `__hash__` for dataclasses to ensure tracking works, so you can use them out of the box.

```python
from dataclasses import dataclass, asdict

@dataclass
class Config(MutableMixin):
    retries: int
    host: str

# Usage
config_col: Mapped[Config] = mapped_column(
    ModelType(
        Config,
        json_dumps=asdict,
        json_loads=lambda d: Config(**d)
    )
)

```

## ⚠️ Important Caveats

### 64-bit Integer Limit

Since `orjson` is written in Rust, it strictly adheres to **64-bit signed integer limits** (from `-2^63` to `2^63 - 1`). If you try to save a larger integer, a `SerializationError` will be raised. This is a trade-off for performance.

### Identity Hashing

To track changes, `MutableMixin` uses **identity-based hashing** (`object.__hash__`). This means two models with the same data are considered "different" keys in a dictionary. Avoid using these mutable models as keys in sets or dicts if you rely on value equality.

## Verification & Stress Testing

Reliability is paramount. We include a forensic-grade stress test suite that anyone can run.

The suite performs:

1. **Hypothesis (Property-based testing):** Generates thousands of edge cases (deep nesting, Unicode, large numbers).
2. **Concurrency Test:** Verifies safety in multi-threaded environments.
3. **Rollback Integrity:** Guarantees state consistency after transaction rollbacks.

```bash
poetry run pytest tests/test_stress.py

```

## License

MIT

```

```