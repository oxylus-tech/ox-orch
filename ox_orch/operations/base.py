from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Generator

from pydantic import Field

from ox_orch.core import register
from ox_orch.core.operation import OperationState, Operation, OperationContext


__all__ = ("RunPython", "DelegateState", "DelegateOperation")


@register("python")
class RunPython(Operation):
    """Run python code."""

    forward: Callable[(Operation, OperationState, OperationContext), None]
    backward: Callable[(Operation, OperationState, OperationContext), None]

    _label = "🐍 Run python code"
    _description = "Run python code. Internal usage only: you can't use it from specification file or API."

    def _apply(self, state, **context):
        self.forward(self, state, **context)

    def _rollback(self, state, **context):
        self.backward(self, state, **context)


class DelegateState(OperationState):
    """
    Operation state for a :py:class:`ParentOperation`.
    The nested operation state resides in :py:attr:`child`.
    """

    child: OperationState | None = Field(description="Nested operation state.")


class DelegateOperation(Operation, ABC):
    """
    An abstract class for operation that requires to run a nested one.
    """

    __state_class__ = DelegateState

    operation: Operation = Field(description="The operation to run inside this one.")

    def _apply(self, state, **context):
        if state.child is None:
            state.child = self.operation.create_state()
        for child_st in self.child_apply(state, **context):
            state.child = child_st
            yield child_st
            yield state

    def _rollback(self, state, **context):
        for child_st in self.child_rollback(state, **context):
            state.child = child_st
            yield child_st
            yield state

    @abstractmethod
    def child_apply(self, state: DelegateState, **context) -> Generator[OperationState, None]:
        pass

    @abstractmethod
    def child_rollback(self, state: DelegateState, **context) -> Generator[OperationState, None]:
        pass
