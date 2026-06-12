from typing import Generator, Optional

from ox_orch.core.state import StateBackend, Status

from .base import OPERATION_REGISTRY, STATE_REGISTRY, RunContext, OperationState, AbstractOperation, RunPython
from .plan import Plan
from .apps import AppPlanState, AppPlan, ReconciliationPlan, AppsPlan
from .subprocess import SubprocessOperation


__all__ = (
    # Base
    "OPERATION_REGISTRY",
    "STATE_REGISTRY",
    "RunContext",
    "OperationState",
    "AbstractOperation",
    "RunPython",
    # Plan
    "Plan",
    "AppPlan",
    "AppPlanState",
    "ReconciliationPlan",
    "AppsPlan",
    # Others
    "SubprocessOperation",
    # re-exports
    "Status",
)


def apply(
    operation: AbstractOperation, state: OperationState, state_backend: Optional[StateBackend] = None, **kwargs
) -> Generator[OperationState, None, None]:
    """
    Apply operation saving state at each change and handling rolling back on error.

    :param operation: the actual operation to apply.
    :param state_backend: the state backend used to load and store the operation's state.
    :param **kwargs: arguments passed to the operation.
    """

    for state_ in operation.apply(state, **kwargs):
        state_backend and state_backend.save(state_)
        yield state


def rollback(
    operation: AbstractOperation, state: OperationState, state_backend: Optional[StateBackend] = None, **kwargs
) -> Generator[OperationState, None, None]:
    """
    Apply operation saving state at each change and handling rolling back on error.

    :param operation: the actual operation to apply.
    :param state_backend: the state backend used to load and store the operation's state.
    :param **kwargs: arguments passed to the operation.
    """

    for state_ in operation.rollback(state, **kwargs):
        state_backend and state_backend.save(state_)
        yield state


def wait(
    func, operation: AbstractOperation, state: OperationState, raises=True, *args, **kwargs
) -> list[OperationState] | tuple[list[OperationState], Exception | None]:
    """
    Execute the provided :py:meth:`apply` or :py:meth:`rollback` function and
    return the results.

    :param func: ``apply`` or ``rollback`` function.
    :param operation: operation to pass to the function.
    :param state: operation state
    :param *args: other provided positional arguments
    :param **kwargs: other provided named arguments.
    :return a tuple of the yielded states and exception is any raised.

    Example:

    .. code-block:: python

        from ox_orch.core import apply, rollback, wait #, ...

        wait(apply, apps_plan, state_backend)

    """
    states, exc = [], None
    try:
        for state in func(operation, state, *args, **kwargs):
            states.append(state)
    except Exception as err:
        exc = err
        if raises:
            raise
    return states if raises else states, exc
