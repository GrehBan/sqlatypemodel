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
* **JIT Wrapping:** Wrappers are created Just-In-Time. Loading 5,000 objects takes **7ms** instead of **1.1s**.


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
from sqlatypemodel.sqlalchemy_utils import create_sync_engine

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
engine = create_sync_engine("sqlite:///") 
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

When you inherit from `BaseMutableMixin` (or its derivatives), the library automatically handles registration:

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
* **`associate=MyCustomModelType`**: Use this if you have multiple different `ModelType` implementations for different databases.

---

### 2. Custom Serialization (Non-Pydantic Classes)

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
    ModelType(
        ConfigData,
        json_dumps=asdict,      # Standard library function
        json_loads=load_config  # Custom loader function
        )
    )
)
```

### 3. High-Performance Usage (`LazyMutableMixin`)

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

### 1. Attrs Support

**⚠️ Crucial Requirements:**

1. **`slots=False`**: `MutableMixin` needs `__dict__` to store internal tracking state (`_parents`, etc.).
2. **`eq=False`**: `MutableMixin` enforces **Identity Hashing** (`hash(obj) == id(obj)`). If you let `attrs` generate a standard `__eq__` (value-based), it will conflict with the identity-based hash.

```python
from attrs import define, asdict
from sqlatypemodel import MutableMixin, ModelType

# 1. Configuration
@define(slots=False, eq=False)
class AttrsConfig(MutableMixin):
    retries: int
    tags: list[str]

# 2. SQLAlchemy Mapping
class User(Base):
    __tablename__ = "users"
    # ...
    config: Mapped[AttrsConfig] = mapped_column(
        ModelType(
            AttrsConfig,
            # Explicitly define how to serialize/deserialize
            json_dumps=asdict,
            json_loads=lambda d: AttrsConfig(**d)
        )
    )

```

### 2. Python Dataclasses

We automatically patch `__hash__` for dataclasses to ensure tracking works.

```python
class ForceHashMixin:
    """Mixin to enforce object identity hashing.

    This ensures that objects can be used in weak references even if their
    default hashing behavior is modified or disabled (e.g., by Pydantic).
    """

    __hash__ = object.__hash__

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        """Ensure __hash__ is set to identity hash upon creation.

        Args:
            *args: Positional arguments for instance creation.
            **kwargs: Keyword arguments for instance creation.

        Returns:
            A new instance of the class.
        """
        if getattr(cls, "__hash__", None) is None:
            cls.__hash__ = ForceHashMixin.__hash__
        return super().__new__(cls)
```

```python
from dataclasses import dataclass, asdict

@dataclass
class DataConfig(MutableMixin):
    host: str
    port: int

# SQLAlchemy Mapping
col: Mapped[DataConfig] = mapped_column(
    ModelType(
        DataConfig,
        json_dumps=asdict,
        json_loads=lambda d: DataConfig(**d)
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

You also can manually create engine and provide our json serializers


```python
from sqlalchemy import create_engine
from sqlalchemy.util.json import get_serializers

dumps, loads = get_serializers(use_orjson=True)

engine = create_engine("postgresql://user:pass@localhost/db", json_serializer=dumps, json_deserializer=loads)
```

---

## 🧠 Under the Hood: How it Works

Understanding the magic helps you design better applications.

### The "Proxy" Pattern

When you assign a `list` or `dict` to a model, `sqlatypemodel` intercepts it and wraps it in a `MutableList` or `MutableDict`. These wrappers look and behave exactly like standard lists/dicts, but they have a hidden link to their parent.

### Logic Flow: Change Tracking (The "Bubble Up" Effect)

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

### Logic Flow: Lazy Loading vs. Eager Loading

How data travels from the Database to your Code.

#### **Eager (`MutableMixin`)**

```text
[DB JSON] -> [json.loads] -> [Raw Dict]
                                 |
                                 v
                          [__init__ / _restore_tracking]
                                 |
                          (Heavy Recursive Scan)
                                 |
                          [Wraps EVERYTHING immediately]
                                 |
User Code <-------------- [Fully Wrapped Object]

```

*Pros:* Fast reads. *Cons:* Slow load time for large objects.

#### **Lazy (`LazyMutableMixin`)**

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

*Pros:* Instant load time. *Cons:* Tiny overhead on first access.

---

## 🔍 Internal Code Peek

To understand the magic, look at how we handle attribute access in **Lazy Loading** (`mixin.py`):

```python
# Simplified logic from sqlatypemodel/mixin/mixin.py
class LazyMutableMixin(BaseMutableMixin):
    def __getattribute__(self, name: str) -> Any:
        # 1. Get the actual value from memory
        value = object.__getattribute__(self, name)

        # 2. Check if it's a raw dict/list that hasn't been wrapped yet
        if is_mutable_and_untracked(value):
            # 3. Wrap it (Create MutableList/Dict and link parent)
            wrapped = wrap_mutable(self, value, key=name)
            
            # 4. Save it back so next time it's fast
            object.__setattr__(self, name, wrapped)
            return wrapped

        return value

```

---

## ⚠️ Important Caveats & Limitations

### 1. Identity Hashing (Crucial)

To track changes, `MutableMixin` **must** be able to use your objects as keys in a `WeakKeyDictionary`. This requires the object to be hashable based on its **Identity** (memory address), not its content.

* **Rule:** Two `UserSettings` objects with the exact same data are **NOT** equal and have different hashes.
* **Implication:** Do not use these models as keys in a `dict` if you rely on value equality.

### 2. 64-bit Integer Limit

`orjson` (Rust) is strict. It supports signed 64-bit integers (`-9,223,372,036,854,775,808` to `9,223,372,036,854,775,807`).

* **Risk:** If you try to save a Python `int` larger than this, a `SerializationError` will be raised.

So, we implemented fallback to python's standard json library, and when orjson serialization raises an exception we will try to use the standard library

```python
def _orjson_dumps_wrapper(obj: Any) -> str:
    """
    Attempt orjson serialization, fallback to standard json on failure.
    Handles:
    1. Integer overflow (int > 64 bit) -> Fallback
    2. Unknown types (TypeError) -> Fallback
    """
    try:
        return orjson.dumps(obj).decode("utf-8")
    except (orjson.JSONEncodeError, TypeError, OverflowError):
        return _std_dumps(obj)


def _orjson_loads_wrapper(data: str | bytes) -> Any:
    """
    Attempt orjson deserialization, fallback to standard json on failure.
    Useful if data in DB was saved via standard json (e.g. huge integers).
    """
    try:
        return orjson.loads(data)
    except (orjson.JSONDecodeError, TypeError, ValueError):
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return json.loads(data)

```

### 3. Attrs & Slots

As mentioned, `attrs` defaults to `slots=True`.

* **Risk:** If you forget `slots=False`, you will get `AttributeError: 'MyModel' object has no attribute '_parents_store'`.
* **Fix:** Always use `@define(slots=False)`.

---

## License

MIT