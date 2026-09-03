.. _cli-overview:

Overview
========

Ox-Orch provides a command line interface for executing and managing
orchestration workflows.

The command line utility exposes the same state-driven execution model as the
Python API. Workflows are described as operations, executed through an
executor and represented by explicit states.

This makes it possible to execute application lifecycle workflows from a shell
while retaining deterministic execution, execution feedback and rollback
capabilities.

The command line interface is primarily intended for tasks such as:

- Applying an application lifecycle workflow;
- Inspecting the current execution state;
- Rolling back a previous execution;
- Managing application reconciliation;
- Running operations defined by an Ox-Orch configuration.

The CLI does not introduce a separate execution model. Instead, it acts as an
interface around the core Ox-Orch concepts.

Core concepts
-------------

The command line interface is built around the same concepts as the Ox-Orch
execution engine.

Operation
.........

An *Operation* represents a unit of behavior that can be executed by
Ox-Orch.

Operations are declarative and serializable. Their configuration describes
what the operation should do, independently from a particular execution.

Depending on the operation, it may perform actions such as:

- Installing or updating an application;
- Reconciling applications with their desired configuration;
- Applying database migrations;
- Running application-specific lifecycle tasks.

Operations may also be composed together. A
:py:class:`~ox_orch.operations.plan.Plan` is an operation that coordinates
multiple nested operations.

The command line utility executes a root operation, which may itself contain
an arbitrarily complex hierarchy of nested operations.

State
.....

Every operation execution produces a *State*.

A state represents the current result of an operation and records the
information required to understand and potentially reverse its execution.

During execution, an operation transitions through different statuses. These
transitions provide the command line interface with execution feedback and
allow the resulting state to be persisted.

Operation states may contain:

- The current execution status;
- The operation identifier;
- The history of status transitions;
- Information produced during execution;
- Data required for rollback.

Plans additionally produce nested states corresponding to their child
operations.

The resulting state is therefore a representation of the executed workflow,
rather than merely a success or failure result.

Execution
.........

An execution combines an operation with the information required to run it.

The execution process is coordinated by an
:py:class:`~ox_orch.core.execution.Executor`.

The executor is responsible for initializing the execution context, running
operations, producing state changes and coordinating hooks and persistence.

The command line interface exposes this execution process through commands
that apply or roll back operations.

Configuration and execution context
...................................

Ox-Orch distinguishes between operation configuration and execution input.

The configuration of an operation describes the operation itself. Because
operations are Pydantic models, this configuration must be serializable.

The execution context contains the information required for a particular run.

This distinction is important when using the command line interface.

A workflow configuration should describe *what* Ox-Orch is expected to do.
Runtime services, project integrations and other execution-specific objects
are provided by the execution environment rather than embedded directly in the
workflow definition.

This separation allows workflows and their resulting states to remain
serializable and portable.


Lifecycle
---------

A typical Ox-Orch command line workflow follows the lifecycle below:

#. A workflow configuration is loaded;
#. The requested operation is resolved;
#. The execution context is initialized;
#. The operation is applied;
#. State changes are reported during execution;
#. The resulting state may be persisted;
#. The execution may later be rolled back using that state.

Rollback is therefore based on the result of a previous execution rather than
on a separate manually written reverse script.


Command reference
-----------------

The command line utility is organized around subcommands.

Each subcommand represents a high-level action that can be performed against
an Ox-Orch workflow.

The command reference documents:

- Available subcommands;
- Positional arguments;
- Optional arguments;
- Input and configuration files;
- State handling;
- Execution and rollback behavior.

See :doc:`commands` for the complete command line reference.


Available operations
--------------------

The operations available to the command line utility depend on the installed
Ox-Orch packages and integrations.

You can list operations using:

.. code-block:: shell

    ox-orch info operations

Operations provide the actual behavior executed by a workflow. They may be
generic Ox-Orch operations or operations provided by an integration.

For example, an integration may provide operations for:

#. Application installation;
#. Application reconciliation;
#. Database migrations;
#. Framework-specific lifecycle management.

Operations can also be composed into plans in order to describe larger
workflows.

See :doc:`operations` for the list of available operations.

Typical usage
-------------

A typical workflow starts by applying an operation:

.. code-block:: bash

    $ ox-orch apply <configuration>

During execution, Ox-Orch reports state changes produced by the operation and
its nested operations.

Once the execution has completed, the resulting state can be used to inspect
the execution or to perform a rollback.

A rollback follows the inverse lifecycle:

.. code-block:: bash

    $ ox-orch rollback <state>

The exact arguments and available subcommands are documented in the
:doc:`commands` section.

Next steps
----------

To get started with the command line utility:

1. Read :doc:`concepts` to understand the execution model;
2. Read :doc:`commands` for the command line reference;
3. Browse :doc:`operations` to discover available operations;
4. See :doc:`examples` for complete workflow examples.
