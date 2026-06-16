import json

import pytest
import yaml

from ox_orch.core.files import YAMLBackend, JSONBackend, JSONLBackend
from ..conftest import DummyModel


@pytest.fixture
def yaml_list_backend():
    return YAMLBackend(DummyModel, as_list=True)


@pytest.fixture
def json_list_backend():
    return JSONBackend(DummyModel, as_list=True)


@pytest.fixture
def jsonl_backend():
    return JSONLBackend(DummyModel)


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
        assert dat.operation_id

    def test_save(self, yaml_backend, yaml_out, op_state):
        yaml_backend.save(yaml_out, op_state)
        assert yaml_out.exists()

    def test_save_and_load_list(self, yaml_list_backend, yaml_out):
        objs = [DummyModel(name="a"), DummyModel(name="b")]

        yaml_list_backend.save(yaml_out, objs)
        loaded = yaml_list_backend.load(yaml_out)

        assert isinstance(loaded, list)
        assert [o.name for o in loaded] == ["a", "b"]

    def test_as_list_mismatch(self, yaml_backend, yaml_file):
        backend = YAMLBackend(DummyModel, as_list=True)

        with pytest.raises(ValueError):
            backend.load(yaml_file)  # file contains dict, not list

    def test_assert_as_list_guard(self, yaml_list_backend):
        yaml_list_backend = YAMLBackend(DummyModel, as_list=False)

        with pytest.raises(RuntimeError):
            yaml_list_backend.assert_as_list()

    def test_append_single_item(self, yaml_list_backend, tmp_path):
        path = tmp_path / "data.yaml"

        yaml_list_backend.append(path, DummyModel(name="a"))
        yaml_list_backend.append(path, DummyModel(name="b"))

        loaded = yaml_list_backend.load(path)

        assert len(loaded) == 2
        assert [o.name for o in loaded] == ["a", "b"]

    def test_append_overwrites_file_correctly(self, yaml_list_backend, tmp_path):
        path = tmp_path / "data.yaml"

        yaml_list_backend.append(path, DummyModel(name="a"))
        yaml_list_backend.append(path, DummyModel(name="b"))

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert isinstance(data, list)
        assert len(data) == 2

    def test_append_requires_list_mode(self, yaml_backend, tmp_path):
        path = tmp_path / "data.yaml"

        with pytest.raises(RuntimeError):
            yaml_backend.append(path, DummyModel(name="x"))


class TestJSONBackend:
    def test_load(self, json_backend, json_file):
        dat = json_backend.load(json_file)
        assert dat.operation_id

    def test_save(self, json_backend, json_out, op_state):
        json_backend.save(json_out, op_state)
        assert json_out.exists()

    def test_save_and_load_list(self, json_list_backend, json_out):
        objs = [DummyModel(name="x"), DummyModel(name="y")]

        json_list_backend.save(json_out, objs)
        loaded = json_list_backend.load(json_out)

        assert isinstance(loaded, list)
        assert [o.name for o in loaded] == ["x", "y"]

    def test_append_single_and_multiple(self, tmp_path):
        path = tmp_path / "data.json"

        backend = JSONBackend(DummyModel, as_list=True)

        backend.save(path, [DummyModel(name="a")])
        backend.append(path, DummyModel(name="b"))
        backend.append(path, [DummyModel(name="c"), DummyModel(name="d")])

        loaded = backend.load(path)

        assert len(loaded) == 4
        assert [o.name for o in loaded] == ["a", "b", "c", "d"]

    def test_append_creates_file(self, tmp_path):
        path = tmp_path / "data.json"

        backend = JSONBackend(DummyModel, as_list=True)

        backend.append(path, DummyModel(name="first"))

        loaded = backend.load(path)

        assert len(loaded) == 1
        assert loaded[0].name == "first"


class TestJSONLAppend:
    def test_append_streaming_behavior(self, tmp_path, jsonl_backend):
        path = tmp_path / "trace.jsonl"

        jsonl_backend.append(path, DummyModel(name="a"))
        jsonl_backend.append(path, DummyModel(name="b"))
        jsonl_backend.append(path, [DummyModel(name="c"), DummyModel(name="d")])

        with open(path, "r", encoding="utf-8") as f:
            lines = [json.loads(l_) for l_ in f if l_.strip()]

        assert len(lines) == 4
        assert [x["name"] for x in lines] == ["a", "b", "c", "d"]

    def test_order_is_preserved(self, tmp_path, jsonl_backend):
        path = tmp_path / "trace.jsonl"

        for i in range(5):
            jsonl_backend.append(path, DummyModel(name=str(i)))

        with open(path, "r", encoding="utf-8") as f:
            names = [json.loads(l_)["name"] for l_ in f]

        assert names == ["0", "1", "2", "3", "4"]
