# sqlatypemodel

[![Tests](https://github.com/GrehBan/sqlatypemodel/actions/workflows/tests.yml/badge.svg)](https://github.com/GrehBan/sqlatypemodel/actions/workflows/tests.yml)
[![PyPI version](https://badge.fury.io/py/sqlatypemodel.svg)](https://badge.fury.io/py/sqlatypemodel)
[![Python versions](https://img.shields.io/pypi/pyversions/sqlatypemodel.svg)](https://pypi.org/project/sqlatypemodel/)

**Typed JSON fields for SQLAlchemy with automatic mutation tracking.**

By default, SQLAlchemy does not detect in-place changes inside JSON columns. `sqlatypemodel` solves this problem, allowing you to work with strictly typed Python objects (Pydantic, Dataclasses, Attrs, or custom classes) while ensuring all changes are automatically saved to the database.

## Key Features

* **Seamless Integration:** Store Pydantic models directly in SQLAlchemy columns.
* **Universal Support:** Works with **Pydantic (V1 & V2)**, **Dataclasses**, **Attrs**, and custom classes.
* **Protocol Based:** Does not require strict inheritance from `BaseModel`—any class implementing `model_dump`/`model_validate` works.
* **Mutation Tracking:** Built-in `MutableMixin` detects deep changes (e.g., `user.data.list.append("item")`) and flags the row for update.
* **High Performance:**
* **O(1) Wrapping:** Smart "short-circuit" logic prevents re-wrapping already tracked collections.
* **Atomic Optimization:** Skips overhead for atomic types (`int`, `str`, `bool`).
* **Optimized Updates:** Avoids expensive serialization (`model_dump`) on every attribute change.



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

## Performance Benchmarks

`sqlatypemodel` is designed for high-load production environments. We benchmarked assignment operations to ensure minimal overhead.

**Test Scenario:** Assigning a pre-filled list of **100,000 integers** to a model field.

| Operation | Complexity | Time (100k items) | Notes |
| --- | --- | --- | --- |
| **Naive Re-wrapping** | O(N) | ~0.15s+ | Recursively traversing and wrapping every item. |
| **sqlatypemodel** | **Optimized** | **<0.01s** | Uses identity checks to skip re-wrapping known collections. |
| **Change Detection** | **O(1)** | **Instant** | Uses `id()` comparison instead of deep equality checks. |

*Benchmarks run on Python 3.14, Pydantic V2.*

## How Automatic Mutation Tracking Works

When you inherit from `MutableMixin`, the class automatically registers itself with `ModelType` using Python's `__init_subclass__` hook. This means:

1. You don't need to call `.as_mutable()` explicitly.
2. All instances are automatically tracked for changes.
3. Both direct field mutations AND nested collection changes are detected.

You can disable this behavior by setting `auto_register=False`:

```python
class MyModel(MutableMixin, BaseModel, auto_register=False):
    pass

```

## Advanced Usage

`sqlatypemodel` is not limited to Pydantic. You can use it with any class by providing `json_dumps` and `json_loads`, or by implementing the **Pydantic Protocol** (`model_dump` / `model_validate`).

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

### Custom Classes (Protocol Approach)

Instead of passing lambdas, your class can implement the protocol:

```python
class MyBucket(MutableMixin):
    def __init__(self, items):
        self.items = items
    
    # Implement Pydantic Protocol
    def model_dump(self, mode="python"):
        return {"items": self.items}
    
    @classmethod
    def model_validate(cls, data):
        return cls(data["items"])

# No extra arguments needed!
bucket_col: Mapped[MyBucket] = mapped_column(ModelType(MyBucket))

```

## Important Caveats

### Identity Hashing

To support robust parent tracking (required for nested mutation detection), `MutableMixin` enforces **identity-based hashing** (`object.__hash__`) or requires you to enable it (for dataclasses). Do not use these models as keys in `dict` or `set` if you rely on value equality.

### Thread Safety & Concurrency

`sqlatypemodel` is thread-safe and supports SQLAlchemy's unit-of-work pattern. Each session tracks mutations independently.

## Verification & Stress Testing

Reliability is paramount. We include a forensic-grade stress test suite (`tests/stress_test.py`) that anyone can run to verify the library's claims.

The suite performs:
1.  **Rollback Integrity Check:** Verifies that Python objects revert to their original state after a DB transaction rollback.
2.  **Deep Recursion Fuzzing:** Modifies deeply nested JSON structures (10+ levels) to ensure `MutableMixin` propagates dirty flags correctly.
3.  **Concurrency Race Condition Test:** Spawns multiple threads writing to the same SQLite database (in WAL/locked mode) to ensure no data loss occurs under load.

### Run it yourself:

```bash
python tests/stress_test.py
```
### Example Output

<details> <summary>Click to expand full stress test log</summary>

```
====================================================================================================
  SQLATYPEMODEL DEEP TRACE | PID: 68678
  System: linux | Python: 3.14.2
====================================================================================================

[    15.001ms] [MEM: 58.32MB] [MainThread] [ SQL_REQ  ] Executing: PRAGMA main.table_info("stress_entities") | Params: ()
[    15.170ms] [MEM: 58.45MB] [MainThread] [ SQL_RES  ] Done in 173.175µs
[    15.370ms] [MEM: 58.45MB] [MainThread] [ SQL_REQ  ] Executing: PRAGMA temp.table_info("stress_entities") | Params: ()
[    15.498ms] [MEM: 58.57MB] [MainThread] [ SQL_RES  ] Done in 127.009µs
[    16.019ms] [MEM: 58.57MB] [MainThread] [ SQL_REQ  ] Executing: 
CREATE TABLE stress_entities (
	id INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	raw_list JSON NOT NULL, 
	complex_data JSON, 
	tree_data JSON NOT NULL, 
	strict_data JSON, 
	PRIMARY KEY (id)
)

 | Params: ()
[    16.142ms] [MEM: 58.57MB] [MainThread] [ SQL_RES  ] Done in 123.081µs

--------------------------------------------------
TEST 1: ROLLBACK INTEGRITY
--------------------------------------------------
[    16.314ms] [MEM: 58.57MB] [MainThread] [ STEP_IN  ] >>> Setup Entity
[    22.790ms] [MEM: 59.20MB] [MainThread] [ SQL_REQ  ] Executing: INSERT INTO stress_entities (name, raw_list, complex_data, tree_data, strict_data) VALUES (?, ?, ?, ?, ?) | Params: ('RollbackTest', '{"items": []}', 'null', '{"name": "original", "value": 0, "children": [], "tags": [], "meta": {}}', 'null')
[    22.976ms] [MEM: 59.20MB] [MainThread] [ SQL_RES  ] Done in 195.418µs
[    25.702ms] [MEM: 59.32MB] [MainThread] [ SQL_REQ  ] Executing: SELECT stress_entities.id AS stress_entities_id, stress_entities.name AS stress_entities_name, stress_entities.raw_list AS stress_entities_raw_list, stress_entities.complex_data AS stress_entities_complex_data, stress_entities.tree_data AS stress_entities_tree_data, stress_entities.strict_data AS stress_entities_strict_data 
FROM stress_entities 
WHERE stress_entities.id = ? | Params: (1,)
[    25.819ms] [MEM: 59.32MB] [MainThread] [ SQL_RES  ] Done in 119.925µs
[    26.236ms] [MEM: 59.32MB] [MainThread] [  STATE   ] Entity created. ID: 1
[    26.273ms] [MEM: 59.32MB] [MainThread] [ STEP_OUT ] <<< Setup Entity DONE in 9927.452µs
[    26.301ms] [MEM: 59.32MB] [MainThread] [ STEP_IN  ] >>> Mutation Phase
[    26.421ms] [MEM: 59.32MB] [MainThread] [  CHECK   ] Session Dirty: True
[    26.448ms] [MEM: 59.32MB] [MainThread] [ STEP_OUT ] <<< Mutation Phase DONE in 126.638µs
[    26.470ms] [MEM: 59.32MB] [MainThread] [ STEP_IN  ] >>> Rollback Operation
[    26.583ms] [MEM: 59.32MB] [MainThread] [  STATE   ] Rollback issued
[    26.604ms] [MEM: 59.32MB] [MainThread] [ STEP_OUT ] <<< Rollback Operation DONE in 115.277µs
[    26.625ms] [MEM: 59.32MB] [MainThread] [ STEP_IN  ] >>> Verification
[    26.948ms] [MEM: 59.32MB] [MainThread] [ SQL_REQ  ] Executing: SELECT stress_entities.id AS stress_entities_id, stress_entities.name AS stress_entities_name, stress_entities.raw_list AS stress_entities_raw_list, stress_entities.complex_data AS stress_entities_complex_data, stress_entities.tree_data AS stress_entities_tree_data, stress_entities.strict_data AS stress_entities_strict_data 
FROM stress_entities 
WHERE stress_entities.id = ? | Params: (1,)
[    26.997ms] [MEM: 59.32MB] [MainThread] [ SQL_RES  ] Done in 48.862µs
[    27.216ms] [MEM: 59.32MB] [MainThread] [   READ   ] Current Name: original
[    27.240ms] [MEM: 59.32MB] [MainThread] [   READ   ] Current Value: 0
[    27.261ms] [MEM: 59.32MB] [MainThread] [ STEP_OUT ] <<< Verification DONE in 619.996µs

--------------------------------------------------
TEST 2: DEEP RECURSION & TRACKING
--------------------------------------------------
[    27.388ms] [MEM: 59.32MB] [MainThread] [ STEP_IN  ] >>> Build Tree (Depth 10)
[    27.822ms] [MEM: 59.32MB] [MainThread] [ SQL_REQ  ] Executing: INSERT INTO stress_entities (name, raw_list, complex_data, tree_data, strict_data) VALUES (?, ?, ?, ?, ?) | Params: ('DeepTest', '{"items": []}', 'null', '{"name": "root", "value": 0, "children": [{"name": "L0", "value": 0, "children": [{"name": "L1", "value": 0, "children": [{"name": "L2", "value": 0, "children": [{"name": "L3", "value": 0, "children": [{"name": "L4", "value": 0, "children": [{"name": "L5", "value": 0, "children": [{"name": "L6", "value": 0, "children": [{"name": "L7", "value": 0, "children": [{"name": "L8", "value": 0, "children": [{"name": "L9", "value": 0, "children": [], "tags": [], "meta": {}}], "tags": [], "meta": {}}], "tags": [], "meta": {}}], "tags": [], "meta": {}}], "tags": [], "meta": {}}], "tags": [], "meta": {}}], "tags": [], "meta": {}}], "tags": [], "meta": {}}], "tags": [], "meta": {}}], "tags": [], "meta": {}}], "tags": [], "meta": {}}', 'null')
[    27.895ms] [MEM: 59.32MB] [MainThread] [ SQL_RES  ] Done in 75.542µs
[    28.129ms] [MEM: 59.32MB] [MainThread] [ STEP_OUT ] <<< Build Tree (Depth 10) DONE in 714.394µs
[    28.155ms] [MEM: 59.32MB] [MainThread] [ STEP_IN  ] >>> Navigate to Leaf
[    28.428ms] [MEM: 59.32MB] [MainThread] [ SQL_REQ  ] Executing: SELECT stress_entities.id AS stress_entities_id, stress_entities.name AS stress_entities_name, stress_entities.raw_list AS stress_entities_raw_list, stress_entities.complex_data AS stress_entities_complex_data, stress_entities.tree_data AS stress_entities_tree_data, stress_entities.strict_data AS stress_entities_strict_data 
FROM stress_entities 
WHERE stress_entities.id = ? | Params: (2,)
[    28.474ms] [MEM: 59.32MB] [MainThread] [ SQL_RES  ] Done in 46.858µs
[    28.917ms] [MEM: 59.32MB] [MainThread] [   INFO   ] Reached leaf at depth 10
[    28.942ms] [MEM: 59.32MB] [MainThread] [ STEP_OUT ] <<< Navigate to Leaf DONE in 766.531µs
[    28.966ms] [MEM: 59.32MB] [MainThread] [ STEP_IN  ] >>> Modify Leaf
[    28.982ms] [MEM: 59.32MB] [MainThread] [  MUTATE  ] Adding tag to leaf set
[    29.019ms] [MEM: 59.32MB] [MainThread] [  MUTATE  ] Changing leaf integer value
[    29.052ms] [MEM: 59.32MB] [MainThread] [ STEP_OUT ] <<< Modify Leaf DONE in 69.911µs
[    29.074ms] [MEM: 59.32MB] [MainThread] [ STEP_IN  ] >>> Check Tracking
[    29.126ms] [MEM: 59.32MB] [MainThread] [  CHECK   ] Entity is_modified: True
[    29.150ms] [MEM: 59.32MB] [MainThread] [  CHECK   ] Session dirty contains entity: True
[    29.169ms] [MEM: 59.32MB] [MainThread] [ STEP_OUT ] <<< Check Tracking DONE in 78.277µs
[    29.189ms] [MEM: 59.32MB] [MainThread] [ STEP_IN  ] >>> Commit
[    30.113ms] [MEM: 59.32MB] [MainThread] [ SQL_REQ  ] Executing: UPDATE stress_entities SET tree_data=? WHERE stress_entities.id = ? | Params: ('{"name": "root", "value": 0, "children": [{"name": "L0", "value": 0, "children": [{"name": "L1", "value": 0, "children": [{"name": "L2", "value": 0, "children": [{"name": "L3", "value": 0, "children": [{"name": "L4", "value": 0, "children": [{"name": "L5", "value": 0, "children": [{"name": "L6", "value": 0, "children": [{"name": "L7", "value": 0, "children": [{"name": "L8", "value": 0, "children": [{"name": "L9", "value": 42, "children": [], "tags": ["touched_at_bottom"], "meta": {}}], "tags": [], "meta": {}}], "tags": [], "meta": {}}], "tags": [], "meta": {}}], "tags": [], "meta": {}}], "tags": [], "meta": {}}], "tags": [], "meta": {}}], "tags": [], "meta": {}}], "tags": [], "meta": {}}], "tags": [], "meta": {}}], "tags": [], "meta": {}}', 2)
[    30.218ms] [MEM: 59.32MB] [MainThread] [ SQL_RES  ] Done in 106.219µs
[    30.479ms] [MEM: 59.32MB] [MainThread] [ STEP_OUT ] <<< Commit DONE in 1271.501µs
[    30.507ms] [MEM: 59.32MB] [MainThread] [ STEP_IN  ] >>> Verify Persistence
[    31.354ms] [MEM: 59.32MB] [MainThread] [ SQL_REQ  ] Executing: SELECT stress_entities.id, stress_entities.name, stress_entities.raw_list, stress_entities.complex_data, stress_entities.tree_data, stress_entities.strict_data 
FROM stress_entities 
WHERE stress_entities.name = ? | Params: ('DeepTest',)
[    31.468ms] [MEM: 59.32MB] [MainThread] [ SQL_RES  ] Done in 116.710µs
[    31.928ms] [MEM: 59.45MB] [MainThread] [   READ   ] Leaf Tags: MutableSet({'touched_at_bottom'})
[    31.956ms] [MEM: 59.45MB] [MainThread] [ STEP_OUT ] <<< Verify Persistence DONE in 1426.153µs

--------------------------------------------------
TEST 3: CONCURRENCY THREADING
--------------------------------------------------
[    32.091ms] [MEM: 59.45MB] [MainThread] [ STEP_IN  ] >>> Concurrency Setup
[    32.836ms] [MEM: 59.45MB] [MainThread] [ SQL_REQ  ] Executing: INSERT INTO stress_entities (name, raw_list, complex_data, tree_data, strict_data) VALUES (?, ?, ?, ?, ?) RETURNING id | Params: ('T1', '{"items": [0]}', 'null', 'null', 'null')
[    32.946ms] [MEM: 59.45MB] [MainThread] [ SQL_RES  ] Done in 110.879µs
[    32.988ms] [MEM: 59.45MB] [MainThread] [ SQL_REQ  ] Executing: INSERT INTO stress_entities (name, raw_list, complex_data, tree_data, strict_data) VALUES (?, ?, ?, ?, ?) RETURNING id | Params: ('T2', '{"items": [0]}', 'null', 'null', 'null')
[    33.026ms] [MEM: 59.45MB] [MainThread] [ SQL_RES  ] Done in 39.504µs
[    33.319ms] [MEM: 59.45MB] [MainThread] [ STEP_OUT ] <<< Concurrency Setup DONE in 1205.167µs
[    33.385ms] [MEM: 59.45MB] [MainThread] [ STEP_IN  ] >>> Running Threads
[    33.563ms] [MEM: 59.45MB] [Th-Worker-1] [  THREAD  ] Worker 1 started for T1
[    33.665ms] [MEM: 59.45MB] [Th-Worker-1] [ STEP_IN  ] >>> Read T1
[    34.078ms] [MEM: 59.45MB] [Th-Worker-1] [ SQL_REQ  ] Executing: SELECT stress_entities.id, stress_entities.name, stress_entities.raw_list, stress_entities.complex_data, stress_entities.tree_data, stress_entities.strict_data 
FROM stress_entities 
WHERE stress_entities.name = ? | Params: ('T1',)
[    33.704ms] [MEM: 59.45MB] [Th-Worker-2] [  THREAD  ] Worker 2 started for T2
[    34.211ms] [MEM: 59.45MB] [Th-Worker-2] [ STEP_IN  ] >>> Read T2
[    34.500ms] [MEM: 59.45MB] [Th-Worker-2] [ SQL_REQ  ] Executing: SELECT stress_entities.id, stress_entities.name, stress_entities.raw_list, stress_entities.complex_data, stress_entities.tree_data, stress_entities.strict_data 
FROM stress_entities 
WHERE stress_entities.name = ? | Params: ('T2',)
[    34.172ms] [MEM: 59.45MB] [Th-Worker-1] [ SQL_RES  ] Done in 94.919µs
[    34.810ms] [MEM: 59.45MB] [Th-Worker-1] [ STEP_OUT ] <<< Read T1 DONE in 1085.391µs
[    34.851ms] [MEM: 59.45MB] [Th-Worker-2] [ SQL_RES  ] Done in 349.918µs
[    35.070ms] [MEM: 59.45MB] [Th-Worker-2] [ STEP_OUT ] <<< Read T2 DONE in 828.559µs
[    40.423ms] [MEM: 59.45MB] [Th-Worker-1] [  THREAD  ] Finished mutations. Waiting for Write Lock...
[    40.506ms] [MEM: 59.45MB] [Th-Worker-1] [   LOCK   ] Acquired Lock (waited 0.001ms). Committing...
[    41.248ms] [MEM: 59.45MB] [Th-Worker-1] [ SQL_REQ  ] Executing: UPDATE stress_entities SET raw_list=? WHERE stress_entities.id = ? | Params: ('{"items": [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]}', 3)
[    41.343ms] [MEM: 59.45MB] [Th-Worker-2] [  THREAD  ] Finished mutations. Waiting for Write Lock...
[    41.484ms] [MEM: 59.45MB] [Th-Worker-1] [ SQL_RES  ] Done in 239.090µs
[    41.728ms] [MEM: 59.45MB] [Th-Worker-1] [   LOCK   ] Commit done. Releasing Lock.
[    41.804ms] [MEM: 59.57MB] [Th-Worker-2] [   LOCK   ] Acquired Lock (waited 0.368ms). Committing...
[    42.051ms] [MEM: 59.57MB] [Th-Worker-2] [ SQL_REQ  ] Executing: UPDATE stress_entities SET raw_list=? WHERE stress_entities.id = ? | Params: ('{"items": [0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2]}', 4)
[    42.109ms] [MEM: 59.57MB] [Th-Worker-2] [ SQL_RES  ] Done in 59.522µs
[    42.306ms] [MEM: 59.57MB] [Th-Worker-2] [   LOCK   ] Commit done. Releasing Lock.
[    42.383ms] [MEM: 59.57MB] [MainThread] [ STEP_OUT ] <<< Running Threads DONE in 8975.010µs
[    42.416ms] [MEM: 59.57MB] [MainThread] [ STEP_IN  ] >>> Verify Threads
[    42.829ms] [MEM: 59.57MB] [MainThread] [ SQL_REQ  ] Executing: SELECT stress_entities.id, stress_entities.name, stress_entities.raw_list, stress_entities.complex_data, stress_entities.tree_data, stress_entities.strict_data 
FROM stress_entities 
WHERE stress_entities.name = ? | Params: ('T1',)
[    42.897ms] [MEM: 59.57MB] [MainThread] [ SQL_RES  ] Done in 68.068µs
[    43.264ms] [MEM: 59.57MB] [MainThread] [ SQL_REQ  ] Executing: SELECT stress_entities.id, stress_entities.name, stress_entities.raw_list, stress_entities.complex_data, stress_entities.tree_data, stress_entities.strict_data 
FROM stress_entities 
WHERE stress_entities.name = ? | Params: ('T2',)
[    43.317ms] [MEM: 59.57MB] [MainThread] [ SQL_RES  ] Done in 52.188µs
[    43.490ms] [MEM: 59.57MB] [MainThread] [  RESULT  ] T1 Items: 51 (Exp: 51)
[    43.512ms] [MEM: 59.57MB] [MainThread] [  RESULT  ] T2 Items: 51 (Exp: 51)
[    43.588ms] [MEM: 59.57MB] [MainThread] [ STEP_OUT ] <<< Verify Threads DONE in 1145.665µs

==================================================
[    43.649ms] [MEM: 59.57MB] [MainThread] [  FINAL   ] ✅ ALL CHECKS PASSED. NO ANOMALIES DETECTED.
==================================================
[    43.682ms] [MEM: 59.57MB] [MainThread] [  SYSTEM  ] Trace finished. Closing file.
```

## License

MIT