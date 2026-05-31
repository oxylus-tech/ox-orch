from __future__ import annotations

from typing import Annotated, Generator
from pydantic import Field, field_validator

from .base import OperationState, Status, AbstractOperation


__all__ = (
    "PlanState",
    "Plan",
)


class PlanState(OperationState):
    """State of a Plan operation."""

    __type_id__ = "state:op:plan"

    children: list[OperationState] = Field(default_factory=list)
    """ Executed children operation states. """
    operation_ids: list[AbstractOperation] = Field(default_factory=list)
    """ Executed operation ids. """

    def get_resume_index(self) -> int:
        """Return resume index."""
        return next((i for i, child in enumerate(self.children) if not child.is_completed), len(self.children))


class Plan(AbstractOperation):
    """
    Plan is an operation composed of child operations.

    Child operations may either be stored in :py:attr:`operations` or
    generated dynamically by overrding :py:meth:`get_operations`.
    """

    operations: Annotated[list[AbstractOperation], Field(subclass_ok=True)]
    """ The operations to run. """
    __type_id__ = "op:plan"
    _state_class = PlanState

    def create_state(self, **kwargs) -> OperationState:
        kwargs["children"] = []
        return super().create_state(**kwargs)

    @field_validator("operations", mode="before")
    def validate_operations(cls, v):
        return [AbstractOperation.model_validate(op) if isinstance(op, dict) and "__type__" in op else op for op in v]

    def _apply(self, state, **context) -> Generator[OperationState]:
        """
        Execute nested operations.

        On failure, it will rollback the whole current operation before raising
        the exception again. The ``**context`` arguments will be passed down to
        the :py:meth:`rollback` method.

        .. note::

            Since the operation raise once rolled back, parent Plan class will
            will rollback too.

        :yield ValueError: state is provided for child operation but does not match.
        """
        operations = self.get_operations(state)

        start_idx = state.get_resume_index()
        for idx in range(start_idx, len(operations)):
            op = operations[idx]

            try:
                if len(state.children) > idx:
                    op_state = state.children[idx]

                    if op_state.operation_id != type(op).__type_id__:
                        raise ValueError(
                            "State operation id does not match to current operation's one: "
                            f"{op_state.operation_id} != {type(op).__type_id__}"
                        )

                else:
                    op_state = op.create_state()
                    state.children.append(op_state)

                yield from op.apply(state=op_state, **context)
            except Exception as exc:
                yield state.fail(exc)
                context["op_idx"] = idx
                yield from self.rollback(state, **context)
                raise

    def _rollback(self, state, **context) -> Generator[OperationState]:
        """
        Execute rollbacks for applied operations (in reverse order).

        On failure, state will be marked as failed and error is raised.

        :param state: the actual state
        :param states: applied states to rollback
        """
        operations = list(self.get_operations(state))
        states = state.children

        # When reversed happens, we want the right state being zipped
        if len(states) < len(operations):
            applied_count = len(states)
            operations = operations[:applied_count]

        for op, op_state in zip(reversed(operations), reversed(states)):
            if op_state.is_any(Status.COMPLETED, Status.RUNNING):
                yield from op.rollback(op_state, **context)

    def get_context(self, state, **context):
        context["plan"] = self
        return super().get_context(state, **context)

    def get_operations(self, state: OperationState) -> Generator[AbstractOperation]:
        """
        Return operations handled by the plan (for apply and rollback).

        :param state: the state for the current plan operation.
        """
        yield from iter(self.operations)
