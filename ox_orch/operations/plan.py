from __future__ import annotations

from typing import Annotated, Generator
from pydantic import Field, field_validator

from ox_orch.core import register, TreeState
from .base import OperationState, Status, Operation


__all__ = (
    "PlanState",
    "Plan",
)


@register("plan")
class PlanState(TreeState, OperationState):
    """State of a Plan operation."""

    def get_resume_index(self) -> int:
        """Return resume index."""
        return next((i for i, child in enumerate(self.children) if not child.is_completed), len(self.children))


@register("plan")
class Plan(Operation):
    """
    Plan is an operation composed of child operations.

    Child operations may either be stored in :py:attr:`operations` or
    generated dynamically by overrding :py:meth:`get_operations`.
    """

    __state_class__ = PlanState
    __full_context__ = True

    _label = "Plan"
    _description = (
        "Run multiple operations sequencially.\n"
        "Operations flowcharts:\n"
        "- apply: `pre_operation` => `operations` => `post_operation`;\n"
        "- rollback:  `pre_operation` => `operations` (reverse order) => `post_operation`;"
    )

    pre_operation: Operation | None = Field(
        default=None, description="Operation to run before any other ones, regardless apply or rollback"
    )
    """
    Operation to always run before any other operation, regardless apply or rollback.

    This operation is not provided by the :py:meth:`get_operations`
    """
    post_operation: Operation | None = Field(
        default=None, description="Operation to run at the end, regardless apply or rollback"
    )
    """
    Operation to always run before any other operation, regardless apply or rollback.

    Same as for :py:attr:`pre_operation`.
    """
    operations: Annotated[
        list[Operation], Field(default_factory=list, subclass_ok=True, description="The nested operations to run")
    ]
    """ The operations to run. """

    def create_state(self, **kwargs) -> OperationState:
        kwargs["children"] = []
        return super().create_state(**kwargs)

    @field_validator("operations", mode="before")
    def validate_operations(cls, v):
        return [Operation.model_validate(op) if isinstance(op, dict) and "__type__" in op else op for op in v]

    def _apply(self, state, exec_ctx, **context) -> Generator[OperationState]:
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
        if self.pre_operation:
            operations.insert(0, self.pre_operation)
        if self.post_operation:
            operations.append(self.post_operation)

        start_idx = state.get_resume_index()
        for idx in range(start_idx, len(operations)):
            op = operations[idx]

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

            yield from op.apply(op_state, exec_ctx, **context)

    def _rollback(self, state, exec_ctx, **context) -> Generator[OperationState]:
        """
        Execute rollbacks for applied operations (in reverse order).

        On failure, state will be marked as failed and error is raised.

        :param state: the actual state
        :param states: applied states to rollback
        """
        operations = self.get_operations(state)
        states = list(state.children)

        if self.pre_operation:
            pre_state = states.pop(0)

        if self.post_operation:
            operations.insert(0, self.post_operation)
            states.insert(0, states.pop(-1))

        if self.pre_operation:
            operations.append(self.pre_operation)
            states.append(pre_state)

        # When reversed happens, we want the right state being zipped
        if len(states) < len(operations):
            applied_count = len(states)
            operations = operations[:applied_count]

        for op, op_state in zip(reversed(operations), reversed(states)):
            if op_state.is_any(Status.COMPLETED, Status.RUNNING, Status.FAILED):
                yield from op.rollback(op_state, exec_ctx, **context)

    def get_context(self, state, **context):
        context["plan"] = self
        return super().get_context(state, **context)

    def get_operations(self, state: OperationState) -> list[Operation]:
        """
        Return operations handled by the plan (for apply and rollback).
        This function MUST be deterministic and coherent between
        calls to avoid incoherent and broken states.

        :param state: the state for the current plan operation.
        """
        return self.operations
