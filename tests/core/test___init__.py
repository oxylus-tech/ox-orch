import pytest

from django_installer.core.operations import apply, rollback, wait
from django_installer.core.state import Status, StateBackend


@pytest.fixture
def state_backend(apps_plan):
    return StateBackend()


def test_apply_rollback_wait_simple_workflow(apps_plan, state_backend):
    state = apps_plan.create_state()
    wait(apply, apps_plan, state, state_backend)
    assert state.status == Status.COMPLETED

    states, exc = wait(rollback, apps_plan, state, state_backend)
    assert state.status == Status.ROLLED_BACK
