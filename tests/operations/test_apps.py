import pytest

from ox_orch.utils import consume_iter
from ox_orch.core.shell import EchoShell
from ox_orch.core.state import Status

from ..conftest import package_versions, package_next_versions


@pytest.fixture
def apps_plan_state(apps_plan):
    return apps_plan.create_state()


class TestAppPlan:
    def test_create_state(self, app_plan, app_meta):
        state = app_plan.create_state()
        assert state.installed_version == package_versions[app_meta.package]
        assert state.app_id == app_meta.id
        assert state.target_version == app_meta.version

    def test_get_inputs(self, app_plan, app_meta):
        state = app_plan.create_state()
        context = app_plan.get_inputs(state)
        assert context["app"] == app_meta
        assert context["app_state"] == state


class TestReconciliationPlan:
    def test__apply(self, reconciliation, exec_ctx, mem_registry, app_dep, app_dep_1, app_meta, app_meta_1):
        apps = [app_dep, app_dep_1]
        state = reconciliation.create_state()
        consume_iter(
            reconciliation._apply(state, exec_ctx, apps, shell=EchoShell(), app_registry=mem_registry, enable=True)
        )

        expected_changes = [app_meta, app_meta_1, app_dep]
        resolved_changes = [st.app for st in state.children]
        assert expected_changes == resolved_changes

        state.validate_diffs()
        for child_st in state.children:
            updates = state.forward[child_st.app_id]
            # TODO: test child state gathering
            assert updates["status"] == Status.COMPLETED

    def test_get_dirty_apps(self, reconciliation, app_metas):
        changed = reconciliation.get_dirty_apps(app_metas)
        assert changed == app_metas[:-1]


class TestAppsPlan:
    def test_get_operations(self, apps_plan, mem_registry, op_1, op_2):
        assert apps_plan.get_operations(None) == [op_1, apps_plan.install, op_2, apps_plan.reconciliation]

    def test__apply_and_sync_registry(
        self, exec_ctx, apps_plan, mem_registry, app_dep, app_dep_1, app_meta, app_meta_1
    ):
        state = apps_plan.create_state()
        apps = [app_dep, app_dep_1]
        consume_iter(apps_plan._apply(state, exec_ctx, apps, mem_registry, shell=EchoShell(), enable=True))

        app_ids = [a.id for a in apps]
        commit_apps = mem_registry.get_all(app_ids)
        for app in commit_apps:
            assert app.state.installed_version == package_next_versions[app.package]

    def test__rollback_call_sync_registry(self, apps_plan):
        pass

    def test_sync_registry(self, apps_plan):
        pass
