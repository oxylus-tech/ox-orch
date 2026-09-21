.. _cli-applications:

Applications
============

Introduction
------------

Ox-Orch operations can be used directly to perform individual tasks, such as
installing packages or running migrations. The application framework provides a higher-level model for managing complete applications.

An application is represented by metadata and associated state. This allows
Ox-Orch to manage a desired set of applications and keep track of their
lifecycle across multiple executions.

The framework is provided by :py:mod:`ox_orch.apps` and
:py:mod:`ox_orch.operations.apps`.

Why use applications?
.....................

Installing a package does not necessarily mean that an application is ready to
use. An application may require additional lifecycle operations, such as
migrations or configuration.

The application framework separates:

- The applications that should be present;
- The operations required to bring them to their desired state.

This allows Ox-Orch to manage and reconcile an application environment rather
than treating every lifecycle action as an isolated operation.

When to use it
..............

The application framework is optional.

Use regular operations when executing individual tasks directly. Use the
application framework when managing applications as persistent units whose
state must be tracked and reconciled across executions.


Application
-----------

An application represent a manageable unit in an Ox-Orch environment. Applications are described using metadata, such as their identifier, version, or supported features. It describe what an application is and what capabilities it provides:

.. code-block:: yaml

    ox-erp:
      # Unique application identifier
      id: ox-erp
      # Human readable name
      name: Oxylus ERP
      # Python package name
      package: ox-erp
      # Python package version
      version: 0.28.1
      # Optional: package source, as git or file uri
      source: null
      # Optional: dependencies
      dependencies: []
      # Optional: features
      features: {}

The complete list of fields can be looked up in the API documentation of the :py:class:`~ox_orch.apps.app.Application`.

It is important to understand that **an Application is not a python package**, as we don't go over package managers territory. It rather is a separate generic concept.

The main command use is ``apps``:

.. code-block:: bash

    ox-orch apps # subcommand here...

Dependencies
............

An application can declare dependencies which are indeed other registered ones on the store. It does not have to reflect the exact python package's one, and allows you to select upon which the workflow will run over.

Lets say you have another application that requires this one:

.. code-block:: yaml

    ox-fin:
      id: ox-fin
      name: Oxylus Finances
      package: ox-fin
      version: 0.14.0
      # Depends on ox-erp app
      dependencies:
      - "ox-erp==0.28.1"

Applications Store
..................

Applications are kept in :ref:`a store <cli-store>` specific to them. The one used by the cli tool loads and saves in files.

The simplest way to create a new store an have a sample is to import a package from Pypi, using ``apps import``:

.. code-block:: bash

    # We use YAML format for readability, but json is allowed to.
    ox-orch apps import <PATH> <PACKAGES...>

    # Example:
    ox-orch apps import apps.yaml oxylus

The list applications of a store, you can use ``apps list``:

.. code-block:: bash

    ox-orch apps list apps.yaml


State
.....

An application state represent the current state of an application in a specific environment. While application describes the application itself, the state contains information procuded while managing that application (eg. as running a workflow result).

This allows the same application definition to be used accross multiple environments, each with its own independent state, as they are stored separately from applications themselves. As so, they have their own store.

Some fields of the application state (see :py:class:`ox_orch.apps.state.AppState`):

.. code-block:: yaml

    id: ox-fin
    version: 0.14.0
    # Installed package
    package: ox-fin
    # Source from which the package has been installed
    source: ox-fin

In practice you don't need to write or handle manually the states of application.


Operations
----------

The main operation for working with applications is ``apps``. It runs a reconciliation for each application requested by user:

.. code-block:: python

    __type_id__: apps
    # This is a list of operations to run for each application.
    reconciliation:
    - my-app-op-1
    - __type_id__: my-app-op-2
      value: 123

    # Other optional operations:
    before_install: null  # before install
    install: null         # install operation
    after_install: null   # after install, before reconcile
    operations: []        # after reconciliation

Example context (:py:class:`~ox_orch.operations.apps.AppsContextInput`):

.. code-block:: python

    apps:
      # List of applications: they shall be present in the store
      apps: ["ox-fin"]

      # Configure the file store.
      store_backend: file
      store_args:
          path: ./path/to/app_store.yaml

      # Configure the app state store.
      state_store_backend: file
      state_store_args:
          path: ./path/to/app_state_store.yaml

Installation mode
.................

When you provide an install operations to ``apps``, only the updated applications and dependencies will be reconciled.

.. code-block:: yaml

    apps:
        install: "install:pip"
        reconciliation:
        - my-app-opp-1
        - my-app-opp-2

With the context:

.. code-block:: yaml

    apps:
        apps: ["ox-fin", "ox-erp", "ox-core"]

        # ... other config here

Imagine that ox-fin or some application's dependency is updated, then reconciliation will run for them only. If ox-erp is not updated, then no reconciliation.


Features
--------

Some external libraries may need extra information on the application, as :ref:`django integration <cli-django>` does. You can add them under the ``features`` key:

.. code-block:: yaml

    id: ox-fin
    name: Oxylus Finances
    package: ox-fin
    version: 0.14.1
    features:
        # Add the feature on the application for django operations.
        django:
            # The list of Django application paths used for INSTALLED_APPS settings.
            apps:
            - ox_erp.contacts
            - ox_erp.locations

The operations may also add features on the application states, as:

.. code-block:: yaml

    id: ox-fin
    # ...
    features:
        django:
            enabled: false

Thoses are generated by operations.
