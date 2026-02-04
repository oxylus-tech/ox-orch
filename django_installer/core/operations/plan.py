from typing import Optional, Type

from .base import AbstractOperation
from ..apps import AppMetadata
from ..state import OperationState, State


__all__ = ("Plan", "AppPlan")


class Plan(AbstractOperation):
    """Run multiple operations sequentially."""

    operations: list[AbstractOperation]
    """ The operations to run. """
    name: str = "plan"

    def create_state(self, **kwargs) -> OperationState:
        kwargs["states"] = []
        state = super().create_state(**kwargs)
        for idx, op in enumerate(self.operations):
            op_state = op.create_state()
            state.states.append(op_state)
        return state

    def validate_state(self, state, recurse=False):
        super().validate_state(state)

        assert len(state.states) == len(self.operations)

        # This arguments avoids double validation on
        # apply/rollback.
        if recurse:
            for idx, op in enumerate(self.operations):
                if len(state.states) <= idx:
                    raise ValueError(f"Missing state for operation `{op}`")
                op.validate_state(state.states[idx])

    def _apply(self, state, **kwargs):
        kwargs["plan"] = self

        for idx, op in enumerate(self.operations):
            try:
                op_state = state.states[idx]
                op.apply(state=op_state, **kwargs)
            except Exception as exc:
                state.fail(exc)
                self.rollback(state, op_idx=idx, **kwargs)
                state.rolled_back(exc)
                raise
        state.finish()

    def _rollback(self, state, op_idx=None, **kwargs):
        kwargs["plan"] = self

        if op_idx:
            ops, states = self.operations[: op_idx + 1], state.states[: op_idx + 1]
        else:
            ops, states = self.operations, state.states

        for op, op_state in zip(reversed(ops), reversed(states)):
            try:
                if not op_state.any(State.PENDING, State.ROLLED_BACK):
                    op.rollback(op_state, **kwargs)
            except Exception as exc:
                state.fail(exc)
                raise
        state.rolled_back()


class AppPlan(Plan):
    app: AppMetadata

    def _apply(self, **kwargs):
        kwargs["app"] = self.app
        super()._apply(**kwargs)

    def _rollback(self, **kwargs):
        kwargs["app"] = self.app
        super()._apply(**kwargs)


class AppsPlan(Plan):
    """
    Installation plan for multiple applications.
    """

    apps: list[AppMetadata]
    """ Ordered list of applications. """
    pre_operations: Optional[list[AbstractOperation]] = None
    """ Operations to run before AppPlan ones. """
    post_operations: Optional[list[AbstractOperation]] = None
    """ Operations to run after AppPlan ones. """
    app_operations: Optional[list[AbstractOperation]] = None
    """ Operation to set on each AppPlan. """

    app_plan_class: Type[AppPlan] = AppPlan

    def __init__(self, **kwargs):
        self.forbid_operations_field(kwargs)

        super().__init__(**kwargs)

        if self.pre_operations is None:
            self.pre_operations = type(self).pre_operations or []
        if self.post_operations is None:
            self.post_operations = type(self).post_operations or []

        self.operations = self.get_operations(self.apps)

    def forbid_operations_field(cls, values):
        if "operations" in values:
            raise ValueError(
                "You are not allowed to set `operations` on AppsPlan; use `app_plans`, `pre_operations`,"
                "`post_operations` instead"
            )
        return values

    def get_app_plan(self, app: AppMetadata, **kwargs):
        kwargs["operations"] = self.app_operations
        return self.app_plan_class(app=app, **kwargs)

    def get_operations(self):
        return self.pre_operations + [self.get_app_plan(app) for app in self.apps] + self.post_operations
