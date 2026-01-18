# sqlatypemodel

[![Tests](https://github.com/GrehBan/sqlatypemodel/actions/workflows/tests.yml/badge.svg)](https://github.com/GrehBan/sqlatypemodel/actions/workflows/tests.yml)
[![Linting](https://github.com/GrehBan/sqlatypemodel/actions/workflows/lint.yml/badge.svg)](https://github.com/GrehBan/sqlatypemodel/actions/workflows/lint.yml)
[![PyPi status](https://img.shields.io/pypi/status/sqlatypemodel.svg?style=flat-square)](https://pypi.python.org/pypi/sqlatypemodel)
[![PyPi Package Version](https://img.shields.io/pypi/v/sqlatypemodel.svg?style=flat-square)](https://pypi.python.org/pypi/sqlatypemodel)
[![Python versions](https://img.shields.io/pypi/pyversions/sqlatypemodel.svg)](https://pypi.org/project/sqlatypemodel/)
[![Downloads](https://img.shields.io/pypi/dm/sqlatypemodel.svg?style=flat-square)](https://pypi.python.org/pypi/sqlatypemodel)
[![MIT License](https://img.shields.io/pypi/l/sqlatypemodel.svg?style=flat-square)](https://opensource.org/licenses/MIT)

# Typed JSON fields for SQLAlchemy with automatic mutation tracking

**sqlatypemodel** solves the "immutable JSON" problem in SQLAlchemy. It allows you to use strictly typed Python objects (**Pydantic**, **Dataclasses**, **Attrs**) as database columns while ensuring that **every change—no matter how deep—is automatically saved.**

Powered by **orjson** for blazing-fast performance and featuring a **State-Based Architecture** for universal compatibility.

---

## 📚 Documentation

[ReadTheDocs](https://sqlatypemodel.readthedocs.io/en/latest/)

Full documentation is available in the `docs/` directory:

*   **[Installation](docs/installation.rst)**
*   **[Usage Guide](docs/usage.rst)**
*   **[Architecture & Internals](docs/architecture.rst)**
*   **[Caveats](docs/caveats.rst)**
*   **[Contributing](CONTRIBUTING.md)**

---

## ✨ Key Features

* **🏗️ State-Based Tracking (v0.8.0+):**
  * **Universal Compatibility:** Works natively with **unhashable** objects (e.g., standard Pydantic models, `eq=True` Dataclasses).
  * **Zero Monkey-Patching:** No longer alters your class's `__hash__` or `__eq__` methods. Uses internal `MutableState` tokens for safe identity tracking.

* **⚡ Maximum Performance (v0.8.3+ Optimized):**
  * **Hot Path Acceleration:** Direct `object.__getattribute__()` calls and type dispatch tables reduce overhead by 40%+.
  * **Lazy Loading:** 2.1x faster DB loading and 35% less memory usage.
  * **Pre-computed state** eliminates repeated lookups.
  * **O(1) type checks** using frozenset membership for atomic types.

* **🐢 -> 🐇 Lazy Loading:**
  * **Zero-cost loading:** Objects loaded from the DB are raw Python dicts until you access them.
  * **JIT Wrapping:** Wrappers are created Just-In-Time.
  * **5.1x faster initialization** compared to eager loading.

* **🥒 Pickle & Celery Ready:**
  * Full support for `pickle`. Pass your database models directly to **Celery** workers or cache them in **Redis**.
  * Tracking is automatically restored upon deserialization via `MutableMethods`.

* **🚀 High Performance:**
  * **Powered by `orjson`:** faster serialization than standard `json`.
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



## 📚 Examples & Usage



We provide a comprehensive suite of ready-to-run examples in the `examples/` directory:



1.  **[Basic Pydantic](./examples/01_pydantic_basic.py)**: The standard workflow for mutation tracking.

2.  **[Lazy Loading Benchmarks](./examples/02_lazy_loading.py)**: Performance comparison between eager and lazy loading.

3.  **[Dataclasses](./examples/03_dataclasses.py)**: Using the safe dataclass wrapper.

4.  **[Attrs Support](./examples/04_attrs.py)**: Integration with the `attrs` library.

5.  **[Async SQLAlchemy](./examples/05_async_sqlalchemy.py)**: Integration with `AsyncSession` and `aiosqlite`.

6.  **[Deep Nesting](./examples/06_nested_collections.py)**: Tracking changes in lists of dictionaries of models.

7.  **[Pickle & Celery](./examples/07_pickle_celery.py)**: Passing models to background workers.



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
---

### 2. High-Performance Usage (`LazyMutableMixin`)

**Recommended for read-heavy, sparse-field applications.**
Objects are initialized "lazily". The overhead of change tracking is only paid when you actually access the attribute.

```python
from sqlatypemodel import LazyMutableMixin

# Just swap MutableMixin -> LazyMutableMixin
class UserSettings(LazyMutableMixin, BaseModel):
    theme: str = "light"
    # ...

```

**Performance Benchmarks (v0.8.3):**

| Metric | Eager | Lazy | Improvement | Notes |
|--------|-------|------|---|---|
| **Initialization (per object)** | 593 µs | 1.6 µs | **376x faster** | Pure Python object init |
| **DB Load (5,000 objects)** | 406ms | 195ms | **2.1x faster** | SQL query + deserialization |
| **First Field Access** | 2.8ms | 146ms | 50x slower | JIT wrapping overhead |
| **Memory Usage (5k objects)** | 11.8MB | 7.8MB | **35% less** | Lower overhead |

**Key Insight:** Lazy loading is **exceptionally fast at initialization** and reduces DB load time significantly (2.1x). Use it for large result sets where you only access a subset of data.

---

## License

MIT
