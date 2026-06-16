from ox_orch.core.shell import EchoShell
from ox_orch.operations import apply, rollback, wait
from ox_orch.core.state import Status


def test_apply_rollback_wait_simple_workflow(apps_plan, apps_ctx, app_metas):
    state = apps_plan.create_state()
    st, exc = wait(
        apply,
        apps_plan,
        state,
        apps_ctx=apps_ctx,
        shell=EchoShell(),
    )
    assert state.status == Status.COMPLETED

    states, exc = wait(
        rollback,
        apps_plan,
        state,
        apps_ctx=apps_ctx,
        shell=EchoShell(),
    )
    assert state.status == Status.ROLLED_BACK
