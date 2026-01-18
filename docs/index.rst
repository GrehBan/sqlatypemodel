Welcome to sqlatypemodel's documentation!
===========================================

Typed JSON fields for SQLAlchemy with automatic mutation tracking.

**sqlatypemodel** solves the "immutable JSON" problem in SQLAlchemy. It allows you to use strictly typed Python objects
(**Pydantic**, **Dataclasses**, **Attrs**) as database columns while ensuring that every change—no matter how deep—is automatically saved.

Quick Links
===========

* **PyPI**: https://pypi.org/project/sqlatypemodel/
* **GitHub**: https://github.com/GrehBan/sqlatypemodel
* **CI/CD**: `GitHub Actions <https://github.com/GrehBan/sqlatypemodel/actions>`_

CI/CD Status
============

* |tests| `Tests <https://github.com/GrehBan/sqlatypemodel/actions/workflows/tests.yml>`_
* |lint| `Linting <https://github.com/GrehBan/sqlatypemodel/actions/workflows/lint.yml>`_
* |security| `Security <https://github.com/GrehBan/sqlatypemodel/actions/workflows/security.yml>`_
* |docs| `Documentation <https://github.com/GrehBan/sqlatypemodel/actions/workflows/docs.yml>`_

.. |tests| image:: https://github.com/GrehBan/sqlatypemodel/actions/workflows/tests.yml/badge.svg
.. |lint| image:: https://github.com/GrehBan/sqlatypemodel/actions/workflows/lint.yml/badge.svg
.. |security| image:: https://github.com/GrehBan/sqlatypemodel/actions/workflows/security.yml/badge.svg
.. |docs| image:: https://github.com/GrehBan/sqlatypemodel/actions/workflows/docs.yml/badge.svg

Documentation
=============
.. toctree::
   :maxdepth: 2
   :caption: sqlatypemodel Documentation:

   readme
   modules

.. toctree::
   :maxdepth: 2
   :caption: Getting Started:

   installation
   usage
   configuration

.. toctree::
   :maxdepth: 2
   :caption: Reference:

   api
   architecture
   best_practices
   caveats
   examples

.. toctree::
   :maxdepth: 2
   :caption: Development:

   contributing
   changelog


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
