import pytest

from pydantic import ValidationError
from django_installer.core.state import State
from django_installer.core.operations import AppsPlan, AppPlan


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


class TestAppsPlan:
    def test___init__(self, apps_plan):
        assert len(apps_plan.operations) == len(apps_plan.pre_operations) + len(apps_plan.apps)

        assert apps_plan.operations == apps_plan.get_operations()

    def test___init__fails_with_operations(self):
        with pytest.raises(ValidationError):
            AppsPlan(operations=[])

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
