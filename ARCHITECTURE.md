# Architecture Overview

## Module Dependency Graph

```text
sqlatypemodel/
├── model_type/
│   ├── model_type.py (depends on mixin for BaseMutableMixin)
│   └── protocols.py
├── mixin/
│   ├── mixin.py (main MutableMixin, LazyMutableMixin)
│   ├── events.py (tracks changes)
│   ├── wrapping.py (wraps mutable objects)
│   ├── state.py (MutableState token)
│   ├── serialization.py (pickle support)
│   ├── inspection.py (introspection logic)
│   ├── _introspection_data.py (Internal: Skip lists and atomic types)
│   ├── protocols.py (Trackable and MutableMixin protocols)
│   └── types.py (Custom Keyable collection types)
└── util/
    ├── _sentinel.py (Internal: MISSING and DELETED constants)
    ├── constants.py (Public constants like DEFAULT_MAX_NESTING_DEPTH)
    ├── json.py (orjson integration with fallback)
    ├── sqlalchemy.py (Engine and AsyncEngine factory helpers)
    ├── dataclasses.py (Safe @dataclass wrapper)
    └── attrs.py (Safe @define wrapper)
```

## Key Architectural Principles

### 1. State-Based Tracking (`MutableState`)
Instead of relying on unstable `__hash__` implementations which often break when using Pydantic or Dataclasses, `sqlatypemodel` uses a **token-based** approach.
- Every trackable object is assigned a `MutableState` token.
- This token is hashable and acts as a stable key in `WeakKeyDictionary` lookups.
- This allows the library to support **unhashable** objects (e.g., Pydantic models with `frozen=False`) natively.

### 2. The Bubble-Up Signal Pattern
Mutations are detected at the "leaf" level (e.g., a `list.append()`) and propagate upwards:
1. **Leaf**: Triggers `self.changed()`.
2. **Events**: `safe_changed` iterates over `_parents` (stored as `MutableState` tokens).
3. **Propagation**: If a parent is another `MutableMixin`, it calls `parent.changed()` recursively.
4. **Root**: When the signal reaches the SQLAlchemy entity, it calls `attributes.flag_modified(entity, key)`.

### 3. Just-In-Time (JIT) Wrapping
For high-performance scenarios, `LazyMutableMixin` uses Python's `__getattribute__` hook to defer the expensive recursive wrapping process.
- **Initial Load**: Objects are loaded as raw `dict`/`list` from the database.
- **Access**: Only when an attribute is accessed is it wrapped into a `MutableList` or `MutableDict`.
- **Performance**: Reduces initialization time by up to **150x** for large datasets.

### 4. Pickle & Task Queue Compatibility
The library is designed for distributed systems (Celery/Redis/RabbitMQ).
- Tracking state is automatically cleaned up before pickling (`__getstate__`).
- Tracking is transparently restored upon unpickling (`__setstate__`) via the `_restore_tracking` hook.

## Internal Safety Mechanisms
- **Recursion Protection**: `DEFAULT_MAX_NESTING_DEPTH` prevents infinite loops in circular object graphs.
- **Thread Safety**: `MutableState` links/unlinks are guarded by `threading.RLock`.
- **Serialization Fallback**: If `orjson` fails (e.g., 128-bit integers), the library automatically falls back to the standard `json` module.