.. _cli-django:

Django Integration
==================

One of the primarily goal of ox-orch was to be deploy applications and hot-reload a running Django server. Lets just focus for the deployment part now, later we'll see how to dynamically install and add applications.


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
      - __type_id__: django:setup            # ensure django is setup
      - __type_id__: django:migrate          # run migrations
      - __type_id__: django:collectstatic    # collect statics
      - __type_id__: django:compilemessages  # compile i18n messages
      # - other operations can go here...
      # Or here, after the fork run

If you're lazy (and you should be on a good manner), you can use the ``django:reconciliation``. It is a plan that already includes thoses operations in this specified order:

.. code-block:: yaml

    operation:
      __type_id__: django:reconciliation

You can add other operations at different places using the following fields on the reconciliation:

- :py:attr:`~ox_orch.django.operations.DjangoProjectSync.before_migrate` (as a list): to run before migrations happen.
- :py:attr:`~ox_orch.django.operations.DjangoProjectSync.after_migrate` (as a list): to run just after migrations.
- ``operations``: to run after all the previous operations.

.. code-block:: yaml

    operation:
      __type_id__: django:reconciliation
      after_migrate:
       - __type_id__: shell
         forward: ["echo", "migrations done!"]
         backward: ["echo", "migrations reverted!"]


Dynamic application enabling
----------------------------

The main constraint of Django is that once the project is setup and runs, it is actually not possible to cleanly reload the configuration. New or updated application won't be taken in account, and this is by design.

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
      # Use UV to install packages
      install: install:uv
      operations:
      # Ensure installed packages are enabled
      - __type_id__: django:enable
      # Fork into a new subprocess ensuring django reinitialization
      - __type_id__: fork
        operation:
          __type_id__: django:reconciliation

Requirements
............

The ``django:enable`` operation works using the application framework of ox-orch, as we need to keep track of the enabled applications at two places: within the ox-orch workflow and the Django project.

You'll need to setup:

- An application store and state store that provides django-related information (as feature);
- The Django project to get the list of enabled application;
- The ox-orch workflow;


Setup django:

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
