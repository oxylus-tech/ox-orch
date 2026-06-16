import pytest


from ox_orch.core.stores import (
    StoreMetadata,
    MemoryStore,
    FileStore,
    FileStoreModel,
)
from ox_orch.core.files import JSONBackend

from ..conftest import DummyModel


@pytest.fixture
def item_a():
    return DummyModel(name="a", value=1)


@pytest.fixture
def item_b():
    return DummyModel(name="b", value=2)


@pytest.fixture
def memory_store(item_a):
    store = MemoryStore(
        model_class=DummyModel,
        key="name",
    )
    store.commit([item_a])
    return store


@pytest.fixture
def backend():
    return JSONBackend(FileStoreModel)


@pytest.fixture
def file_store(tmp_path, backend):
    return FileStore(
        path=tmp_path / "store.json",
        model_class=DummyModel,
        key="name",
        backend=backend,
    )


class TestStoreMetadata:
    def test_defaults(self):
        metadata = StoreMetadata()
        assert metadata.created_at is not None
        assert metadata.updated_at is not None
        assert metadata.version is None
        assert metadata.backend is None
        assert metadata.extra == {}


class TestMemoryStore:

    def test_get_metadata(self, memory_store):
        assert isinstance(memory_store.get_metadata(), StoreMetadata)

    def test_get_existing(self, memory_store, item_a):
        assert memory_store.get("a") == item_a

    def test_get_missing(self, memory_store):
        assert memory_store.get("missing") is None

    def test_get_all(self, memory_store, item_a):
        result = memory_store.get_all(["a", "missing"])
        assert result == [item_a]

    def test_commit_new_item(self, memory_store, item_b):
        memory_store.commit([item_b])
        assert memory_store.get("b") == item_b

    def test_delete_existing(self, memory_store):
        memory_store.delete("a")
        assert memory_store.get("a") is None

    def test_delete_missing(self, memory_store):
        memory_store.delete("missing")

    def test_missing_model_class(self):
        with pytest.raises(ValueError):
            MemoryStore(None, key="name")

    def test_partial_commit_update(self, memory_store):
        memory_store.partial_commit({"a": {"value": 42}})

        assert memory_store.get("a").value == 42

    def test_partial_commit_delete(self, memory_store):
        memory_store.partial_commit({"a": None})

        assert memory_store.get("a") is None


class TestFileStoreModel:
    def test_defaults(self):
        model = FileStoreModel()
        assert model.data == {}
        assert isinstance(model.metadata, StoreMetadata)


class TestFileStore:

    def test_save_and_load(self, file_store, item_a):
        file_store.commit([item_a])
        file_store.save()

        loaded = FileStore(
            path=file_store.path,
            model_class=DummyModel,
            key="name",
            backend=file_store.backend,
        )

        loaded.load()

        assert "a" in loaded.data
        assert loaded.data["a"].name == "a"
        assert loaded.data["a"].value == 1

    def test_load_missing_file(self, file_store):
        file_store.load()
        assert file_store.data == {}

    def test_save_persists_metadata(self, file_store, item_a):
        file_store.metadata.version = "1.0"
        file_store.commit([item_a])
        file_store.save()

        loaded = FileStore(
            path=file_store.path,
            model_class=DummyModel,
            key="name",
            backend=file_store.backend,
        )

        loaded.load()
        assert loaded.metadata.version == "1.0"

    def test_backend_list_not_allowed(self, tmp_path):
        backend = JSONBackend(FileStoreModel, as_list=True)

        with pytest.raises(ValueError):
            FileStore(
                path=tmp_path / "store.json",
                model_class=DummyModel,
                key="name",
                backend=backend,
            )
