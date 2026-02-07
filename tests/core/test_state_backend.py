import pytest

from django_installer.core import state, files


@pytest.fixture
def yaml_file(data_dir):
    path = data_dir / "state.backend.test.yaml"
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def state_file_backend(yaml_file, apps_plan):
    return state.StateFileBackend(yaml_file, files.YAMLBackend, state=apps_plan.create_state())


class TestStateFileBackend:
    def test_save_load(self, state_file_backend):
        state_file_backend.state.status = state.Status.FAILED
        state_file_backend.save()
        assert state_file_backend.path.exists()

        # Check if the saved one is correctly saved and loaded
        state_file_backend.state.status = state.Status.RUNNING
        state_file_backend.load()
        assert state_file_backend.state.status == state.Status.FAILED
