import pytest


@pytest.fixture
def yaml_file(data_dir):
    return data_dir / "state-0.yaml"


@pytest.fixture
def json_file(data_dir):
    return data_dir / "state-0.json"


@pytest.fixture
def yaml_out(data_dir):
    path = data_dir / "state.test.yaml"
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def json_out(data_dir):
    path = data_dir / "state.test.json"
    yield path
    path.unlink(missing_ok=True)


class TestFileAndYAMLBackend:
    def test_load(self, yaml_backend, yaml_file):
        dat = yaml_backend.load(yaml_file)
        assert dat.name

    def test_save(self, yaml_backend, yaml_out, op_state):
        yaml_backend.save(yaml_out, op_state)
        assert yaml_out.exists()


class TestJSONBackend:
    def test_load(self, json_backend, json_file):
        dat = json_backend.load(json_file)
        assert dat.name

    def test_save(self, json_backend, json_out, op_state):
        json_backend.save(json_out, op_state)
        assert json_out.exists()
