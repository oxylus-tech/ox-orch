import pytest

from ox_orch.core.shell import EchoShell
from ox_orch.operations import apply, rollback, wait
from ox_orch.core.state import Status, StateBackend


@pytest.fixture
def state_backend(apps_plan):
    return StateBackend()


def test_apply_rollback_wait_simple_workflow(apps_plan, state_backend, mem_registry, app_metas):
    state = apps_plan.create_state()
    st, exc = wait(
        apply,
        apps_plan,
        state,
        state_backend=state_backend,
        app_registry=mem_registry,
        apps=app_metas,
        shell=EchoShell(),
    )
    assert state.status == Status.COMPLETED

    states, exc = wait(
        rollback,
        apps_plan,
        state,
        state_backend=state_backend,
        app_registry=mem_registry,
        apps=app_metas,
        shell=EchoShell(),
    )
    assert state.status == Status.ROLLED_BACK
