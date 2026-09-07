.. _cli-django:

Django Integration
==================

One of the primarily goal of ox-orch was to be deploy applications and hot-reload a running Django server. Lets just focus for the deployment part now, later we'll see how to dynamically install and add applications.

The code lies in the :py:mod:`ox_orch.django` module.

Quickstart
----------

Here is a list of the Django operations, with a brief description for each. You can find more information in the technical documentation of the module :py:mod:`ox_orch.django.operations`:

- ``django:enable``: enable django applications.
- ``django:setup``: initialize the django framework.
- ``django:manage``: run a django management command.
- ``django:collectstatic``: collect statics.
- ``django:compilemessages``: compile I18n messages.
- ``django:migrate``: run django applications migrations.
- ``django:reconciliation``: run common django reconciliation as migrations, collect static etc.

A simple setup to deploy application update is the following:

.. code-block:: yaml

    operation:
      __type_id__: plan
      operations:
      - "django:setup"            # ensure django is setup
      - "django:migrate"          # run migrations
      - "django:collectstatic"    # collect statics
      - "django:compilemessages"  # compile i18n messages
      # - other operations can go here...
      # Or here, after the fork run

If you're lazy (and you should be on a good manner), you can use the ``django:reconciliation``. It is a plan that already includes thoses operations in this specified order:

.. code-block:: yaml

    operation: "django:reconciliation"

You can add other operations at different places using the following fields on the reconciliation:

- :py:attr:`~ox_orch.django.operations.DjangoProjectSync.before_migrate` (as a list): to run before migrations happen.
- :py:attr:`~ox_orch.django.operations.DjangoProjectSync.after_migrate` (as a list): to run just after migrations.
- ``operations``: to run after all the previous operations.

.. code-block:: yaml

    operation:
      __type_id__: "django:reconciliation"
      after_migrate:
       - __type_id__: shell
         forward: ["echo", "migrations done!"]
         backward: ["echo", "migrations reverted!"]


Context
.......

This is the context used over Django related operations (:py:class:`~ox_orch.django.operations.DjangoContextInput`):

.. code-block:: yaml

    django:
        project_path: "/path/to/the/project"
        settings_module: "my_project.settings"


Running
.......

You need to load the :py:mod:`ox_orch.django` module as the following:

.. code-block:: bash

    ox-orch -m "ox_orch.django" run -c context.yaml apply django.yaml


Managed applications mode
-------------------------

The main constraint of Django is that once the project is setup and runs, it is actually not possible to cleanly reload the configuration. New or updated applications won't be taken in account, and this is by design.

This problem shall be break down in two parts:

#. First, how to setup newly installed application or updated ones;
#. Second, the django running server must be reloaded;

We will currently only address here the first problem which is the most important. We later provide a solution for the second one (which in theory is not really that hard).

First approach
..............

Lets envision a simple Django pipeline, what you usually have is:

#. Install or update applications package.
#. Enable thoses applications.
#. Apply migrations.
#. Collect static data.
#. Eventually run other django related tasks

At step 1 or 2, Django is already setup as you'll have to fetch data from it in a coherent and structured way. If not already required, remember that your pipeline may fail mid-way, which means that you certainly want to roll back to keep coherent project state.

How can we do then? The answer actually is simple (though harder to implement): spawn a new subprocess.

This is where the ``fork`` operation goes in, which results in:

.. code-block:: yaml

    operation:
      __type_id__: apps
      # Use Pip to install packages
      install: "install:pip"
      operations:
      # Ensure installed packages are enabled
      - "django:enable"
      # Fork into a new subprocess ensuring django reinitialization
      - __type_id__: fork
        operation: "django:reconciliation"

Requirements
............

The ``django:enable`` operation works using the application framework of ox-orch, as we need to keep track of the enabled applications at two places: within the ox-orch workflow and the Django project.

You'll need to setup:

- An application store and state store that provides django-related information (as feature)..
- The Django project to get the list of enabled application;
- The ox-orch workflow;


Setup Application and stores
............................

To provide django capabilities and information, we add the ``django`` feature on applications and states (:py:class:`~ox_orch.django.project.DjangoAppFeature`)`:

.. code-block:: yaml

    id: ox-fin
    name: Oxylus Finances
    package: ox-fin
    version: 0.14.1
    features:
        # Add the feature on the application
        django:
            # The list of Django application paths used for INSTALLED_APPS settings.
            apps:
            - ox_erp.contacts
            - ox_erp.locations

Please refer to :ref:`this documentation <cli-applications>` for detailed information about applications.

The generated application state will have an assigned feature too (:py:class:`~ox_orch.django.project.DjangoStateFeature`):

.. code-block:: yaml

    id: ox-fin
    features:
        django:
            enabled: true


Setup django
............

.. code-block:: python

    # settings.py

    from pathlib import Path

    from ox_orch.django import DjangoApps
    from ox_orch.apps import AppStateFileStore

    BASE_DIR = Path(__file__).resolve().parent.parent.parent

    django_apps = DjangoApps(state_store=AppStateFileStore(BASE_DIR / "app_states.json"))
    django_apps.state_store.load()

    # ...

    # Put the ox-orch app list before the default ones.
    # Lookups/overrides (templates, statics, ...) are in ascending order.
    # This means implicitely that apps dependencies are in reverse one.
    INSTALLED_APPS = django_apps.get_installed_apps() + [
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.sites",
        "django.contrib.messages",
        "django.contrib.staticfiles",
    ]

    # ...


Workflow
........

Example setup:

.. code-block:: yaml

    # Reuse the previous example
    operation:
      __type_id__: apps
      # Use Pip to install packages
      install: "install:pip"
      operations:
      # Ensure installed packages are enabled
      - "django:enable"
      # Fork into a new subprocess ensuring django reinitialization
      - __type_id__: fork
        operation: "django:reconciliation"

Note that we don't use the reconciliation mechanisms of the ``apps`` operation, since ``django:reconciliation`` works independently of apps update.

What you set as reconciliation operations will run for any installed/updated application and their dependencies:

.. code-block:: yaml

    # Reuse the previous example
    operation:
      __type_id__: apps
      # ...
      reconciliation:
      - "django:enable"
      operations:
      - __type_id__: fork
        operation: "django:reconciliation"

Only updated and installed applications or dependencies will be enabled.


Context
.......

You need to provide information to the ``apps`` and ``django:enable`` operations:

.. code-block:: yaml

    # Used by ``apps`` and ``django:enable``
    apps:
      apps: ["ox-fin"]
      store_backend: file
      store_args:
          path: ./path/to/app_store.yaml
      state_store_backend: file
      state_store_args:
          path: ./path/to/app_state_store.yaml

    # Django context
    django:
        project_path: "/path/to/the/project"
        settings_module: "my_project.settings"


Running
.......

Once you got all those pieces, you can just run it:

.. code-block:: bash

    ox-orch -m "ox_orch.django" run -c context.yaml apply django.yaml -s trace.yaml
