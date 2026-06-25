ox-orch
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


Features
---------

The system models application lifecycle as a graph of operations.

The library in the main lines allows:

- Composable operation system for lifecycle workflows. Workflows can be nested and pipelines reusable.
- Plan-based orchestration of multiple operations
- Deterministic execution graph with dependency resolution
- Explicit state tracking per operation, with forward/backward diff model for safe rollback (+ rollback on failure).
- Application store
- Framework-agnostic design (Django support optional)
- Load and save states and operations workflow into YAML;

Currently supported operations:

- Core operations: base operation, run python function, plan execution, shell invokation;
- App installation and reconciliation operations;
- Django specific operations (migrations, collect statics, manage command);
- Python packages installation: pip, uv, poetry;


Why ox-orch
-----------

The initial reason of this project was to allow application installation into Django by the end-user.
Despite this initial goal, we want it to be reusable for other use cases.

Modern deployment and lifecycle management is often fragmented across scripts, tooling, and manual steps. This leads to inconsistent environments, fragile rollback strategies and hidden side effects among other things...

``ox-orch`` solves this by introducing a unified execution model where:

- every change is explicit
- every operation is reversible
- execution is deterministic
- workflows are composable

This makes complex lifecycle operations safe to run, inspect, and replay.


Advantages
----------

- **Deterministic execution**: identical input produces identical outcomes
- **Safe rollback**: rollback is based on recorded diffs, not ad-hoc logic
- **Composable architecture**: operations can be nested and reused
- **Clear separation of concerns**: execution, state, and persistence are decoupled
- **Framework independence**: no hard dependency on Django or any runtime
- **Auditability**: every change is tracked as structured state

What's next?
------------

The long-term goal of ``ox-orch`` is to make application lifecycle management feel safe, predictable, and
almost invisible in day-to-day operations. Installing, updating, and evolving applications should not require fragile
scripts or manual intervention, but instead rely on a structured system that understands state, dependencies, and
recovery.

A key direction is seamless application installation and runtime update workflows. The system is designed to eventually
handle full application lifecycle transitions, including dependency installation, database migrations, and controlled
restart of running services (for example Django servers) without breaking consistency or requiring downtime beyond what
is strictly necessary.

This will be achieved through a hybrid model combining a programmable backend and a CLI tool. The backend will expose
orchestration capabilities through APIs that can be integrated into custom environments or existing platforms, while the
CLI will provide a direct, reliable interface for local and operational use.

Although Django is an important initial target, the architecture is intentionally kept platform-agnostic. Django support
will be provided through dedicated adapters, while the core engine remains reusable for other ecosystems and deployment
targets.

Planned capabilities include:

- Seamless package installation with environment reconciliation
- Safe database migration orchestration with rollback support
- Controlled restart and reload of running services (e.g. Django apps)
- API-based orchestration backend for integration into custom systems
- CLI tool for direct execution of plans and operations
- Plugin/adapters system for platform-specific behaviors (Django, future frameworks)
