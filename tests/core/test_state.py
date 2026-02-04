from django.utils import timezone as tz
import pytest

from django_installer.core.state import State, OperationState


@pytest.fixture
def state():
    return OperationState(name="test_op")


class TestOperationState:
    def test_start(self, state):
        now = tz.now()
        state.start()
        assert state.state == State.RUNNING
        assert state.started_at >= now

    def test_finish(self, state):
        now = tz.now()
        state.finish()
        assert state.state == State.DONE
        assert state.finished_at >= now

    def test_rolled_back(self, state):
        state.rolled_back()
        assert state.state == State.ROLLED_BACK

    def test_fail(self, state):
        exc = Exception("test error")
        state.fail(exc)
        assert state.state == State.FAILED
        assert state.error == str(exc)

    def test_summary(self, state):
        assert state.summary() == f"test_op (status={state.state})"

    def test_summary_with_nested_states(self, state):
        state.states = [OperationState(name="foo", state=State.RUNNING), OperationState(name="bar")]

        assert state.summary() == (
            f"test_op (status={state.state}):\n" f"- foo (status={State.RUNNING})\n" f"- bar (status={State.PENDING})"
        )
