from multiprocessing import Queue, Process
from typing import Any, Literal

from ox_orch.core.registry import register
from .base import Operation, OperationState


__all__ = ("ForkOperation", "fork_entry")


@register("fork")
class ForkOperation(Operation):
    """
    This operation allows to spawn a new child process in which its nested
    operation will be run.

    **It is strongly recommanded to read about fork and memory mechanisms
    before implementing any operation that shall be run in a child process.**

    The forked process is started in spawn mode. This implies that:

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
