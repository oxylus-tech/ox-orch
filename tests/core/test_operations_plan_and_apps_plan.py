import pytest

from pydantic import ValidationError
from django_installer.core.state import Status
from django_installer.core.operations import AppsPlan

from .conftest import apply, rollback, assert_states


@pytest.fixture
def plan_state(plan):
    return plan.create_state()


@pytest.fixture
def plan_states(plan, plan_state):
    plan_state.children = [op.create_state() for op in plan.operations]
    return plan_state.children


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
                (plan.__type_id__, Status.RUNNING),
                (op.__type_id__, Status.RUNNING),
                (op.__type_id__, Status.COMPLETED),
                (op_1.__type_id__, Status.RUNNING),
                (op_1.__type_id__, Status.COMPLETED),
                (plan.__type_id__, Status.COMPLETED),
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
                (plan.__type_id__, Status.RUNNING),
                (op.__type_id__, Status.RUNNING),
                (op.__type_id__, Status.FAILED, exc),
                (plan.__type_id__, Status.FAILED, exc),
                (plan.__type_id__, Status.ROLLING_BACK),
                (op.__type_id__, Status.ROLLING_BACK),
                (op.__type_id__, Status.ROLLED_BACK),
                (plan.__type_id__, Status.ROLLED_BACK),
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
                (plan.__type_id__, Status.ROLLING_BACK),
                (op.__type_id__, Status.ROLLING_BACK),
                (op.__type_id__, Status.ROLLED_BACK),
                (op_1.__type_id__, Status.ROLLING_BACK),
                (op_1.__type_id__, Status.ROLLED_BACK),
                (plan.__type_id__, Status.ROLLED_BACK),
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
                (plan.__type_id__, Status.ROLLING_BACK),
                (op.__type_id__, Status.ROLLING_BACK),
                (op.__type_id__, Status.FAILED, exc),
                (plan.__type_id__, Status.FAILED, exc),
            ],
        )

    def test_get_operations(self, plan, plan_state):
        assert list(plan.get_operations(plan_state)) == plan.operations

    def test_get_operations_with_states(self, plan, plan_state, plan_states):
        assert list(plan.get_operations(plan_state, plan_states)) == plan.operations

    def test_get_operations_with_states_fails(self, plan, plan_state, plan_states):
        with pytest.raises(ValueError):
            list(plan.get_operations(plan_state, plan_states + plan_states))


@pytest.fixture
def apps_plan_state(apps_plan):
    return apps_plan.create_state()


class TestAppsPlan:
    def test___init__fails_with_apps(self, mem_registry, app_meta):
        with pytest.raises(ValidationError):
            AppsPlan(mem_registry, apps=[app_meta])

    def test_operations(self, apps_plan, apps_plan_state, app_meta, app_meta_1, app_dep):
        def get_implicit_updates(self, *args):
            yield app_dep

        apps_plan.__dict__["get_implicit_updates"] = get_implicit_updates
        assert list(apps_plan.get_operations(apps_plan_state)) == [
            *apps_plan.pre_operations,
            apps_plan.get_app_plan(app_meta),
            apps_plan.get_app_plan(app_meta_1),
            apps_plan.get_app_plan(app_dep),
            *apps_plan.operations,
        ]

    def test_operations_from_states(self, apps_plan, apps_plan_state, app_dep):
        app_ops = [apps_plan.get_app_plan(app) for app in apps_plan.apps]
        dep_op = apps_plan.get_app_plan(app_dep)
        states = [
            *(op.create_state() for op in apps_plan.pre_operations),
            *(op.create_state() for op in app_ops),
            dep_op.create_state(),
            *(op.create_state() for op in apps_plan.operations[:1]),
        ]

        assert list(apps_plan.get_operations(apps_plan_state, states)) == [
            *apps_plan.pre_operations,
            *app_ops,
            dep_op,
            *apps_plan.operations[:1],
        ]

    def test_get_implicit_updates(self, apps_plan):
        pass

    def test_load_apps(self, apps_plan):
        pass

    def test_get_app_plan(self, apps_plan, app_meta):
        plan = apps_plan.get_app_plan(app_meta)
        assert plan.app == app_meta
        assert plan.operations == apps_plan.app_plan.operations
