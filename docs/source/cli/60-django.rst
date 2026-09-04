.. _cli-django:

Django Integration
==================

Introduction
------------

One of the primarily goal of ox-orch was to be install and hot-reload application within django project.

The main constraint of Django is that once the project is setup and runs, it is actually not possible to cleanly reload the configuration. New or updated application won't be taken in account, and this is by design.

This problem shall be break down in two parts:

#. First, how to setup newly installed application or updated ones;
#. Second, the django running server must be reloaded;

We will currently only address in this document on the first problem which is the most important. We later provide a solution for the second one (which in theory is not really that hard).

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
          # This needs to run within a plan, as fork only accept one operation.
          __type_id__: plan
          operations:
          - __type_id__: django:setup            # ensure django is setup
          - __type_id__: django:migrate          # run migrations
          - __type_id__: django:collectstatic    # collect statics
          - __type_id__: django:compilemessages  # compile i18n messages
          # - other operations can go here...
      # Or here, after the fork run

If you're lazy (and should on a good manner), you can use the ``django:reconciliation`` within the fork. It ensures that those operations runs:

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
          # optionally, you can add other tasks
          # after_migrate:
          #  - __type_id__: shell
          #    forward: ["echo", "migrations done!"]
          #    backward: ["echo", "migrations reverted!"]


Available Django operations
...........................

Here is a list of the Django operation, with a brief description for each. You can find more information in the technical documentation of the module :py:mod:`ox_orch.django.operations`:

- ``django:enable``: enable django applications.
- ``django:setup``: initialize the django framework.
- ``django:manage``: run a django management command.
- ``django:collectstatic``: collect statics.
- ``django:compilemessages``: compile I18n messages.
- ``django:migrate``: run django applications migrations.
- ``django:reconciliation``: run common django reconciliation as migrations, collect static etc.


Full setup
----------

We however will have to provide more information on the Django project and the applications, which are:

#. Context: provide context information about the django project.
#. Applications: provide information on packages that actually contains django applications.
#. Setup the Django project in order to dynamically load new information and ensure application dependencies.
