import pytest

from ox_orch.core import Status, register
from ox_orch.utils import consume_iter
from ox_orch.core.shell import EchoShell
from ox_orch.operations import RunPython, AppsContext, AppsPlan, AppPlan, ReconciliationPlan
from ox_orch.apps import AppState, AppStateFeature

from ..conftest import package_versions, package_next_versions, FakeInstall


# TODO: features update and commit check


@register("test-op-apps")
class AppStateFeatureTest(AppStateFeature):
    name: str | None = None
    value: int | None = None


@pytest.fixture
def op_feature_1():
    def apply(state, *a, app_ctx, **kw):
        app_ctx.app_plan_state.add_facts({"features": {"test-op-apps": {"value": 123}}})

    return RunPython(forward=apply, backward=lambda *a, **kw: None)


@pytest.fixture
def op_feature_2():
    def apply(state, *a, app_ctx, **kw):
        app_ctx.app_plan_state.add_facts({"features": {"test-op-apps": {"name": app_ctx.app.id}}})

    return RunPython(forward=apply, backward=lambda *a, **kw: None)


@pytest.fixture
def update_feature_data():
    return {"test-op-apps": {"name": "feature-2", "value": 123}}


@pytest.fixture
def app_plan(app_meta, op_feature_1, op_feature_2):
    return AppPlan(app=app_meta, operations=[op_feature_1, op_feature_2])


@pytest.fixture
def reconciliation(app_plan):
    return ReconciliationPlan(app_plan=app_plan)


@pytest.fixture
def apps_plan(app_plan, op_1, op_2, op_3):
    return AppsPlan(
        install=FakeInstall(),
        reconciliation=app_plan,
        before_install=[op_1],
        after_install=[op_2],
        # app_plan=app_plan,
        # pre_operations=[op, op_1],
        # operations=[op_2, op_3],
    )


@pytest.fixture
def apps_ctx(app_store, app_state_store, app_dep, app_dep_1):
    return AppsContext(store=app_store, state_store=app_state_store, apps=[app_dep, app_dep_1])


@pytest.fixture
def apps_plan_state(apps_plan):
    return apps_plan.create_state()


class TestAppPlanState:
    def test_add_facts(self, app_plan):
        state = app_plan.create_state()

        state.add_facts({"foo": "bar", "features": {"test": {"name": "test-1", "value": 123}}})
        assert state.facts == {"foo": "bar", "features": {"test": {"name": "test-1", "value": 123}}}

        state.add_facts({"features": {"test": {"value": 564, "value-2": "v2"}}})
        assert state.facts == {"foo": "bar", "features": {"test": {"name": "test-1", "value": 564, "value-2": "v2"}}}


class TestAppPlan:
    def test_create_state(self, app_plan, app_meta):
        state = app_plan.create_state()
        assert state.app == app_meta
        assert state.version == package_versions[app_meta.package]
        assert state.target_version == app_meta.version

    def test_get_inputs(self, app_plan, app_meta, apps_ctx):
        state = app_plan.create_state()
        context = app_plan.get_inputs(state, apps_ctx)
        assert context["app_ctx"].app == app_plan.app
        assert isinstance(context["app_ctx"].app_state, AppState)
        assert context["app_ctx"].app_plan == app_plan
        assert context["app_ctx"].app_plan_state == state


class TestReconciliationPlan:
    def test__apply(self, reconciliation, exec_ctx, apps_ctx, app_dep, app_dep_1, app_meta, app_meta_1):
        state = reconciliation.create_state()
        consume_iter(reconciliation._apply(state, exec_ctx, apps_ctx, shell=EchoShell(), enable=True))

        expected_changes = [app_meta, app_meta_1, app_dep]
        resolved_changes = [st.app for st in state.children]
        assert expected_changes == resolved_changes

        for child_st in state.children:
            # TODO: test child state gathering
            updates = state.forward[child_st.app.id]
            assert updates["status"] == Status.COMPLETED
            assert updates["features"] == {"test-op-apps": {"name": child_st.app.id, "value": 123}}

    def test_get_dirty_apps(self, reconciliation, app_metas, app_state_store):
        changed = reconciliation.get_dirty_apps(app_metas, app_state_store)
        assert changed == app_metas[:-1]


class TestAppsPlan:
    def test_get_operations(self, apps_plan, op_1, op_2):
        assert apps_plan.get_operations(None) == [op_1, apps_plan.install, op_2, apps_plan.reconciliation]

    def test__apply_and_rollback(self, exec_ctx, apps_plan, apps_ctx, app_dep, app_dep_1, app_meta, app_meta_1):
        state = apps_plan.create_state()
        consume_iter(apps_plan._apply(state, exec_ctx, apps_ctx, shell=EchoShell()))

        app_ids = list(state.forward.keys())
        assert app_ids
        assert state.backward

        # Test against versions & features update
        for app_state in apps_ctx.state_store.get_all(app_ids):
            assert app_state.version == package_next_versions[app_state.package]
            # black has not been updated by test fixtures design
            if app_state.id != "black":
                assert app_state.features["test-op-apps"] == AppStateFeatureTest(name=app_state.id, value=123)

        # ---- Rollback!
        consume_iter(apps_plan._rollback(state, exec_ctx, apps_ctx, shell=EchoShell()))

        for app_state in apps_ctx.state_store.get_all(app_ids):
            assert not app_state.features
