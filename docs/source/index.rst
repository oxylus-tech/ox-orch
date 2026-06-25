Ox-Orch
=======

A state-driven orchestration engine for deterministic application lifecycle management.

``ox-orch`` provides a structured way to define, execute, and rollback complex workflows such as package installation, migrations, and application reconciliation. It replaces imperative deployment scripts with a composable, state-based execution model.


Example of a plan to install or update Django applications:


.. code-block:: python

    from ox_orch.operations import AppsPlan, UvInstall, ForkOperation
    from ox_orch.django import DjangoEnable, DjangoReconciliation

    install_apps = AppsPlan(
        install=UvInstall(),
        operations=[
            DjangoEnable(),
            ForkOperation(
                operation=DjangoReconciliation(),
            )
        ]
    )



Documentation
-------------

Guide
.....

.. toctree::
   :maxdepth: 2

   guide


API
...


.. toctree::
   :maxdepth: 2

   api
