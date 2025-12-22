# sqlatypemodel

[![Tests](https://github.com/GrehBan/sqlatypemodel/actions/workflows/tests.yml/badge.svg)](https://github.com/GrehBan/sqlatypemodel/actions/workflows/tests.yml)
[![PyPI version](https://badge.fury.io/py/sqlatypemodel.svg)](https://badge.fury.io/py/sqlatypemodel)
[![Python versions](https://img.shields.io/pypi/pyversions/sqlatypemodel.svg)](https://pypi.org/project/sqlatypemodel/)


# Typed JSON fields for SQLAlchemy with automatic mutation tracking

**sqlatypemodel** solves the "immutable JSON" problem in SQLAlchemy. It allows you to use strictly typed Python objects (**Pydantic**, **Dataclasses**, **Attrs**) as database columns while ensuring that **every change—no matter how deep—is automatically saved.**

Powered by **`orjson`** for blazing-fast performance and featuring a **Lazy Loading** architecture for instant database reads.

---

## ✨ Key Features

* **🐢 -> 🐇 Lazy Loading (v0.7.0):**
  * **Zero-cost loading:** Objects loaded from the DB are raw Python dicts until you access them.
  * **JIT Wrapping:** Wrappers are created Just-In-Time. Loading 5,000 objects takes **~7ms** instead of **~1.1s**.

* **🥒 Pickle & Celery Ready:**
  * Full support for `pickle`. Pass your database models directly to **Celery** workers or cache them in **Redis**.
  * Tracking is automatically restored upon deserialization.

* **🚀 High Performance:**
  * **Powered by `orjson`:** 10x-50x faster serialization than standard `json`.
  * **Native Types:** Supports `datetime`, `UUID`, and `numpy` out of the box.
  * **Smart Caching:** Introspection results are cached (`O(1)` overhead).

* **🔄 Deep Mutation Tracking:**
  * Detects changes like `user.settings.tags.append("new")` automatically.
  * No more `flag_modified()` or reassigning the whole object.

* **Universal Support:** Works with Pydantic (V1 & V2), Dataclasses, Attrs, and Plain classes.

---

## The Problem

By default, SQLAlchemy considers JSON columns immutable unless you replace the entire object.

```python
# ❌ NOT persisted by default in SQLAlchemy
user.settings.theme = "dark"
user.settings.tags.append("new")

session.commit() # Nothing happens! Data is lost.

```

## The Solution

With `sqlatypemodel`, in-place mutations are tracked automatically:

```python
# ✅ Persisted automatically
user.settings.theme = "dark"
user.settings.tags.append("new")

session.commit() # UPDATE "users" SET settings = ...

```

---

## Installation

```bash
pip install sqlatypemodel

```

To ensure you have `orjson` (recommended):

```bash
pip install sqlatypemodel[fast]

```

---

## Quick Start (Pydantic)

### 1. Standard Usage (`MutableMixin`)

Best for write-heavy workflows or when you always access the data immediately.

```python
from typing import List
from pydantic import BaseModel, Field
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from sqlatypemodel import ModelType, MutableMixin
from sqlatypemodel.util.sqlalchemy import create_engine

# 1. Define Pydantic Model (Inherit from MutableMixin)
class UserSettings(MutableMixin, BaseModel):
    theme: str = "light"
    tags: List[str] = Field(default_factory=list)

# 2. Define Entity
class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    settings: Mapped[UserSettings] = mapped_column(ModelType(UserSettings))

# 3. Usage
# Use our helper to get free orjson configuration
engine = create_engine("sqlite:///") 
Base.metadata.create_all(engine)

with Session(engine) as session:
    user = User(settings=UserSettings())
    session.add(user)
    session.commit()

    # Mutation works!
    user.settings.tags.append("python") 
    session.commit() 

```

### 🔧 Internal Magic:

The library uses `__init_subclass__` to automate the connection between your models and the SQLAlchemy `ModelType`. When you inherit from `BaseMutableMixin` (or its derivatives), the library automatically handles registration.

```python
class BaseMutableMixin(serialization.ForceHashMixin, Mutable, abc.ABC):
    def __init_subclass__(cls, **kwargs: Any) -> None:
        # Our internal flags:
        auto_register = kwargs.pop("auto_register", True) # Default: True
        associate_cls = kwargs.pop("associate", None)     # Link to custom ModelType

        if auto_register and not inspect.isabstract(cls):
             # Automatically calls ModelType.register_mutable(cls)
             from sqlatypemodel.model_type import ModelType

             associate = associate_cls or ModelType
             associate.register_mutable(cls)

```

**What this means for you:**

* **Zero Configuration:** Just inherit, and the model is ready for tracking.
* **`auto_register=False`**: Use this flag if you want to define a base class for your models but don't want it globally registered yet.

---

### 2. High-Performance Usage (`LazyMutableMixin`)

**Recommended for read-heavy applications.**
Objects are initialized "lazily". The overhead of change tracking is only paid when you actually access the attribute.

```python
from sqlatypemodel import LazyMutableMixin

# Just swap MutableMixin -> LazyMutableMixin
class UserSettings(LazyMutableMixin, BaseModel):
    theme: str = "light"
    # ...

```

**Performance Comparison (Load 5,000 objects):**

* **Standard (`MutableMixin`):** ~1100ms
* **Lazy (`LazyMutableMixin`):** ~7ms (**~150x faster**)

---

## 🛠 Advanced Support: Attrs, Dataclasses, Plain Classes

`sqlatypemodel` isn't just for Pydantic. It supports any Python class, provided you configure it correctly.

### 1. Python Dataclasses (Native Support)

Standard dataclasses are unsafe for mutable tracking in Python 3.12+ because `__eq__` compares values (crashing recursion during initialization) and `__hash__` is generated based on values (breaking tracking).

We provide a **safe wrapper** that enforces Identity Hashing and Equality.

```python
from dataclasses import asdict
from typing import Any
from sqlatypemodel import MutableMixin, ModelType
# ✅ Use this import instead of the standard library
from sqlatypemodel.util.dataclasses import dataclass 

@dataclass
class DataConfig(MutableMixin):
    host: str
    port: int
    meta: dict[str, Any]

# SQLAlchemy Mapping
col: Mapped[DataConfig] = mapped_column(
    ModelType(
        DataConfig,
        json_dumps=asdict,
        json_loads=lambda d: DataConfig(**d)
    )
)

```

### 2. Attrs (⚠️ Common Pitfall)

**Critical:** You **must** disable slots and value-based equality.

* `slots=False`: The library needs `__dict__` to inject tracking metadata.
* `eq=False`: We use Identity Hashing. Standard equality breaks tracking.

We provide a helper to enforce this:

```python
from attrs import asdict
from sqlatypemodel import MutableMixin, ModelType
# ✅ Use our helper to ensure safety
from sqlatypemodel.util.attrs import define 

@define 
class AttrsConfig(MutableMixin):
    retries: int
    tags: list[str]

# Mapping
col = mapped_column(
    ModelType(
        AttrsConfig,
        json_dumps=asdict,
        json_loads=lambda d: AttrsConfig(**d)
    )
)

```

### 3. Plain Python Classes

You can even use raw Python classes.

```python
class VanillaConfig(MutableMixin):
    def __init__(self, key: str, value: int):
        self.key = key
        self.value = value

    def to_dict(self):
        return {"key": self.key, "value": self.value}

# SQLAlchemy Mapping
col: Mapped[VanillaConfig] = mapped_column(
    ModelType(
        VanillaConfig,
        json_dumps=lambda o: o.to_dict(),
        json_loads=lambda d: VanillaConfig(**d)
    )
)

```

---

## 🔧 Under the Hood: Architecture

### 1. `orjson` Power

We use `orjson` for serialization. It is ~50x faster than `json` and supports types that normally break standard serializers: `datetime`, `UUID`, `numpy` arrays, and `dataclasses`.

### 2. Utilities: Easy Engine Configuration

To use the full power of `sqlatypemodel`, your SQLAlchemy Engine must be configured to use `orjson`. We provide helpers to do this automatically:

```python
from sqlatypemodel.util.sqlalchemy import create_engine, create_async_engine

# Sync (SQLite, Postgres, etc.)
engine = create_engine("postgresql://user:pass@localhost/db")

# Async (asyncpg, aiosqlite)
engine = create_async_engine("postgresql+asyncpg://...")

```

### 3. Logic Flow: Change Tracking (The "Bubble Up" Effect)

When you modify a deeply nested list, the signal bubbles up to SQLAlchemy.

```text
User Code:  user.settings.tags.append("new")
                      |
                      v
[Leaf]      MutableList.append("new")
                      |
            (triggers self.changed())
                      |
                      v
[Logic]     sqlatypemodel.events.safe_changed()
                      |
            1. Looks up `self._parents` (WeakKeyDictionary)
            2. Finds parent object: UserSettings
                      |
                      v
[Parent]    UserSettings.changed()
                      |
            (triggers safe_changed() recursively)
                      |
            1. Looks up `self._parents`
            2. Finds parent object: User (SQLAlchemy Model)
                      |
                      v
[Root]      SQLAlchemy Model (User)
                      |
            flag_modified(user, "settings") -> Marks row as "Dirty"

```

### 4. Logic Flow: Lazy Loading (`LazyMutableMixin`)

```text
[DB JSON] -> [json.loads] -> [Raw Dict]
                                 |
                                 v
User Code <-------------- [Object with Raw Dict in __dict__]
                                 |
                          (User accesses .data)
                                 |
                          [__getattribute__ Intercept]
                                 |
                          1. Is it raw? -> Yes.
                          2. Wrap it NOW (Just-In-Time).
                          3. Update __dict__ with wrapper.
                                 |
                          [Return Wrapped Object]

```

---

## ⚠️ Important Caveats

### 1. Identity Hashing (Crucial)

To track changes, `MutableMixin` **must** be able to use your objects as keys in a `WeakKeyDictionary`. This requires the object to be hashable based on its **Identity** (memory address), not its content.

* **Rule:** Two `UserSettings` objects with the exact same data are **NOT** equal (`a != b`) and have different hashes.
* **Implication:** Do not use these models as keys in a `dict` if you rely on value equality.

### 2. 64-bit Integer Limit

`orjson` (Rust) is strict. It supports signed 64-bit integers (`-9,223,372,036,854,775,808` to `9,223,372,036,854,775,807`).
If you try to save a Python `int` larger than this, the library automatically falls back to the standard `json` library, ensuring data safety at the cost of performance for that specific record.

---

## License

MIT
