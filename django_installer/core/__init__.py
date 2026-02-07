from typing import Generator

from . import operations
from .apps import AppMetadata
from .files import YAMLBackend, JSONBackend
from .registry import AppRegistry, MemoryAppRegistry, NotFoundError
from .state import State, Status, StateBackend, StateFileBackend


__all__ = [
    "operations",
    "AppMetadata",
    "AppRegistry",
    "MemoryAppRegistry",
    "NotFoundError",
    "YAMLBackend",
    "JSONBackend",
    "State",
    "Status",
    "StateBackend",
    "StateFileBackend",
    "apply",
    "rollback",
    "wait",
]


def apply(
    operation: operations.AbstractOperation, state_backend: StateBackend, **kwargs
) -> Generator[State, None, None]:
    """
    Apply operation saving state at each change and handling rolling back on error.

    :param operation: the actual operation to apply.
    :param state_backend: the state backend used to load and store the operation's state.
    :param **kwargs: arguments passed to the operation.
    """

    state = state_backend.load()
    for state_ in operation.apply(state, **kwargs):
        state_backend.save(state_)
        yield state


def rollback(
    operation: operations.AbstractOperation, state_backend: StateBackend, **kwargs
) -> Generator[State, None, None]:
    """
    Apply operation saving state at each change and handling rolling back on error.

    :param operation: the actual operation to apply.
    :param state_backend: the state backend used to load and store the operation's state.
    :param **kwargs: arguments passed to the operation.
    """

    state = state_backend.load()
    for state_ in operation.rollback(state, **kwargs):
        state_backend.save(state_)
        yield state


def wait(
    func, operation: operations.AbstractOperation, state_backend: StateBackend, **kwargs
) -> tuple[list[State], Exception | None]:
    """
    Execute the provided :py:meth:`apply` or :py:meth:`rollback` function and
    return the results.

    :param func: ``apply`` or ``rollback`` function.
    :param operation: operation to pass to the function.
    :param state_backend: state backend to pass to the function.
    :param **kwargs: other provided named arguments.
    :return a tuple of the yielded states and exception is any raised.

    Example:

    .. code-block:: python

        from django_installer.core import apply, rollback, wait #, ...

        wait(apply, apps_plan, state_backend)

    """
    states, exc = [], None
    try:
        for state in func(operation, state_backend, **kwargs):
            states.append(state)
    except Exception as err:
        exc = err
    return states, exc
