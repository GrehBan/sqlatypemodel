Configuration
=============

``sqlatypemodel`` works out of the box with zero configuration, but you can tune it for specific needs.

Nesting Depth Limit
-------------------

To prevent stack overflow errors or denial-of-service attacks via deeply nested JSON payloads, the library enforces a maximum recursion depth during change tracking.

**Default:** 100 levels

**How to change:**

Override the ``_max_nesting_depth`` attribute on your model class.

.. code-block:: python

    class DeepModel(MutableMixin, BaseModel):
        _max_nesting_depth = 500  # Allow deeper nesting

        data: dict | list

    # Or set it on the instance
    model = DeepModel()
    model._max_nesting_depth = 1000

Change Suppression
------------------

The library maintains an internal counter ``_change_suppress_level`` to support batch operations. While you normally use the ``batch_changes()`` context manager, you can inspect this value for debugging.

.. code-block:: python

    print(model._change_suppress_level)  # 0 usually

SQLAlchemy Engine
-----------------

To use ``orjson`` (recommended for performance), you must configure the SQLAlchemy engine.

**Helper Function (Recommended):**

.. code-block:: python

    from sqlatypemodel.util.sqlalchemy import create_engine

    # Automatically injects json_serializer/json_deserializer
    engine = create_engine("sqlite:///")

**Manual Configuration:**

.. code-block:: python

    from sqlalchemy import create_engine
    from sqlatypemodel.util.json import get_serializers

    dumps, loads = get_serializers()

    engine = create_engine(
        "sqlite:///",
        json_serializer=dumps,
        json_deserializer=loads
    )

Environment Variables
---------------------

You can control behavior via environment variables:

.. code-block:: bash

    # Enable verbose logging for change tracking
    export SQLATYPEMODEL_DEBUG=1

    # Disable orjson and use stdlib json
    export SQLATYPEMODEL_NO_ORJSON=1

Testing Configuration
---------------------

For testing, use in-memory SQLite database:

.. code-block:: python

    from sqlatypemodel.util.sqlalchemy import create_engine

    engine = create_engine("sqlite:///:memory:")

See `.github/WORKFLOWS.md <https://github.com/GrehBan/sqlatypemodel/blob/master/.github/WORKFLOWS.md>`_ for CI/CD configuration.
