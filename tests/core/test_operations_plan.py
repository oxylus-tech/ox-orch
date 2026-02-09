import pytest

from pydantic import ValidationError
from django_installer.core.state import Status
from django_installer.core.operations import AppsPlan, AppPlan

from .conftest import apply, rollback, assert_states


@pytest.fixture
def plan_state(plan):
    return plan.create_state()


class TestPlan:
    def test_create_state(self, plan, plan_state):
        plan.validate_state(plan_state)

    def test__apply(self, plan, plan_state, op, op_1):
        states, exc_ = apply(plan, plan_state)

        assert not exc_
        assert plan_state.status == Status.COMPLETED
        assert_states(
            states,
            [
                (plan.operation_id, Status.RUNNING),
                (op.operation_id, Status.RUNNING),
                (op.operation_id, Status.COMPLETED),
                (op_1.operation_id, Status.RUNNING),
                (op_1.operation_id, Status.COMPLETED),
                (plan.operation_id, Status.COMPLETED),
            ],
        )

    def test__apply_fails_with_op(self, plan, plan_state, op, op_1):
        exc = RuntimeError("foo")
        states, exc_ = apply(plan, plan_state, exc=exc)

        assert exc_ is exc
        assert plan_state.status == Status.ROLLED_BACK
        assert_states(
            states,
            [
                (plan.operation_id, Status.RUNNING),
                (op.operation_id, Status.RUNNING),
                (op.operation_id, Status.FAILED, exc),
                (plan.operation_id, Status.FAILED, exc),
                (plan.operation_id, Status.ROLLING_BACK),
                (op.operation_id, Status.ROLLING_BACK),
                (op.operation_id, Status.ROLLED_BACK),
                (plan.operation_id, Status.ROLLED_BACK),
            ],
        )

    def test__rollback(self, plan, plan_state, op, op_1):
        # Force one value to not be pending
        # Note that only op_1 will be rolled back, no op
        plan_state.status = Status.COMPLETED
        plan_state.children[0].status = Status.COMPLETED
        plan_state.children[1].status = Status.COMPLETED
        states, exc_ = rollback(plan, plan_state)

        assert not exc_
        assert plan_state.status == Status.ROLLED_BACK
        assert_states(
            states,
            [
                (plan.operation_id, Status.ROLLING_BACK),
                (op.operation_id, Status.ROLLING_BACK),
                (op.operation_id, Status.ROLLED_BACK),
                (op_1.operation_id, Status.ROLLING_BACK),
                (op_1.operation_id, Status.ROLLED_BACK),
                (plan.operation_id, Status.ROLLED_BACK),
            ],
        )

    def test__rollback_fails_with_op(self, plan, plan_state, op):
        plan_state.status = Status.COMPLETED
        plan_state.children[0].status = Status.COMPLETED
        plan_state.children[1].status = Status.COMPLETED
        exc = RuntimeError("bar")
        states, exc_ = rollback(plan, plan_state, rexc=exc)

        assert exc is exc_
        assert_states(
            states,
            [
                (plan.operation_id, Status.ROLLING_BACK),
                (op.operation_id, Status.ROLLING_BACK),
                (op.operation_id, Status.FAILED, exc),
                (plan.operation_id, Status.FAILED, exc),
            ],
        )


class TestAppsPlan:
    def test___init__(self, apps_plan):
        assert len(apps_plan.operations) == len(apps_plan.pre_operations) + len(apps_plan.apps)

        assert apps_plan.operations == apps_plan.get_operations()

    def test___init__fails_with_operations(self, op):
        with pytest.raises(ValidationError):
            AppsPlan(operations=[op])

    def test___init__fails_with_apps(self, app_meta):
        with pytest.raises(ValidationError):
            AppsPlan(apps=[app_meta])

    def test_get_operation(self, apps_plan):
        ops = apps_plan.get_operations()
        assert ops[0] == apps_plan.pre_operations[0]
        assert isinstance(ops[1], AppPlan)
        assert ops[1].app == apps_plan.apps[0]
        assert ops[1].operations == apps_plan.app_operations
        assert ops[2].app == apps_plan.apps[1]

    def test_get_app_plan(self, apps_plan, app_meta):
        plan = apps_plan.get_app_plan(app_meta)
        assert plan.app == app_meta
        assert plan.operations == apps_plan.app_operations
