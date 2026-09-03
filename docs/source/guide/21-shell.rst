.. _guide-shell:

Shell
=====

Some operations may require to execute custom process or python commands. What you'll may want in such case is to provide an environment or its variables. The idea behind the :py:mod:`ox_orch.core.shell` module is to provide a common configuration for those operations.

So how does it work?

- A :py:class:`~ox_orch.core.shell.ShellSpec` is defined on :py:class:`~ox_orch.operations.execution.ExecutionSpec` class (default is provided).
- This class is mapped to a :py:class:`~ox_orch.core.shell.Shell` on attribute ``shell`` on the :py:class:`~ox_orch.operations.execution.ExecutionContext`.
- Operations then can use it to :py:meth:`~ox_orch.core.shell.Shell.run` commands.


.. code-block:: python

    from ox_orch.operations import Operation

    class PrintHello(Operation):
        def _apply(self, state, exec_ctx, **context):
            """ Just call the echo command. """
            exec_ctx.shell.run(["echo", f"Hello this is {state.operation_id}"])

Some usefull Shell methods:

- A :py:class:`~ox_orch.core.shell.run`: you know it already ;)
- A :py:class:`~ox_orch.core.shell.run_python`: execute python with the provided arguments.
- A :py:class:`~ox_orch.core.shell.run_python_module`: execute a python module with the provided arguments.


We also provide two classes to use with operations:

- A :py:class:`~ox_orch.operations.shell.ShellMixin`: handles apply and rollback using arguments returned by ``get_forward`` and ``get_backward`` methods (both MUST be implemented);
- A :py:class:`~ox_orch.operations.shell.ShellOperation`: allows to only provide forward and backward commands.

.. code-block:: python

    from ox_orch.operations import Operation
    from ox_orch.operations.shell import ShellOperation, ShellMixin

    # Simple invokation example
    shell = ShellOperation(
        forward=["echo", "apply!"],
        backward=["echo", "rollback!"]
    )

    # Subclassing:
    class PrintHello(ShellMixin, Operation):
        def get_forward(self, state, **context):
            return ["echo", f"Hello this is {state.operation_id}"]

        def get_backward(self, state, **context):
            return ["echo", f"Goodbye from {state.operation_id}"]


Spec and execution
------------------

You can provide custom specification for the shell at the executor level, by setting :py:attr:`ox_orch.operations.execution.ExecutionSpec.shell` attribute to an instance of :py:class:`~ox_orch.core.shell.ShellSpec`.

Here are the main attributes:

- :py:attr:`~ox_orch.core.shell.ShellSpec.backend`: execution backend, currently only ``local`` (default) and ``echo`` (only print, don't run anything);
- :py:attr:`~ox_orch.core.shell.ShellSpec.python`: python executable path, using ``PYTHON_EXECUTABLE`` env variable by default or current executable.
- :py:attr:`~ox_orch.core.shell.ShellSpec.cwd`: current working directory.
- :py:attr:`~ox_orch.core.shell.ShellSpec.env`: environment variable.
- :py:attr:`~ox_orch.core.shell.ShellSpec.timeout`: execution timeout (defaults to ``None``).

.. code-block:: python

    # Example setting
    exec_spec = ExecutionSpec(
        operation=Operation(),
        # Optional as default is provided
        shell=ShellSpec(env={"VAR_1": "VALUE 1"})
    )

    # Example updating
    exec_spec.shell.env["VAR_2"] = "VALUE 2"


Environment
-----------

It was initially envisionned to provide multiple shell as for docker, remote ssh etc. However for the sake of simplicity, it was decided not to as you can run ox-orch from within remote containers.

What it does mean is that if you want to run within a container or environment, you'll have to run it from within it. However, you still can provide custom python interpreter though the ShellSpec's :py:attr:`~ox_orch.core.shell.ShellSpec.python`.

However, if you still want to implement custom shell runner, you'll have to:

- Subclass :py:class:`~ox_orch.core.shell.Shell`, overriding the ``run`` method.
- Register it to :py:attr:`~ox_orch.core.shell.SHELL_REGISTRY` dict by backend name.
