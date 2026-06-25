.. guide-operations:

Operations
==========

The :py:class:`~ox_orch.operations.base.Operation` is the base unit of action. It is responsible for:

- Apply and rollback execution, as *deterministic and reproducible* behavior;
- Validate operation-specific configuration;
- Emit execution events through state transitions;

Operations are declarative objects describing *what* should happen rather than
*how* to execute a deployment script. They are designed to be serializable,
composable and reusable across different execution environments.

It has two main methods:

- :py:meth:`~ox_orch.operations.base.Operation.apply`: run the operation;
- :py:meth:`~ox_orch.operations.base.Operation.rollback`: reverse the operation using provided state;

Both actually yields :py:class:`~ox_orch.operations.base.OperationState` to the caller, allowing to keep him updated about the different state changes.

An important subclass of Operation is :py:class:`~ox_orch.operations.plan.Plan`, allowing multiple nested operations to run. Though the Plan class only handles providing them as a list, the subclasses may implement different behaviors.

You must distinct two kind of input for an operation:

- *The configuration of the operation itself*: static accross different calls over different execution contexts. This MUST be Pydantic's serializable data, as Operation are Pydantic models.
- *The context*: provides user inputs arguments among other contextual values used for apply/rollback (list of applications, application store, django project, etc.).


Basic mechanisms of an operation
--------------------------------

Implement a custom operation
............................

Lets dive into the ox-orch world by first looking at a custom implementation of an
operation. Here it simply "hello" and "goodbye" messages:

.. code-block:: python

    # Lets define a custom operation
    from pydantic import Field

    from ox_orch.core import register
    from ox_orch.operations import Operation, OperationState

    class HelloState(OperationState):
        _label = "Hello"

        name: str|None = Field(default=None, description="User name")

    @register("hello")
    class Hello(Operation):
        # Assign the state class to the operation
        __state_class__ = HelloState

        # Provide metadata
        _label = "Hello"
        _description = "Prints hello and goodbye messages to user."

        # Lets implement our custom method.
        #  Note the "_" prefix on those methods
        def _apply(self, state, name, **context):
            # Update the state.
            state.name = name
            print(f"Hello {name}")

        def _rollback(self, state, **context):
            if not state.name:
                raise ValueError("Missing name")
            print(f"Goodbye {state.name}!")

Remarks:

- As you can see, we implemented an ``HelloState`` class and assigned it to the operation using ``__state_class__``. This is optional as by default it will uses the parent ``Operation`` class' one.
- The state is updated *in-place* and yielded back to the caller.
- ``@register("hello")``: register the operation using this type id. It ensures that the operation can be used from the engine (on the opposite of abstract or interfaces classes).
- See those ``_label``, ``_description`` or Field usage? It provides extra information that are used for human interaction. See :ref:`op-registry`
- Rollback operation shall rely on the provided state rather than context input. However, there are case where you might need to use this context (eg. access to store, db, etc.).

.. important::

    When you implement an operation, you MUST ensure it is deterministic and reproducible. The same call with the same input allways MUST resolve to the same behavior.

    You also MUST ensure that rollback will reverse the consequences of the state operation. However, the **rollback may not change the state data** as it may lead
    to inconsistencies.

Custom operation code always go to the ``_apply`` and ``_rollback`` method. The entrypoint ``apply`` and ``rollback`` ensure various tasks as init, error handling, etc.

The overriden methods may also yield multiple state, for example when running children operation.

.. code-block:: python

    # Dummy mimick of how Plan does it:
    def _apply(self, state, **context):

        for child in self.operations:
            child_st = child.create_state()
            yield from child.apply(state, **context)


Running
.......

Once we have an operation, can directly call its ``apply`` and ``rollback`` methods:

.. code-block:: python

    operation = Hello()
    state = operation.create_state()

    # Remember that `apply` is a generator
    for child_st in operation.apply(state, name="Alice"):
        print(f"[{child.operation_id}] {child_st.status}, {child_st.name}")

    # Just for proving that the state is modified in-place.
    assert state is child_st
    assert state.name == "Alice"


Displays:

.. code-block::

    ["hello:b43def"] running, None
    Hello Alice
    ["hello:b43def"] completed, Alice


Rollback:

.. code-block:: python

    for child_st in operation.rollback(state):
        print(f"[{child.operation_id}] {child_st.status}, {child_st.name}")

Displays:

.. code-block::

    ["hello:b43def"] rolling_back, None
    Goodbye Alice
    ["hello:b43def"] rolled_back, Alice


Error handling
..............

When an exception is raised, the state's status is set to :py:attr:`~ox_orch.core.state.Status.FAILED` before yielded back. You can
eventually inspect its :py:attr:`~ox_orch.core.state.State._exc` attribute:

.. code-block:: python

    import traceback

    # ...

    traceback.print_exception(state._exc)


States
------

Each Operation run is reflected by a :py:class:`~ox_orch.operations.base.OperationState` instance. It is responsible for:

- Keeping track of the actual :py:class:`~ox_orch.core.state.Status` of an execution (PENDING, COMPLETED, FAILED, ...);
- Keeping information required to rollback the operation;
- Optionally provide extra informations.


When calling ``apply`` or ``rollback``, those methods yield states of the run operation (RUNNING, COMPLETED, FAILED, states optionally yielded from ``_apply`` and ``_rollback``).
State correctness is really important, as they are the key to a successfull rollback. You MUST design them carefully.

More information about states: :ref:`guide-states`.


Registry and stores
-------------------


.. _op-registry:

Registry
........

Operators and state are :py:class:`~ox_orch.core.registry.RegisteredClass`, more precicely :py:class:`~ox_orch.core.pydantic.PolymorphicModel`. This means a few things:

- Operation and state subclasses can be fully de-serialized using pydantic. This allows usage through API, YAML file description of the operation, etc.
- To allow this you must use the :py:func:`~ox_orch.core.registry.register` decorator. It ensure that the related registry knows about the object.
- Depending on the base class, different registry are, which allows us to reuse the same name for different class types -- keeping coherency all along.
- The registration key is also called ``type_id``.


So, lets take the first example:

.. code-block::

    from ox_orch.operations import Operation, OperationState

    op = Hello()
    op_state = op.create_state(name="Alice")

    # Serialize
    op_data = op.model_dump()
    op_state_data = op_state.model_dump()

    # Deserialize from base classes
    deser_op = Operation.model_validate(op_data)
    deser_state = OperationState.model_validate(op_state_data)

    # Magic!
    assert isinstance(deser_op, Hello) and isinstance(deser_state, HelloState)
    assert deser_state.name == "Alice"


You know understand the whole power of this mechanism, because it opens up to many tasks:

- Saving and loading operations and state into file or other backend;
- By-passing them using API or RPC;
- ...


Documented classes
..................

Lets go more precise again: the Operation and OperationState class are of a specific registered class: :py:class:`~ox_orch.core.registry.DocumentedRegistry`.

This ones add extra data that can be reused later to provide information, or auto-generated documentation by:

- Providing the ``_label`` and ``_description`` attributes, describing the object model.
- Assumes that documented fields are annotated using pydantic ``Field.description``.



Stores
......

Operation and OperationState can be committed to and retrieved from stores. A store is a container interface ensuring to provide owned objects by key, update them (full or partial), etc.

They are responsible for:
- owning specific objects and allow to query them;
- updating them, either as a full commit or patching it;
- saving and loading the data from a backend (if persistent). We have for example the :py:class:`~ox_orch.core.stores.FileStore` that do it on files. You can imagine to implement your own stores (eg. db persistence)

See :ref:`guide-stores` for more details.

Here is just a simple example:

.. code-block:: python

    from pydantic import Field
    from ox_orch.core import FileStore, FileBackend, FileStoreModel, JSONBackend
    from ox_orch.operations import OperationState

    # Ensure that registered store data will be correctly de-serialized
    # from the file backend
    class OperationStateStoreModel(FileStoreModel):
        # Data is the actual store's data.
        data: dict[str, OperationState] = Field(default_factory=dict)


    state_store = FileStore(
        # Store arguments
        model_class=OperationState, # The data we store
        key="operation_id",         # The key used to refers to it
        # FileStore arguments
        path=Path("states.json"),   # Path to file
        backend=JSONBackend(OperationStateStoreModel) # File backend
    )

    ops = [Hello(), Hello()]
    states = [op.create_state(name=f"User {i}") for i, op in enumerate(ops)]

    # Commit
    state_store.commit(states)
    assert len(state_store) == 2

    st, st_2 = states
    store_st = state_store.get(st.operation_id)
    assert store_st == st and store_st is not st

    # Partial Commit
    state_store.partial_commit({
        # Provide only the fields to update for each element.
        st.operation_id: {"name": "Alice"}
    })
    assert state_store.get(st.operation_id).name == "Alice"
    assert state_store.get(st_2.operation_id).name == "User 1"

    # Save is triggered manually
    state_store.save()


Presentation of different operation types
-----------------------------------------

Plans
.....

Plans are special kind of operation allowing to run multiple child ones in sequencial
order.

The base class :py:class:`~ox_orch.operations.plan.Plan` can derived for different specific
implementation, as for example :py:class:`~ox_orch.operations.apps.AppPlan`.

.. code-block:: python

    from ox_orch.operations import Plan

    # Lets imagine you have defined custom operations
    plan = Plan(
        pre_operation=MySetup(), # optional
        operations= [
            MyFirstOp(),
            MySecondOp(),
            MyThirdOp(),
        ],
        post_operation=MyCleanup() # optional
    )

Remarks:

- ``operations``: those are the children operation to run. They are rollbacked in reverse order.
- ``pre_operation`` and ``post_operation`` are optional, and meant to be always run before and after all ``operation``, regardless it is rollbacking or not.

This means:

- On ``apply`` run: ``pre_operation`` -> ``operations`` -> ``post_operation``
- On ``rollback`` run: ``pre_operation`` -> ``reverse(operations)`` -> ``post_operation``

The states of the children will be yield upstream, allowing you to catch them when running a plan:

.. code-block::

    # States yielded from Plan.apply
    - plan: running
    - my_setup: running
    - my_setup: completed
    - my_first_op: running
    - my_first_op: completed
    - my_second_op: running
    - my_second_op: completed
    - my_third_op: running
    - my_third_op: completed
    - my_clean_up: running
    - my_clean_up: completed
    - plan: completed


Delegate operations
...................

The :py:class:`~ox_orch.operations.base.DelegateOperation` and its state :py:class:`~ox_orch.operations.base.DelegateState` are meant to run an inner
operation.

It is not aimed to be used directly as an operation, but rather to be implemented
using custom behaviors. Though you can use it as is:

.. code-block:: python

    from ox_orch.operations import DelegateOperation

    op = DelegateOperation(
        operation=MyFirstOp()
    )



Python
......

The :py:class:`~ox_orch.operations.base.RunPython` class allows to run arbitrary python
function on apply and rollback. For security reason, it can not be serialize-deserialized.

.. code-block:: python

    from ox_orch.operations import RunPython

    op = RunPython(
        forward=lambda state, **ctx: print("Apply", state.operation_id),
        backward=lambda state, **ctx: print("Rollback", state.operation_id)
    )
