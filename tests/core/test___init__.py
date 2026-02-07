import pytest

from django_installer.core import apply, rollback, wait, Status, StateBackend


@pytest.fixture
def state_backend(apps_plan):
    return StateBackend(apps_plan.create_state())


def test_apply_rollback_wait_simple_workflow(apps_plan, state_backend):
    wait(apply, apps_plan, state_backend)
    assert state_backend.state.status == Status.COMPLETED

    wait(rollback, apps_plan, state_backend)
    assert state_backend.state.status == Status.ROLLED_BACK
