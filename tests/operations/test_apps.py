import pytest

from ox_orch.utils import consume_iter
from ox_orch.core.shell import EchoShell
from ox_orch.core.state import Status
from ox_orch.apps import AppState

from ..conftest import package_versions, package_next_versions


@pytest.fixture
def apps_plan_state(apps_plan):
    return apps_plan.create_state()


class TestAppPlan:
    def test_create_state(self, app_plan, app_meta):
        state = app_plan.create_state()
        assert state.version == package_versions[app_meta.package]
        assert state.app_id == app_meta.id
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
            updates = state.forward[child_st.app_id]
            # TODO: test child state gathering
            assert updates["status"] == Status.COMPLETED

    def test_get_dirty_apps(self, reconciliation, app_metas, app_state_store):
        changed = reconciliation.get_dirty_apps(app_metas, app_state_store)
        assert changed == app_metas[:-1]


class TestAppsPlan:
    def test_get_operations(self, apps_plan, op_1, op_2):
        assert apps_plan.get_operations(None) == [op_1, apps_plan.install, op_2, apps_plan.reconciliation]

    def test__apply_and_sync_registry(self, exec_ctx, apps_plan, apps_ctx, app_dep, app_dep_1, app_meta, app_meta_1):
        state = apps_plan.create_state()
        apps = [app_dep, app_dep_1]
        consume_iter(apps_plan._apply(state, exec_ctx, apps_ctx, shell=EchoShell()))

        app_ids = [a.id for a in apps]
        states = apps_ctx.state_store.get_all(app_ids)
        for state in states:
            assert state.version == package_next_versions[state.package]

    def test__rollback_call_sync_registry(self, apps_plan):
        pass

    def test_sync_registry(self, apps_plan):
        pass
