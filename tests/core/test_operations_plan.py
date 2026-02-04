import pytest

from django_installer.core.state import State


@pytest.fixture
def plan_state(plan):
    return plan.create_state()


class TestPlan:
    def test_create_state(self, plan, plan_state):
        plan.validate_state(plan_state)

    def test__apply(self, plan, plan_state):
        plan.apply(plan_state)

        assert len(plan_state.states)
        assert plan_state.state == State.DONE
        assert all(s.state == State.DONE for s in plan_state.states)

    def test__apply_fails_with_op(self, plan, plan_state):
        exc = RuntimeError("foo")

        with pytest.raises(RuntimeError):
            plan.apply(plan_state, exc=exc)

        assert plan_state.state == State.ROLLED_BACK
        assert plan_state.states[0].state == State.ROLLED_BACK
        assert plan_state.states[1].state == State.PENDING

    def test__rollback(self, plan, plan_state):
        # Force one value to not be pending
        plan_state.states[1].state = State.DONE
        plan.rollback(plan_state)

        assert plan_state.state == State.ROLLED_BACK
        assert all(s.any(State.ROLLED_BACK, State.PENDING) for s in plan_state.states)

    def test__rollback_fails_with_op(self, plan, plan_state):
        plan_state.states[0].state = State.DONE
        exc = RuntimeError("bar")
        with pytest.raises(RuntimeError):
            plan.rollback(plan_state, rexc=exc)

        assert plan_state.state == State.FAILED
        assert plan_state.states[0].state == State.FAILED
        assert plan_state.error == str(exc)


# class TestAppsPlan:
#     def test___init__(self, apps_plan):
#         pass
#
#     def test___init__fails_with_operations(self, apps_plan):
#         pass
#
#     def test_get_app_plan(self, apps_plan):
#         pass
#
#     def test_get_operation(self, apps_plan):
#         pass
