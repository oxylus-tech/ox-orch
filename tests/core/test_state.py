from django.utils import timezone as tz
import pytest

from ox_installer.core.state import Status, StateInfo, State, StateYAMLBackend


@pytest.fixture
def yaml_file(data_dir):
    path = data_dir / "state.backend.test.yaml"
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def state_file_backend():
    return StateYAMLBackend()


@pytest.fixture
def state():
    return State(name="test state")


class TestState:
    def test_is_any(self, state):
        assert state.is_any(Status.COMPLETED, Status.PENDING)
        assert not state.is_any(Status.COMPLETED, Status.FAILED)

    def test_is_completed(self, state):
        assert not state.is_completed()
        state.status = Status.COMPLETED
        assert state.is_completed()

    def test_was_run(self, state):
        assert not state.was_run()
        state.status = Status.COMPLETED
        assert state.was_run()
        state.status = Status.FAILED
        assert state.was_run()
        state.status = Status.ROLLED_BACK
        assert state.was_run()

    def test_set_status(self, state):
        state.error = "test error"
        vals = [state.status, state.updated, state.error]

        state.set_status(Status.FAILED, "some error")
        assert state.status == Status.FAILED
        assert state.error == "some error"
        assert state.history == [StateInfo(status=vals[0], updated=vals[1], error=vals[2])]

    def test_validate_transition(self, state):
        state.validate_transition(Status.RUNNING)
        with pytest.raises(ValueError):
            state.validate_transition(Status.COMPLETED)

    def test_start(self, state):
        now = tz.now()
        state.start()
        assert state.status == Status.RUNNING
        assert state.updated >= now

    def test_rolling_back(self, state):
        state.status = Status.COMPLETED
        state.rolling_back()
        assert state.status == Status.ROLLING_BACK

    def test_finish(self, state):
        now = tz.now()
        state.status = Status.RUNNING
        state.finish()
        assert state.status == Status.COMPLETED
        assert state.updated >= now

    def test_rolled_back(self, state):
        state.status = Status.ROLLING_BACK
        state.rolled_back()
        assert state.status == Status.ROLLED_BACK

    def test_fail(self, state):
        exc = Exception("test error")
        state.status = Status.RUNNING
        state.fail(exc)
        assert state.status == Status.FAILED
        assert state.error == str(exc)

    def test_summary(self, state):
        assert state.summary() == f"{state.name} (status={state.status})"

    def test_summary_with_nested_states(self, state):
        state.children = [State(name="foo", status=Status.RUNNING), State(name="bar")]
        assert state.summary() == (
            f"{state.name} (status={state.status}):\n"
            f"- foo (status={Status.RUNNING})\n"
            f"- bar (status={Status.PENDING})"
        )


class TestStateFileBackend:
    def test_save_load(self, state_file_backend, yaml_file, op):
        state = op.create_state()
        state.status = Status.FAILED
        state_file_backend.save(state, yaml_file)
        assert yaml_file.exists()

        state = state_file_backend.load(yaml_file)
        assert state.status == Status.FAILED
        assert state._source == yaml_file
