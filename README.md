# sqlatypemodel

[![Tests](https://github.com/GrehBan/sqlatypemodel/actions/workflows/tests.yml/badge.svg)](https://github.com/GrehBan/sqlatypemodel/actions/workflows/tests.yml)
[![PyPI version](https://badge.fury.io/py/sqlatypemodel.svg)](https://badge.fury.io/py/sqlatypemodel)
[![Python versions](https://img.shields.io/pypi/pyversions/sqlatypemodel.svg)](https://pypi.org/project/sqlatypemodel/)

# Typed JSON fields for SQLAlchemy with automatic mutation tracking

**sqlatypemodel** solves the "immutable JSON" problem in SQLAlchemy. It allows you to use strictly typed Python objects (**Pydantic**, **Dataclasses**, **Attrs**) as database columns while ensuring that **every change—no matter how deep—is automatically saved.**

Powered by **`orjson`** for blazing-fast performance and featuring a **State-Based Architecture** for universal compatibility.

---

## ✨ Key Features

* **🏗️ State-Based Tracking (v0.8.0+):**
  * **Universal Compatibility:** Works natively with **unhashable** objects (e.g., standard Pydantic models, `eq=True` Dataclasses).
  * **Zero Monkey-Patching:** No longer alters your class's `__hash__` or `__eq__` methods. Uses internal `MutableState` tokens for safe identity tracking.

* **⚡ Maximum Performance (v0.7+ Optimized):**
  * **40-47% faster** attribute access through direct `object.__getattribute__()` instead of `hasattr()`
  * **Pre-computed state** eliminates 60-70% of repeated lookups
  * **O(1) type checks** using frozenset membership for atomic types
  * **LRU cache tuning** (8192 entries) for better hit rates
  * **Cold→Hot path architecture** for typical workloads

* **🐢 -> 🐇 Lazy Loading:**
  * **Zero-cost loading:** Objects loaded from the DB are raw Python dicts until you access them.
  * **JIT Wrapping:** Wrappers are created Just-In-Time.
  * **5.1x faster initialization** compared to eager loading
  * **47% less memory** overhead than eager mixin

* **🥒 Pickle & Celery Ready:**
  * Full support for `pickle`. Pass your database models directly to **Celery** workers or cache them in **Redis**.
  * Tracking is automatically restored upon deserialization via `MutableMethods`.

* **🚀 High Performance:**
  * **Powered by `orjson`:** faster serialization than standard `json`.
  * **Native Types:** Supports `datetime`, `UUID`, and `numpy` out of the box.
  * **Smart Caching:** Introspection results are cached (`O(1)` overhead).
  * **Benchmark:** Load 5,000 objects in 192ms (lazy) vs 416ms (eager)

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

2.  **[Lazy Loading Benchmarks](./examples/02_lazy_loading.py)**: Performance comparison between eager and lazy loading (1.2x overall speedup, 2.0x faster DB load).

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
* **`auto_register=False:`** Use this flag if you want to define a base class for your models but don't want it globally registered yet.

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

**Performance Benchmarks:**

| Metric | Eager | Lazy | Improvement | Notes |
|--------|-------|------|---|---|
| **Initialization (per object)** | 593 µs | 1.6 µs | **376x faster** | Pure Python object init |
| **DB Load (5,000 objects)** | 393ms | 194ms | **2.0x faster** | SQL query + deserialization |
| **First Field Access** | 2.3ms | 144ms | 62x slower | JIT wrapping overhead |
| **Full Workflow** | 422ms | 366ms | **1.2x faster** | DB load + access + commit |

**Key Insight:** Lazy loading is **exceptionally fast at initialization** (376x), but the advantage shrinks in real-world DB workflows (1.2x) because SQL query time dominates. The JIT wrapping creates a "first access tax"—avoid lazy loading if you access most/all fields.

**Use case:** 
- ✅ Lazy: Large result sets where you only need a few fields
- ✅ Eager: Write-heavy workflows accessing most fields
- ✅ Lazy: API responses (serialize specific fields only)
- ❌ Lazy: Full object traversal (pays JIT tax on every field)


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
        dumper=asdict,
        loader=lambda d: DataConfig(**d)
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
        dumper=asdict,
        loader=lambda d: AttrsConfig(**d)
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

## 📊 Benchmark Performance Summary

### Performance

| Operation | Before | After | Improvement |
|-----------|--------|-------|-------------|
| **Lazy init/object** | ~8µs | ~1.7µs | **5.1x faster** |
| **Attribute read** | ~2.0µs | ~1.2µs | **40% faster** |
| **Attribute write** | ~3.2µs | ~2.1µs | **34% faster** |
| **Memory (Lazy)** | ~12MB | ~6.1MB | **47% less** |
| **DB load (5000 objects)** | ~440ms | ~416ms | **5% faster** |

### Benchmark Test Results (N=5000, with Optimizations)

| Name (time in µs) | Min | Max | Mean | StdDev | Median | IQR | OPS (Kops/s) | Rounds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **test_benchmark_db_load_lazy** | 1.4020 | 23.7250 | 1.5317 | 0.3680 | 1.4920 | 0.0400 | 652.8531 | 48499 |
| **test_benchmark_read_access_lazy_cached** | 3.8570 | 39.9650 | 4.1546 | 0.6319 | 4.0680 | 0.0890 | 240.6966 | 59698 |
| **test_benchmark_db_load_eager** | 498.4650 | 646.1940 | 523.9364 | 14.2668 | 521.3440 | 16.8730 | 1.9086 | 1114 |

---

### 🔑 Key Definitions

* **Min/Max/Mean/Median:** The recorded time for the operations in microseconds (µs).
* **StdDev:** Standard Deviation from the Mean.
* **IQR:** InterQuartile Range (difference between the 75th and 25th percentiles).
* **OPS:** Operations Per Second (calculated as ).
* **Rounds:** The number of times the benchmark was executed to collect data.

### 📝 Execution Overview

* **Platform:** Linux (Python 3.14.2)
* **Total Tests Collected:** 51
* **Status:** 51 Passed
* **Total Duration:** 5.89 seconds

---

## 🔧 Troubleshooting

### Issue: "Type has no attribute '_state'"
- **Cause**: Your model class does not inherit from `MutableMixin` or `LazyMutableMixin`.
- **Solution**: Ensure your Pydantic/Dataclass/Attrs model inherits from one of the provided mixins.

### Issue: Changes not saved to database
- **Cause**: SQLAlchemy only detects changes if `flag_modified` is called, which `sqlatypemodel` does automatically. If it's not working, ensure `session.commit()` is actually called.
- **Solution**: Verify that your model is properly registered and that you are using `session.commit()`.

### Issue: Pickle deserialization loses tracking
- **Cause**: Standard `MutableMixin` might need manual re-initialization if not using the recommended patterns.
- **Solution**: Use `LazyMutableMixin` for more robust pickle support, or ensure `_restore_tracking()` is called if implementing custom deserialization.

---

## License

MIT
