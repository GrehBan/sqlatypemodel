sqlatypemodel
=============

.. image:: https://github.com/GrehBan/sqlatypemodel/actions/workflows/tests.yml/badge.svg
   :target: https://github.com/GrehBan/sqlatypemodel/actions/workflows/tests.yml
   :alt: Tests

.. image:: https://github.com/GrehBan/sqlatypemodel/actions/workflows/lint.yml/badge.svg
   :target: https://github.com/GrehBan/sqlatypemodel/actions/workflows/lint.yml
   :alt: Linting

.. image:: https://img.shields.io/pypi/status/sqlatypemodel.svg?style=flat-square
    :target: https://pypi.python.org/pypi/sqlatypemodel
    :alt: PyPi status

.. image:: https://img.shields.io/pypi/v/sqlatypemodel.svg?style=flat-square
    :target: https://pypi.python.org/pypi/sqlatypemodel
    :alt: PyPi Package Version

.. image:: https://img.shields.io/pypi/pyversions/sqlatypemodel.svg
   :target: https://pypi.org/project/sqlatypemodel/
   :alt: Python versions

.. image:: https://img.shields.io/pypi/dm/sqlatypemodel.svg?style=flat-square
    :target: https://pypi.python.org/pypi/sqlatypemodel
    :alt: Downloads

.. image:: https://img.shields.io/pypi/l/sqlatypemodel.svg?style=flat-square
    :target: https://opensource.org/licenses/MIT
    :alt: MIT License

Typed JSON fields for SQLAlchemy with automatic mutation tracking
==================================================================

**sqlatypemodel** solves the "immutable JSON" problem in SQLAlchemy. It allows you to use strictly typed Python objects (**Pydantic**, **Dataclasses**, **Attrs**) as database columns while ensuring that **every change—no matter how deep—is automatically saved.**

Powered by **orjson** for blazing-fast performance and featuring a **State-Based Architecture** for universal compatibility.

Key Features
------------

* **State-Based Tracking:** Universal compatibility with unhashable objects (Pydantic, Dataclasses).
* **Maximum Performance:** 40%+ speedup in hot paths via direct attribute access and dispatch optimization.
* **Lazy Loading:** 2.1x faster DB loading and 35% less memory usage.
* **Pickle & Celery Ready:** Full support for serialization and caching.
* **High Performance:** Powered by ``orjson`` with smart caching.
* **Deep Mutation Tracking:** Automatically detects nested changes.

The Problem
-----------

By default, SQLAlchemy considers JSON columns immutable unless you replace the entire object.

.. code-block:: python

    # ❌ NOT persisted by default in SQLAlchemy
    user.settings.theme = "dark"
    user.settings.tags.append("new")

    session.commit() # Nothing happens! Data is lost.

The Solution
------------

With ``sqlatypemodel``, in-place mutations are tracked automatically:

.. code-block:: python

    # ✅ Persisted automatically
    user.settings.theme = "dark"
    user.settings.tags.append("new")

    session.commit() # UPDATE "users" SET settings = ...

Resources
---------

*   :doc:`installation`
*   :doc:`usage`
*   :doc:`examples`
*   :doc:`api`
*   :doc:`changelog`

License
-------

MIT
