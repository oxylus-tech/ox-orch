from multiprocessing import Queue, Process
from typing import Any, Literal

from .base import Operation, OperationState


__all__ = ("BaseFork", "ForkOperation", "ForkChild", "fork_entry")


class BaseFork(Operation):
    """
    This is the base class to use to spawn a new child process for a nested operation.

    It does not implement the apply and rollback methods,
    only provide common argument and the :py:meth:`run`.

    ** Read the doc of :py:meth:`ForkOperation` for more information. **
    """

    operation: Operation
    """ The operation to execute in the child process. """
    queue_max_size: int = 64
    """ Max size for a queue. """

    def run(self, method, state, args, kwargs):
        queue = Queue(maxsize=self.queue_max_size)
        try:
            process = Process(
                target=fork_entry,
                args=(
                    queue,
                    self.operation,
                    method,
                    state,
                    args,
                    kwargs,
                ),
            )
            process.start()

            while True:
                typ, dat = queue.get(True)
                match typ:
                    case "state":
                        yield dat
                    case "done":
                        break
                    case "error":
                        process.terminate()
                        raise RuntimeError(dat)

            process.join()
        finally:
            queue.close()


class ForkOperation(BaseFork):
    """
    This operation allows to spawn a new child process in which its nested
    operation will be run.

    .. important::

        It is strongly recommanded to read about fork and memory mechanisms
        before implementing any operation that shall be run in a child process.

    The default implementation of the operation will simply act
    as proxy to the nested operation:

        - The state and its validation will be the child's one;
        - Apply & Rollback run child's equivalent methods;

    Process invokation & constraints
    --------------------------------

    The forked process is started in ``spawn`` mode. This implies that:

        - All input parameters shall be pickable (serializable);
        - Memory is not shared between parent and child process;
        - Only states are provided back to the ForkRunner.

    A forked operation may:

        - read stores, files;
        - inspect the environment and execute commands;
        - compute change sets;
        - update its own state;
        - create child states;

    It may not:

        - commit to stores or save them;
        - mutate parent-owned runtime objects;

    The method used to actually run the child operation is :py:func:`fork_entry`. This method add context value
    ``forked=True`` allowing children to detect it.
    """

    operation: Operation
    """ The operation to execute in the child process. """
    queue_max_size: int = 64
    """ Max size for a queue. """

    def create_state(self, *args, **kwargs):
        """Return nested operation state."""
        return self.operation.create_state(*args, **kwargs)

    def validate_state(self, state):
        self.operation.validate_state(state)

    def _apply(self, state, *args, **kwargs):
        self.run("apply", state, args, kwargs)

    def _rollback(self, state, *args, **kwargs):
        self.run("rollback", state, args, kwargs)


class ForkChild(Operation):
    """
    This is an helper class that enforce an operation to run in forked subprocess.

    In such case it will raise a RuntimeError on apply and rollback.
    """

    def apply(self, *args, **kwargs):
        if not kwargs.get("forked"):
            raise RuntimeError(f"{self.__type_id__} MUST be spawned from a fork operation.")
        yield from super().apply(*args, **kwargs)

    def rollback(self, *args, **kwargs):
        if not kwargs.get("forked"):
            raise RuntimeError(f"{self.__type_id__} MUST be spawned from a fork operation.")
        yield from super().rollback(*args, **kwargs)


def fork_entry(
    queue: Queue,
    operation: Operation,
    method: Literal["apply", "rollback"],
    state: OperationState,
    args: list[Any],
    kwargs: dict[str, Any],
):
    """
    This is the main entry point to execute an operation into a child process.

    The value of ``init_hook`` is a dotted path to a function to execute before
    the operation is run. It takes as argument: ``operation, state, *args, **kwargs``.

    :param operation: Operation to run.
    :param method: Method to execute.
    :param state: Operation state.
    :param args: Operation method positional arguments.
    :param kwargs: Operation method named arguments.
    :param queue: RPC queue
    :param init_hook: Import string to init function to execute before the operation is called.
    """

    try:
        func = getattr(operation, method)
        kwargs["forked"] = True
        for st in func(state, *args, **kwargs):
            queue.put(("state", st))

    except Exception as e:
        queue.put(("error", str(e)))
        raise
    finally:
        try:
            queue.put(("done", None))
        except Exception:
            pass
