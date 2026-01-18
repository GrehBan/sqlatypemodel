Usage Guide
===========

This comprehensive guide covers all aspects of using ``sqlatypemodel`` in production applications.

Table of Contents
-----------------

1.  :ref:`getting-started`
2.  :ref:`integration-pydantic`
3.  :ref:`integration-dataclasses`
4.  :ref:`integration-attrs`
5.  :ref:`loading-strategies`
6.  :ref:`async-support`
7.  :ref:`custom-serialization`
8.  :ref:`error-handling`
9.  :ref:`advanced-patterns`

.. _getting-started:

Getting Started
---------------

The core concept is simple: replace standard Python types in your database models with ``sqlatypemodel``-enhanced classes.

1.  **Inherit**: Make your data model inherit from ``MutableMixin`` (or ``LazyMutableMixin``).
2.  **Wrap**: Use ``ModelType(YourModel)`` in the SQLAlchemy column definition.
3.  **Use**: Mutate objects freely; changes are auto-saved.

.. _integration-pydantic:

Pydantic Integration
--------------------

Pydantic is the primary citizen of ``sqlatypemodel``. We support Pydantic V2 fully.

Basic Model
~~~~~~~~~~~

.. code-block:: python

    from pydantic import BaseModel
    from sqlatypemodel import MutableMixin

    class Profile(MutableMixin, BaseModel):
        bio: str | None = None
        preferences: dict[str, bool] = {}

Entity Definition
~~~~~~~~~~~~~~~~~

.. code-block:: python

    from sqlalchemy.orm import Mapped, mapped_column
    from sqlatypemodel import ModelType

    class User(Base):
        __tablename__ = "users"
        # ...
        profile: Mapped[Profile] = mapped_column(ModelType(Profile))

Nested Models
~~~~~~~~~~~~~

You can nest Pydantic models arbitrarily. Changes deep in the hierarchy bubble up.

.. code-block:: python

    class Address(MutableMixin, BaseModel):
        city: str
        zip: str

    class UserData(MutableMixin, BaseModel):
        addresses: list[Address] = []

    # Usage
    user.data.addresses[0].city = "New York" # Detected!

.. _integration-dataclasses:

Python Dataclasses
------------------

We provide first-class support for standard library ``dataclasses``.

The Safe Wrapper
~~~~~~~~~~~~~~~~

While standard dataclasses work, Python 3.12+ introduced optimizations that can cause recursion loops during initialization of mutable tracking objects. We recommend using our wrapper which enforces safe defaults (``eq=False``, ``slots=False``).

.. code-block:: python

    from sqlatypemodel.util.dataclasses import dataclass
    from sqlatypemodel import MutableMixin

    @dataclass
    class Config(MutableMixin):
        host: str
        port: int = 8080

Manual Mapping
~~~~~~~~~~~~~~

For dataclasses, you usually provide a serializer/deserializer to ``ModelType``, as they don't have built-in ``.model_dump()`` methods like Pydantic.

.. code-block:: python

    from dataclasses import asdict

    col = mapped_column(
        ModelType(
            Config,
            dumper=asdict,
            loader=lambda d: Config(**d)
        )
    )

.. _integration-attrs:

Attrs Integration
-----------------

Similar to dataclasses, we support ``attrs``.

.. code-block:: python

    from attrs import asdict, define
    from sqlatypemodel.util.attrs import define as safe_define
    from sqlatypemodel import MutableMixin

    @safe_define
    class AppState(MutableMixin):
        status: str

    # Mapping
    col = mapped_column(
        ModelType(
            AppState,
            dumper=asdict,
            loader=lambda d: AppState(**d)
        )
    )

.. _loading-strategies:

Loading Strategies: Eager vs Lazy
---------------------------------

Choosing the right mixin is the most important performance decision.

MutableMixin (Eager)
~~~~~~~~~~~~~~~~~~~~

*   **Behavior**: Scans and wraps the *entire* object graph immediately upon loading from the database.
*   **Pros**:
    *   Fastest attribute access after load (no "jit tax").
    *   Predictable performance profile.
*   **Cons**:
    *   Slower DB load time for large objects.
    *   Higher memory usage (wrappers created for everything).
*   **Best For**: Write-heavy scenarios, small objects, or when you traverse the whole object anyway.

LazyMutableMixin (Lazy)
~~~~~~~~~~~~~~~~~~~~~~~

*   **Behavior**: Loads raw data. Wraps only what you touch.
*   **Pros**:
    *   **2x Faster** DB loads.
    *   **35% Less** memory.
*   **Cons**:
    *   First access to any field is slower (wrapping overhead).
*   **Best For**: Read-heavy scenarios, large documents where you only read a few fields (e.g. API filtering).

.. _async-support:

Async Support
-------------

``sqlatypemodel`` is fully compatible with ``sqlalchemy.ext.asyncio``.

Helpers
~~~~~~~

We provide helpers to create async engines with optimized JSON serializers pre-configured.

.. code-block:: python

    from sqlatypemodel.util.sqlalchemy import create_async_engine

    engine = create_async_engine("postgresql+asyncpg://...")

Context Manager
~~~~~~~~~~~~~~~

When using ``AsyncSession``, the workflow is identical to sync code.

.. code-block:: python

    async with AsyncSession(engine) as session:
        user = await session.get(User, 1)
        user.settings.theme = "dark"
        await session.commit()

.. _custom-serialization:

Custom Serialization
--------------------

By default, ``ModelType`` attempts to use Pydantic's ``model_dump(mode='json')`` for serialization and ``model_validate`` for deserialization. You can override this behavior.

Using ``dumper`` and ``loader``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is useful for non-Pydantic models (like Dataclasses) or when you need custom logic.

.. code-block:: python

    def my_dumper(obj: MyModel) -> dict:
        return {"custom_field": obj.field}

    def my_loader(data: dict) -> MyModel:
        return MyModel(field=data["custom_field"])

    col = mapped_column(
        ModelType(
            MyModel,
            dumper=my_dumper,
            loader=my_loader
        )
    )

.. _error-handling:

Error Handling
--------------

The library provides specific exceptions for serialization failures.

Exceptions
~~~~~~~~~~

*   ``SQLATypeModelError``: Base exception for all library errors.
*   ``SerializationError``: Raised when an object cannot be converted to a dictionary for DB storage.
*   ``DeserializationError``: Raised when database data cannot be converted back to a model instance.

Usage
~~~~~

.. code-block:: python

    from sqlatypemodel.exceptions import DeserializationError

    try:
        session.commit()
    except DeserializationError as e:
        print(f"Failed to load model {e.model_name}: {e.original_error}")

.. _advanced-patterns:

Advanced Patterns
-----------------

Batching Changes
~~~~~~~~~~~~~~~~

If you are performing thousands of mutations in a loop, you can suppress intermediate signals to save CPU cycles.

.. code-block:: python

    with user.settings.batch_changes():
        for _ in range(1000):
            user.settings.log.append("entry")
    # Single change notification fired here

Deep Nesting
~~~~~~~~~~~~

The library handles arbitrary nesting (dicts of lists of models of dicts...).
By default, there is a recursion limit of 100 to prevent stack overflows. You can customize this:

.. code-block:: python

    class DeepModel(MutableMixin, BaseModel):
        _max_nesting_depth = 500
        # ...

Pickling & Caching
~~~~~~~~~~~~~~~~~~

You can pickle your models and store them in Redis/Memcached. When unpickled, they automatically reconnect their internal tracking mechanisms.

.. code-block:: python

    import pickle

    # Save to cache
    data = pickle.dumps(user.settings)
    redis.set("user:1:settings", data)

    # Load from cache
    settings = pickle.loads(redis.get("user:1:settings"))
    settings.theme = "blue" # Tracking still works!

Development & CI/CD
-------------------

Code Quality
~~~~~~~~~~~~

Before contributing, ensure all checks pass locally:

.. code-block:: bash

    # Install pre-commit hooks
    pre-commit install

    # Run all quality checks
    pre-commit run --all-files

    # Or manually:
    poetry run ruff check src/sqlatypemodel tests --fix
    poetry run black src/sqlatypemodel tests
    poetry run mypy src/sqlatypemodel

Testing
~~~~~~~

Run tests locally to ensure your changes work:

.. code-block:: bash

    # All tests
    poetry run pytest -v

    # With coverage
    poetry run pytest -v --cov=sqlatypemodel --cov-report=term-missing

    # Specific test category
    poetry run pytest tests/unit/ -v

GitHub Actions
~~~~~~~~~~~~~~

All code is automatically tested via GitHub Actions:

- **tests.yml**: Tests on Python 3.10-3.14 with databases
- **lint.yml**: Code quality checks (ruff, black, mypy, pre-commit)
- **security.yml**: Weekly security scanning
- **docs.yml**: Documentation building
- **publish.yml**: Automated PyPI publishing on release

See `.github/WORKFLOWS.md <https://github.com/GrehBan/sqlatypemodel/blob/master/.github/WORKFLOWS.md>`_ for complete information.

Releases
~~~~~~~~

Releases are fully automated:

1. Update version in ``pyproject.toml``
2. Update ``CHANGELOG.md``
3. Commit and push to ``master``
4. Create a GitHub Release (UI)
5. ✅ Automated: Package published to PyPI in ~2-3 minutes!

See `.github/WORKFLOWS.md <https://github.com/GrehBan/sqlatypemodel/blob/master/.github/WORKFLOWS.md>`_ for publishing workflow details.
