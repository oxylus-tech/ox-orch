import pytest

from ox_orch.core import files, state


@pytest.fixture
def yaml_backend():
    return files.YAMLBackend(state.State)


@pytest.fixture
def json_backend():
    return files.JSONBackend(state.State)
