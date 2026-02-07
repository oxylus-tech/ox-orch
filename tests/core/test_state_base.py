from django.utils import timezone as tz
import pytest

from django_installer.core.state.base import Status, StateInfo, State


@pytest.fixture
def state():
    return State(name="test_op")


class TestState:
    def test_set_status(self, state):
        state.error = "test error"
        vals = [state.status, state.updated, state.error]

        state.set_status(Status.FAILED, "some error")
        assert state.status == Status.FAILED
        assert state.error == "some error"
        assert state.history == [StateInfo(status=vals[0], updated=vals[1], error=vals[2])]

    def test_start(self, state):
        now = tz.now()
        state.start()
        assert state.status == Status.RUNNING
        assert state.updated >= now

    def test_finish(self, state):
        now = tz.now()
        state.finish()
        assert state.status == Status.COMPLETED
        assert state.updated >= now

    def test_rolled_back(self, state):
        state.rolled_back()
        assert state.status == Status.ROLLED_BACK

    def test_fail(self, state):
        exc = Exception("test error")
        state.fail(exc)
        assert state.status == Status.FAILED
        assert state.error == str(exc)

    def test_summary(self, state):
        assert state.summary() == f"test_op (status={state.status})"

    def test_summary_with_nested_states(self, state):
        state.states = [State(name="foo", status=Status.RUNNING), State(name="bar")]

        assert state.summary() == (
            f"test_op (status={state.status}):\n"
            f"- foo (status={Status.RUNNING})\n"
            f"- bar (status={Status.PENDING})"
        )
