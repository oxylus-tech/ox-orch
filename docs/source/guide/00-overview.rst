Overview
========

Ox-Orch is a state-driven orchestration engine for deterministic application lifecycle management.

It provides a structured way to define, execute, and rollback complex workflows such as package installation, migrations
and application reconciliation. It replaces imperative deployment scripts with a composable, state-based execution model.


Quickstart
----------

Define a workflow:

.. code-block:: python

    from ox_orch.operations import AppsPlan, UvInstall
    from ox_orch.django import DjangoReconciliation

    install_apps = AppsPlan(
        install=UvInstall(),
        after_install=DjangoReconciliation(),
    )


Both operations and states are serializable as pydantic models, allowing to provide them through API or using configuration files.

Once the workflow is defined, you will execute it like this:

.. code-block:: python

    from ox_orch.operations.execution import Executor, ExecutionSpec
    from ox_orch.apps import Application, AppsContext, AppMemoryStore, AppStateMemoryStore
    from ox_orch.hooks import LoggingHook

    # ...

    # We have to provide apps_ctx to AppsPlan, which gather:
    # - An app store: store applications, here in memory
    # - An app state store: store application states, in memory too;
    # - A list of apps metadata to use
    applications = [
        # By default, package is set to the id
        Application(id="test-1", version="0.0.1"),
        Application(id="test-2", version="1.4.2", package="test-2-pkg"),
        Application(id="test-3", version="1.4.3", package="test-3-pkg")
    ]

    apps_ctx = AppsContext.from_apps_ids(
        ["test-1", "test-2"],
        store=AppMemoryStore(items=applications),
        state_store=AppStateMemoryStore(),
    )

    spec = ExecutionSpec(
        # The operation to execute
        operation=install_apps,
        # Add a hook that logs all states changes
        hooks = [LoggingHook()],
        # Some user input values if needed.
        # inputs={},
    )
    executor = Executor()

    # Dummy invocation example, when you need to get state, eg. feedback to
    # to client's API.
    for state in executor.apply(spec, apps_ctx=apps_ctx):
        print(f"[{state.operation_id}] {state.status}")

    # Another way to invoke without looping over it:
    state = executor.apply_sync(spec, apps_ctx=apps_ctx)


Rollback becomes trivial:

.. code-block::

    rb_state = executor.rollback_sync(spec, state, apps_ctx=apps_ctx)

    # That's it.


.. note::

    We could have passed down ``apps_ctx`` to ExecutionSpec's ``input``. However, it would be wrong.

    The goal of this class is to provide user's input data to run the execution, which implies that they shall be serializable and only data oriented. User can not inject custom code or behavior.


Concepts
--------

The two main concepts in Ox-Orch are *Operation* and *State*.

An operation describes a unit of behavior that can be applied and rolled back.
A state represents the current and historical execution information associated
with that operation.

Together they provide a deterministic execution model where every action
produces an explicit state transition. Most other components of Ox-Orch
(executors, plans, hooks and stores) exist to coordinate, observe or persist
those transitions.


Small summary of the concepts:

- Operation: the core abstraction to run an action. A :py:class:`~ox_orch.operations.plan.Plan` allows to run multiple
  operation sequentially.
- State: keep track of the operation execution state.
- Executor: the class responsible to run the operation, providing feedback about what is happening.
- Store: store state and data in order to reuse them, using different backends.


Operation
.........

The :py:class:`~ox_orch.operations.base.Operation` is the base unit of action. It is responsible for:

- Apply and rollback execution;
- Track of the execution using states;
- Persist and restore execution state;
- Expose deterministic and reproducible behavior;
- Validate operation-specific configuration;
- Emit execution events through state transitions;
- Integrate with executors, hooks and stores;
- Provide reconciliation capabilities when supported by subclasses;

Operations are declarative objects describing *what* should happen rather than
*how* to execute a deployment script. They are designed to be serializable,
composable and reusable across different execution environments.

It has two main methods:

- :py:meth:`~ox_orch.operations.base.Operation.apply`: run the operation;
- :py:meth:`~ox_orch.operations.base.Operation.rollback`: reverse the operation using provided state;

Both actually yields :py:class:`~ox_orch.operations.OperationState` to the caller, allowing to keep him updated about the different state changes.

An important subclass of Operation is :py:class:`~ox_orch.operations.plan.Plan`, allowing multiple nested operations to run. Though the Plan class only handles providing them as a list, the subclasses may implement different behaviors.

You must distinct two kind of input for an operation:

- *The configuration of the operation itself* static accross different calls over different execution contexts. This MUST be Pydantic's serializable data, as Operation are Pydantic models.
- *The running context* which provides user inputs arguments among other contextual values used for apply/rollback.


State
.....

The :py:class:`~ox_orch.core.state.State` is responsible for:

- Keeping track of the actual status of the execution (PENDING, COMPLETED, FAILED, ...);
- Validate transition between the different status;
- Keeping information required to rollback the operation;
- Optionally provide extra information;
- Persist execution progress;
- Store execution results and metadata;
- Allow interrupted executions to resume safely;
- Provide a deterministic representation of an operation lifecycle;

For an operation, the actual state class used is :py:class:`~ox_orch.operations.base.OperationState` that adds the following:

- Link to an operation (by id);
- Keep an history of status changes;
- Keep the run context (only on the root operation state);
- Nested states for plan state and derived (subclassing :py:class:`~ox_orch.core.state.TreeState`);
- Store operation-specific rollback data;
- Track execution timestamps and diagnostics;

Executor
........

The executor is the main utility class that you'll need to run operations. It handles:

- Load a provided configuration (:py:class:`~ox_orch.operations.execution.ExecutionSpec`);
- Initialize the context used for running operations;
- Run the operation(s), calling hooks at different stages;
- Create and manage operation states;
- Coordinate state persistence through stores;
- Handle rollback execution;
- Restore previous execution states when provided;
- Emit execution events and notifications;
- Provide synchronous and streaming execution APIs;
- Propagate execution context to nested operations;


Store
.....

Stores are responsible for persisting data used by the orchestration engine.

Ox-Orch distinguishes between two broad categories of stores:

- Metadata stores, which provide access to managed resources;
- State stores, which persist operation execution states.

Stores may use various backends such as in-memory implementations,
filesystems, databases or remote services.

By abstracting persistence behind dedicated interfaces, operations remain
independent from the underlying storage technology.
