Extend Ox-Orch
--------------

Create custom operations
........................

You can create your own operations, by simply subclassing :py:class:`ox_orch.operations.base.Operation` and registering it.

When creating a custom operation you MUST ensure to:

- provide both :py:meth:`~ox_orch.operations.base.Operation._apply` and :py:meth:`~ox_orch.operations.base.Operation._rollback`
- always provide consistent state transition between rollback and apply;
- register the operation and its state (if provided) when you aim to use them directly (for non-abstract operations);


.. code-block:: python

    from ox_orch.core import register
    from ox_orch.operations import Operation, OperationState

    # Optionally provide a custom state to keep track of changes.
    @register("custom-operation")
    class CustomState(OperationState):
        previous_value: int|None = None
        value: int = 0

    @register("custom-operation")
    class CustomOperation(Operation):
        # Define the state class used by the operation
        __state_class__ = CustomState

        def _apply(self, state: CustomState, exec_ctx, **inputs):
            state.previous_value = state.value
            state.value = state.value + 1

        def _rollback(self, state: CustomState, exec_ctx, **inputs):
            state.value = state.previous_value

As you may already know, Operation and OperationState are both :py:class:`~ox_orch.core.pydantic.PolymorphicModel` subclasses, each assigned to a different registry.
This allows us to use the same key safely, whilst keeping coherent naming patterns.

You can also yield states from the overriden methods, which will be handled upstream. This is for example what :py:class:`~ox_orch.operations.plan.Plan` or :py:class:`~ox_orch.operations.apps.AppsPlan` do. This allows to provide feedback to end-user all along the running process:


.. code-block:: python

    # Just for the sake of example, this code is NOT SAFE to run as it does
    # not provide safe state transition.

    class CustomOperation(Operation):
        nested: Operation|None = None

        def _apply(self, state, exec_ctx, **inputs):
            if self.nested:
                inputs["custom_state"] = state
                yield from self.nested.apply(state, exec_ctx, **inputs)

        def _rollback(self, state, exec_ctx, **inputs):
            if self.nested:
                inputs["custom_state"] = state
                yield from self.nested.rollback(state, exec_ctx, **inputs)


Registries
..........

In ``ox-orch``, the :py:class:`~ox_orch.core.registry.Registry` class is used
at different places, mostly to handle different kind of :py:class:`~ox_orch.core.pydantic.PolymorphicModel`.

Classes as ``Operation``, ``OperationState`` are subclass the ``Registry`` one,
set the register to use on the attribute ``__registry__``:

.. code-block:: python

    from ox_orch.core import RegisteredClass, Registry


    POLYGON_REGISTRY = Registry()

    class Polygon(RegisteredClass):
        __registry__ = Registry()


The subclasses will then register using the :py:func:`~ox_orch.core.registry.register` decorator:

.. code-block:: python

    from ox_orch.core import register

    @register("square")
    class Square(Polygon):
        pass

    @register("Circle")
    class Circle(Polygon):
        pass

    # ...

    assert "square" in POLYGON_REGISTRY
    assert "circle" in POLYGON_REGISTRY

    square_cls = POLYGON_REGISTRY.get("square")

    # raises a ValueError
    POLYGON_REGISTRY.get("not_a_polygon")
