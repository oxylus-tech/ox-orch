import pytest

from ox_orch.core.state import Status

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
                (plan.id, Status.RUNNING),
                (op.id, Status.RUNNING),
                (op.id, Status.COMPLETED),
                (op_1.id, Status.RUNNING),
                (op_1.id, Status.COMPLETED),
                (plan.id, Status.COMPLETED),
            ],
        )

    def test__apply_fails_with_op(self, plan, plan_state, op, op_1):
        exc = RuntimeError("foo")
        states, exc_ = apply(plan, plan_state, exc=exc)

        assert exc_ is exc
        assert plan_state.status == Status.FAILED
        assert_states(
            states,
            [
                (plan.id, Status.RUNNING),
                (op.id, Status.RUNNING),
                (op.id, Status.FAILED, exc),
                (plan.id, Status.FAILED, exc),
            ],
        )

    def test__rollback(self, plan, plan_state, op, op_1):
        # Force one value to not be pending
        # Note that only op_1 will be rolled back, no op
        plan_state.status = Status.COMPLETED
        plan_state.children = [
            op.create_state(status=Status.COMPLETED),
            op_1.create_state(status=Status.COMPLETED),
        ]
        states, exc_ = rollback(plan, plan_state)

        assert not exc_
        assert plan_state.status == Status.ROLLED_BACK
        assert_states(
            states,
            [
                (plan.id, Status.ROLLING_BACK),
                (op_1.id, Status.ROLLING_BACK),
                (op_1.id, Status.ROLLED_BACK),
                (op.id, Status.ROLLING_BACK),
                (op.id, Status.ROLLED_BACK),
                (plan.id, Status.ROLLED_BACK),
            ],
        )

    def test__rollback_fails_with_op(self, plan, plan_state, op, op_1):
        plan_state.status = Status.COMPLETED
        plan_state.children = [
            op.create_state(status=Status.COMPLETED),
            op_1.create_state(status=Status.COMPLETED),
        ]
        exc = RuntimeError("bar")
        states, exc_ = rollback(plan, plan_state, rexc=exc)

        assert exc is exc_
        assert_states(
            states,
            [
                (plan.id, Status.ROLLING_BACK),
                (op_1.id, Status.ROLLING_BACK),
                (op_1.id, Status.FAILED, exc),
                (plan.id, Status.FAILED, exc),
            ],
        )

    def test_get_operations(self, plan, plan_state):
        assert list(plan.get_operations(plan_state)) == plan.operations
