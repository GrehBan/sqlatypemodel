# sqlatypemodel

[![Tests](https://github.com/GrehBan/sqlatypemodel/actions/workflows/tests.yml/badge.svg)](https://github.com/GrehBan/sqlatypemodel/actions/workflows/tests.yml)
[![PyPI version](https://badge.fury.io/py/sqlatypemodel.svg)](https://badge.fury.io/py/sqlatypemodel)
[![Python versions](https://img.shields.io/pypi/pyversions/sqlatypemodel.svg)](https://pypi.org/project/sqlatypemodel/)

# Typed JSON fields for SQLAlchemy with automatic mutation tracking

**sqlatypemodel** solves the "immutable JSON" problem in SQLAlchemy. It allows you to use strictly typed Python objects (**Pydantic**, **Dataclasses**, **Attrs**) as database columns while ensuring that **every change—no matter how deep—is automatically saved.**

Powered by **`orjson`** for blazing-fast performance and featuring a **State-Based Architecture** for universal compatibility.

---

## ✨ Key Features

* **🏗️ State-Based Tracking (v0.8.0):**
  * **Universal Compatibility:** Works natively with **unhashable** objects (e.g., standard Pydantic models, `eq=True` Dataclasses).
  * **Zero Monkey-Patching:** No longer alters your class's `__hash__` or `__eq__` methods. Uses internal `MutableState` tokens for safe identity tracking.

* **🐢 -> 🐇 Lazy Loading:**
  * **Zero-cost loading:** Objects loaded from the DB are raw Python dicts until you access them.
  * **JIT Wrapping:** Wrappers are created Just-In-Time. Loading 5,000 objects takes **~7ms** instead of **~1.1s**.

* **🥒 Pickle & Celery Ready:**
  * Full support for `pickle`. Pass your database models directly to **Celery** workers or cache them in **Redis**.
  * Tracking is automatically restored upon deserialization via `MutableMethods`.

* **🚀 High Performance:**
  * **Powered by `orjson`:** 10x-50x faster serialization than standard `json`.
  * **Native Types:** Supports `datetime`, `UUID`, and `numpy` out of the box.
  * **Smart Caching:** Introspection results are cached (`O(1)` overhead).

* **🔄 Deep Mutation Tracking:**
  * Detects changes like `user.settings.tags.append("new")` automatically.
  * No more `flag_modified()` or reassigning the whole object.

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

The library uses `__init_subclass__` to automate the connection between your models and the SQLAlchemy `ModelType`.

```python
class BaseMutableMixin(MutableMethods, Mutable, abc.ABC):
    def __init_subclass__(cls, **kwargs: Any) -> None:
        # Automatically calls ModelType.register_mutable(cls)
        from sqlatypemodel.model_type import ModelType
        ModelType.register_mutable(cls)

```

**What this means for you:**

* **Zero Configuration:** Just inherit, and the model is ready for tracking.
* **Unhashable Models OK:** Your models don't need to be hashable. The library assigns a unique `_state` token to every instance to track relationships safely.

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

`sqlatypemodel` isn't just for Pydantic. It supports any Python class.

### 1. Python Dataclasses

In v0.8.0+, standard dataclasses work out of the box, even if they are unhashable (`eq=True, frozen=False`).

However, for deep recursion safety during initialization on Python 3.12+, we still recommend our safe wrapper:

```python
from dataclasses import asdict
from typing import Any
from sqlatypemodel import MutableMixin, ModelType
# ✅ Safe wrapper (prevents recursion loops during init)
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

### 2. Attrs

Standard `attrs` classes are fully supported.

```python
from attrs import asdict, define
from sqlatypemodel import MutableMixin, ModelType

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

---

## 🔧 Under the Hood: Architecture

### 1. State-Based Tracking (The "Safe" Way)

Unlike other libraries that require your objects to be hashable (often breaking Pydantic/Dataclasses), `sqlatypemodel` attaches a lightweight **State Token** (`MutableState`) to every tracked object.

* **Parent** holds the `_state` token strongly.
* **Children** track their parents via `WeakKeyDictionary[_state, attribute_name]`.
* **Result**: Robust tracking that survives Garbage Collection race conditions and works with *any* Python object.

### 2. Logic Flow: Change Tracking (The "Bubble Up" Effect)

When you modify a deeply nested list, the signal bubbles up to SQLAlchemy using these tokens.

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
            1. Iterates `self._parents` (WeakKeyDictionary)
            2. Resolves `MutableState` -> Parent Object (UserSettings)
                      |
                      v
[Parent]    UserSettings.changed()
                      |
            (triggers safe_changed() recursively)
                      |
            1. Resolves `MutableState` -> Parent Object (User Entity)
                      |
                      v
[Root]      SQLAlchemy Model (User)
                      |
            flag_modified(user, "settings") -> Marks row as "Dirty"

```

---

## ⚠️ Important Caveats

### 1. 64-bit Integer Limit

`orjson` (Rust) is strict. It supports signed 64-bit integers (`-9,223,372,036,854,775,808` to `9,223,372,036,854,775,807`).
If you try to save a Python `int` larger than this, the library automatically falls back to the standard `json` library, ensuring data safety at the cost of performance for that specific record.

### 2. Mixed Types in Collections

While supported, avoid mixing complex mutable types in the same list (e.g., `[MyModel(), {"key": "val"}]`) if you can. It works, but the "Lazy" loading mechanism has to infer types at runtime, which is slightly slower than uniform lists.

---

## License

MIT
