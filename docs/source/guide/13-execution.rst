.. _guide-execution:

Execution
=========

We have seen how operations work, and part of the elements composing the stack of ox-orch. Lets discover an important one, as it is the entry point for it, ensuring the connection between user interface and the operation.

Basically:

- The :py:class:`~ox_orch.operations.execution.ExecutionSpec` provides initial arguments to the Executor (apply / rollback).
- The :py:class:`~ox_orch.operations.execution.Executor` method will:
    - Ensure context initialization and run the operation.
    - Emit event to registered hooks at different stages (see :py:mod:`ox_orch.hooks`).
    - Run the operation yielding back operation states;
- :py:class:`~ox_orch.operations.execution.ExecutionContext` will be provided as ``exec_ctx`` context value;

.. image:: ../static/guide-execution.png


*So why an executor?*

Providing it for a simple operation doesn't seem to worth it. However lets take a different perspective:

- As the number of nested operations of a Plan grows, they will require more and more context data;
- We want the end user to provide input for those context in a coherent way;
- We want extra arguments to provide to all operations, as dry-run or the :py:mod:`~ox_orch.core.shell` to use (nb: allowing to run shell commands). This is for example used by the install operations to know in which environment to run the package installer.


.. code-block:: python

    op = MyOperation()
    spec = ExecutionSpec(
        operation=MyOperation(),
        hooks=["logging"],
        inputs={
            # This will resolve to custom MyContext registered as "my_ctx"
            "my_ctx": {"name": "Alice"},
            # Example AppsContext configuration
            "apps_ctx": {
                "store_backend": "file",
                "store_args": {"path": "/tmp/apps.json"},
                "state_store": "memory",
            }
        }
    )

    # You can de-serialize spec:
    data = spec.model_dump(mode="json")
    spec = ExecutionSpec.model_validate(data)


Create and run:

.. code-block:: python

    executor = Executor()

    # You may provide context as named argument here, they'll override any
    # value provided by the spec inputs.
    # As for example: apply(spec, apps_ctx=apps_ctx)
    for state in executor.apply(spec):
        print(state)

    # IF you don't want to iterate, but only run:
    state = executor.apply_sync(spec)
